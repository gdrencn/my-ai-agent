"""Owned connector-only system service, independent from native model units."""
import hashlib
import os
from pathlib import Path
import pwd
import sys
from ..output import run
from ..service import escaped, exec_arg, privileged
from ..store import Error, atomic, read, write
from .packaging import runtime_bytes


def require_systemd():
    if not Path('/run/systemd/system').exists():
        raise Error('Connectors require systemd inside mas')


class Controller:
    def __init__(self, store, unit_dir=None, executable=None):
        self.store = store
        self.unit = 'maa-connectors-' + str(os.getuid()) + '.service'
        self.path = Path(unit_dir or '/etc/systemd/system') / self.unit
        self.executable = Path(executable or Path.home() / '.local/share/my-ai-agent/connectors.pyz')
        self.marker = '# my-ai-agent IM owner uid=' + str(os.getuid()) + '\n'

    def check(self):
        if self.path.with_suffix(self.path.suffix + '.d').exists():
            raise Error('Unmanaged connector service overrides; remove them explicitly first')
        saved = read(self.store.checked('service.json'))
        for path, key in ((self.path, 'unit_sha256'), (self.executable, 'runtime_sha256')):
            if path.is_symlink():
                raise Error('Refusing symlink in connector installation')
            if path.exists() and (not saved or hashlib.sha256(path.read_bytes()).hexdigest() != saved.get(key)):
                raise Error('Connector installation was modified or is not owned: {v0}', v0=str(path))
        return saved

    def active(self):
        result = run(['systemctl', 'is-active', self.unit], capture_output=True, text=True, timeout=5)
        return result.stdout.strip() in ('active', 'activating', 'reloading')

    def enabled(self):
        result = run(['systemctl', 'is-enabled', self.unit], capture_output=True, text=True, timeout=5)
        return result.stdout.strip() == 'enabled'

    def install(self):
        saved = self.check()
        require_systemd()
        blob = runtime_bytes()
        user = pwd.getpwuid(os.getuid()).pw_name
        unit = (self.marker + '[Unit]\nDescription=my-ai-agent basic IM connectors\n'
                'After=network-online.target\nWants=network-online.target\n\n[Service]\n'
                f'User={user}\nEnvironment={escaped("HOME=" + str(Path.home()))}\n'
                f'Environment={escaped("MAA_IM_HOME=" + str(self.store.root))}\n'
                f'ExecStart={exec_arg(sys.executable)} {exec_arg(self.executable)}\n'
                'Restart=on-failure\nRestartSec=5\nTimeoutStopSec=15\nKillMode=control-group\n'
                'UMask=0077\nNoNewPrivileges=true\n\n[Install]\nWantedBy=multi-user.target\n')
        if (saved and self.path.exists() and self.executable.exists() and
                saved['runtime_sha256'] == hashlib.sha256(blob).hexdigest() and
                saved['unit_sha256'] == hashlib.sha256(unit.encode()).hexdigest()):
            return
        previous = {p: (p.read_bytes(), p.stat().st_mode & 0o777) if p.exists() else None
                    for p in (self.executable, self.path, self.store.path('service.json'))}
        running, enabled = self.active(), self.enabled()
        try:
            if running:
                self.stop()
            atomic(self.executable, blob, 0o755)
            self._write_unit(unit)
            write(self.store.path('service.json'), {'version': 1, 'unit_sha256': hashlib.sha256(unit.encode()).hexdigest(),
                                                  'runtime_sha256': hashlib.sha256(blob).hexdigest()})
            privileged(['systemctl', 'daemon-reload'])
            self.sync(any(row['enabled'] for row in self.store.config()['connections'].values()))
        except BaseException:
            for path, saved in previous.items():
                if path == self.path:
                    if saved:
                        self._write_unit(saved[0].decode())
                    elif path.exists():
                        privileged(['rm', '--', str(path)])
                elif saved:
                    atomic(path, *saved)
                else:
                    path.unlink(missing_ok=True)
            privileged(['systemctl', 'daemon-reload'])
            if previous[self.path]:
                privileged(['systemctl', 'enable' if enabled else 'disable', self.unit])
                if running:
                    privileged(['systemctl', 'start', self.unit])
            raise

    def _write_unit(self, content):
        temp = self.store.path('service.tmp')
        atomic(temp, content)
        try:
            privileged(['install', '-D', '-m', '644', str(temp), str(self.path)])
        finally:
            temp.unlink(missing_ok=True)

    def sync(self, enabled):
        self.check()
        if not self.path.exists():
            if enabled:
                raise Error('Install the connector module first')
            return
        privileged(['systemctl', 'enable' if enabled else 'disable', self.unit])
        privileged(['systemctl', 'start' if enabled else 'stop', self.unit])

    def stop(self):
        self.check()
        if self.path.exists():
            privileged(['systemctl', 'stop', self.unit])

    def uninstall(self):
        self.check()
        if self.path.exists():
            privileged(['systemctl', 'disable', '--now', self.unit])
            privileged(['rm', '--', str(self.path)])
            privileged(['systemctl', 'daemon-reload'])
        self.executable.unlink(missing_ok=True)
