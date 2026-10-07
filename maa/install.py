"""Official installers, container guard, owned entrypoints and unit setup."""
import http.client
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import urllib.request
from . import codex
from .service import Controller, privileged
from .store import Error, Store, atomic
from .output import operation, stage, native_output

URLS = {'ollama': 'https://ollama.com/install.sh',
        'llamacpp': 'https://llama.app/install.sh',
        'codex': 'https://chatgpt.com/codex/install.sh'}


def require_container():
    try:
        connection = http.client.HTTPConnection('localhost', timeout=3)
        connection.sock = socket.socket(socket.AF_UNIX)
        connection.sock.settimeout(3)
        connection.sock.connect('/dev/lxd/sock')
        connection.request('GET', '/1.0/config/user.mas.managed')
        response = connection.getresponse()
        value = response.read(4096).decode().strip('"\n ')
        connection.close()
        status = response.status
        if status in (401, 403) and os.geteuid() != 0:
            # devlxd exposes instance config only to container root. The manager
            # stays owned by the invoking user; sudo reads only this mas marker.
            probe = privileged(['curl', '-fsS', '--unix-socket', '/dev/lxd/sock',
                                'http://localhost/1.0/config/user.mas.managed'],
                               capture_output=True, text=True)
            value, status = probe.stdout.strip('"\n '), 200
        if status != 200 or value not in ('true', '1'):
            raise Error('Not a mas-managed container')
    except (OSError, http.client.HTTPException) as exc:
        raise Error('Install/configure inside a mas container, not on the host') from exc


def component(name):
    with operation('安装底座 / Codex CLI'):
        _component(name)


def _component(name):
    require_container()
    names = list(URLS) if name == 'all' else [name]
    for item in names:
        stage(f'下载安装程序：{item}')
        with tempfile.NamedTemporaryFile(suffix='.sh') as source:
            # Use the official command's curl behavior (redirects and TLS). Some
            # official CDN frontends reject Python's default HTTP user agent.
            subprocess.run(['curl', '-fsSL', URLS[item], '-o', source.name], check=True)
            env = dict(os.environ, CODEX_NON_INTERACTIVE='true')
            try:
                stage(f'官方安装：{item}')
                with native_output():
                    print(f'官方安装：{item} — {URLS[item]}', flush=True)
                    subprocess.run(['sh', source.name], env=env, cwd=Path.home(), check=True)
            finally:
                if item == 'ollama' and Path('/etc/systemd/system/ollama.service').exists():
                    # Also quiesce a partially installed official daemon on error.
                    privileged(['systemctl', 'disable', '--now', 'ollama.service'])
        if item == 'codex':
            codex.yolo(True)


def product(archive, components='all'):
    require_container()
    from .manager import Manager
    store = Store()
    controller = Controller(store)
    controller.ensure()
    legacy = controller.legacy_path()
    if legacy is not None:
        was_running = subprocess.run(['systemctl', 'is-active', '--quiet', 'maa.service']).returncode == 0
    else:
        was_running = controller.running()
    controller.migrate()
    root = Path.home() / '.local/share/my-ai-agent'
    executable = root / 'maa.pyz'
    atomic(executable, Path(archive).read_bytes(), 0o755)
    bindir = Path.home() / '.local/bin'
    import shlex
    for name, command in [('maa', '')]:
        path = bindir / name
        marker = '# managed by my-ai-agent\n'
        if path.exists() and marker not in path.read_text():
            raise Error(f'Existing command is not owned by maa: {path}')
        wrapper = '#!/bin/sh\n' + marker + 'exec ' + shlex.quote(sys.executable) + ' ' + shlex.quote(str(executable)) + command + ' "$@"\n'
        atomic(path, wrapper, 0o755)
    codex.install_launcher()
    codex.yolo(True)
    if components != 'none':
        manager = Manager()
        with manager.store.lock(), manager.maintenance():
            component(components)
    if store.selected():
        manager = Manager(store, controller)
        manager.start()
        if not was_running:
            manager.pause()
    print(f'my-ai-agent 已安装：{executable}\n运行 {bindir / "maa"} 打开菜单。', flush=True)
