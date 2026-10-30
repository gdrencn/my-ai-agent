"""Linux capabilities and software prerequisites, independent of deployment."""
import os
from pathlib import Path
import re
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


def ca_available():
    """Inspect native trust offline, including OpenSSL's lazy hashed directories."""
    if ssl.create_default_context().get_ca_certs():
        return True
    paths = ssl.get_default_verify_paths()
    directories = os.environ.get(paths.openssl_capath_env, paths.openssl_capath)
    for directory in (directories or '').split(os.pathsep):
        if not directory:
            continue
        try:
            for certificate in Path(directory).iterdir():
                # OpenSSL looks up certificates by subject-hash.N, not arbitrary
                # PEM filenames or CRL hash.rN entries. Symlinks are native here.
                if not re.fullmatch(r'[0-9a-f]{8}\.[0-9]+', certificate.name):
                    continue
                try:
                    if not certificate.is_file():
                        continue
                    probe = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                    probe.load_verify_locations(cafile=str(certificate))
                    if probe.get_ca_certs():
                        return True
                except OSError:
                    continue
        except OSError:
            continue
    return False


def missing_dependencies(component='none'):
    commands = {'curl': 'curl', 'install': 'coreutils', 'rm': 'coreutils', 'truncate': 'coreutils'}
    if component in ('ollama', 'all'):
        commands.update(tar='tar', gzip='gzip', zstd='zstd')
    missing = {package for command, package in commands.items() if not shutil.which(command)}
    if not ca_available():
        missing.add('ca-certificates')
    return sorted(missing)


PACKAGE_MANAGERS = (
    ('apt-get', (('update',), ('install', '-y'))),
    ('dnf', (('install', '-y'),)),
    ('yum', (('install', '-y'),)),
    ('zypper', (('--non-interactive', 'install'),)),
    ('pacman', (('-S', '--needed', '--noconfirm'),)),
)
PACKAGE_ALIASES = {'pacman': {'python3': 'python'}}


def package_commands(packages):
    """Use the same package command table as generated shell bootstrappers."""
    for tool, operations in PACKAGE_MANAGERS:
        if shutil.which(tool):
            native_packages = [PACKAGE_ALIASES.get(tool, {}).get(p, p) for p in packages]
            return [[tool, *args, *(native_packages if i == len(operations)-1 else [])]
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
