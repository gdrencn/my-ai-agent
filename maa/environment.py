"""Linux capabilities and software prerequisites, independent of deployment."""
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
from .store import Error


def require_linux():
    if sys.platform != 'linux' or sys.version_info < (3, 11):
        raise Error('Linux and Python 3.11+ are required')


def require_systemd():
    require_linux()
    if not shutil.which('systemctl') or not Path('/run/systemd/system').is_dir():
        raise Error('A running systemd system manager is required')
    result = subprocess.run(['systemctl', 'show', '--property=Version', '--value'],
                            capture_output=True, text=True, timeout=10)
    if result.returncode or not result.stdout.strip():
        raise Error('Cannot communicate with the systemd system manager: {v0}',
                    v0=result.stderr.strip())


def missing_dependencies(component='none'):
    commands = {'curl': 'curl', 'install': 'coreutils', 'rm': 'coreutils', 'truncate': 'coreutils'}
    if component in ('ollama', 'all'):
        commands.update(tar='tar', gzip='gzip', zstd='zstd')
    missing = {package for command, package in commands.items() if not shutil.which(command)}
    if not ssl.create_default_context().get_ca_certs():
        missing.add('ca-certificates')
    return sorted(missing)


PACKAGE_MANAGERS = (
    ('apt-get', (('update',), ('install', '-y'))),
    ('dnf', (('install', '-y'),)),
    ('yum', (('install', '-y'),)),
    ('zypper', (('--non-interactive', 'install'),)),
    ('pacman', (('-S', '--needed', '--noconfirm'),)),
)


def package_commands(packages):
    """Use the same package command table as generated shell bootstrappers."""
    for tool, operations in PACKAGE_MANAGERS:
        if shutil.which(tool):
            return [[tool, *args, *(packages if i == len(operations)-1 else [])]
                    for i, args in enumerate(operations)]
    raise Error('Install missing dependencies with your package manager: {v0}', v0=', '.join(packages))


def prepare_dependencies(component='none'):
    require_systemd()
    missing = missing_dependencies(component)
    if not missing:
        return
    if os.geteuid() != 0 and not shutil.which('sudo'):
        raise Error('Installing dependencies requires root or sudo: {v0}', v0=', '.join(missing))
    from .output import operation, stage
    from .service import privileged
    with operation('准备运行依赖'):
        for command in package_commands(missing):
            stage('安装依赖：{v0}', v0=' '.join(command))
            privileged(command, native=True)
    remaining = missing_dependencies(component)
    if remaining:
        raise Error('Dependencies remain unavailable after installation: {v0}', v0=', '.join(remaining))
