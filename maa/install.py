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
from .store import Error, Store, atomic, write
from .output import operation, stage, run, diagnostic

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
            run(['curl', '-fsSL', URLS[item], '-o', source.name], check=True)
            env = dict(os.environ, CODEX_NON_INTERACTIVE='true')
            try:
                stage(f'官方安装：{item}')
                diagnostic(f'官方安装：{item} — {URLS[item]}\n')
                run(['sh', source.name], native=True, env=env, cwd=Path.home(), check=True)
            finally:
                if item == 'ollama' and Path('/etc/systemd/system/ollama.service').exists():
                    # Also quiesce a partially installed official daemon on error.
                    privileged(['systemctl', 'disable', '--now', 'ollama.service'])


def product(archive, components='all'):
    require_container()
    from .manager import Manager
    store = Store()
    controller = Controller(store)
    root = Path.home() / '.local/share/my-ai-agent'
    executable = root / 'maa.pyz'
    bindir = Path.home() / '.local/bin'
    import shlex
    entry = bindir / 'maa'
    blob = Path(archive).read_bytes()
    with store.lock():
        controller.ensure()
        legacy = controller.legacy_path()
        codex.check_entrypoint(entry)
        codex.check_entrypoint(codex.launcher_path())
        codex.preflight()
        marker = store.path('installation.json')
        first = not any(path.exists() for path in (executable, entry, codex.launcher_path(), marker,
                        store.path('selected.json'), store.path('models.json'), codex.home() / 'maa-yolo-recovery.json')) and legacy is None
        paths = (executable, entry, codex.launcher_path(), marker,
                 codex.home() / 'config.toml', codex.home() / 'maa-yolo-recovery.json')
        backup = {path: (path.read_bytes(), path.stat().st_mode & 0o777) if path.exists() else None for path in paths}
        try:
            atomic(executable, blob, 0o755)
            wrapper = ('#!/bin/sh\n# managed by my-ai-agent\nexec ' + shlex.quote(sys.executable) +
                       ' ' + shlex.quote(str(executable)) + ' "$@"\n')
            atomic(entry, wrapper, 0o755)
            codex.install_launcher()
            if first:
                codex.yolo(True)
            write(marker, {'version': 1})
        except BaseException as primary:
            try:
                for path, saved in backup.items():
                    if saved is None:
                        path.unlink(missing_ok=True)
                    else:
                        atomic(path, *saved)
            except BaseException as secondary:
                detail = f'Installation rollback failed: {secondary}'
                if isinstance(primary, KeyboardInterrupt):
                    raise KeyboardInterrupt(detail) from primary
                raise Error(f'{primary}\n{detail}') from primary
            raise
        # Rejected inputs and failed entrypoint writes never migrate services.
        was_running = (run(['systemctl', 'is-active', '--quiet', 'maa.service']).returncode == 0
                       if legacy is not None else controller.running())
        controller.migrate()
    if components != 'none':
        manager = Manager(store, controller)
        manager.install(components)
    if store.selected() and legacy is not None:
        manager = Manager(store, controller)
        manager.start()
        if not was_running:
            manager.pause()
    print(f'my-ai-agent 已安装：{executable}\n运行 {bindir / "maa"} 打开菜单。', flush=True)
