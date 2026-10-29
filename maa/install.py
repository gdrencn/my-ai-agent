"""Official installers, prerequisite preparation and owned entrypoints."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
from . import codex
from .service import Controller, privileged
from .store import Error, Store, atomic, write
from .output import operation, stage, run, diagnostic
from . import preferences
from .i18n import t, text
from .environment import prepare_dependencies

URLS = {'ollama': 'https://ollama.com/install.sh',
        'llamacpp': 'https://llama.app/install.sh',
        'codex': 'https://chatgpt.com/codex/install.sh'}



def component(name):
    with operation('安装底座 / Codex CLI'):
        _component(name)


def _component(name):
    prepare_dependencies(name)
    names = list(URLS) if name == 'all' else [name]
    for item in names:
        stage('下载安装程序：{v0}', v0=item)
        with tempfile.NamedTemporaryFile(suffix='.sh') as source:
            # Use the official command's curl behavior (redirects and TLS). Some
            # official CDN frontends reject Python's default HTTP user agent.
            run(['curl', '-fsSL', URLS[item], '-o', source.name], check=True)
            env = dict(os.environ, CODEX_NON_INTERACTIVE='true')
            try:
                stage('官方安装：{v0}', v0=item)
                diagnostic(text('官方安装：{v0} — {v1}\n', v0=item, v1=URLS[item]))
                run(['sh', source.name], native=True, env=env, cwd=Path.home(), check=True)
            finally:
                if item == 'ollama' and Path('/etc/systemd/system/ollama.service').exists():
                    # Also quiesce a partially installed official daemon on error.
                    privileged(['systemctl', 'disable', '--now', 'ollama.service'])


def product(archive, components='all', *, language=None):
    selected_language = preferences.installation_language(language)
    with preferences.using(selected_language):
        return _product(archive, components, selected_language)


def _product(archive, components, selected_language):
    from . import __version__
    print(t('installing', version=__version__), flush=True)
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
        prepare_dependencies(components)
        marker = store.path('installation.json')
        first = not any(path.exists() for path in (executable, entry, codex.launcher_path(), marker,
                        store.path('selected.json'), store.path('models.json'), codex.home() / 'maa-yolo-recovery.json')) and legacy is None
        paths = (executable, entry, codex.launcher_path(), marker,
                 codex.home() / 'config.toml', codex.home() / 'maa-yolo-recovery.json', preferences.path())
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
            preferences.set_language(selected_language)
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
                raise Error('{v0}\n{v1}', v0=primary, v1=detail) from primary
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
    print(t('installed', executable=executable, entry=bindir / 'maa'), flush=True)
