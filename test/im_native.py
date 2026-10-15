"""Installed connector lifecycle inside a disposable mas container.

No official account credentials are used. Protocol send/receive fixtures run in
the paired portable suite; this file verifies actual units, ownership and local
cleanup with an empty runtime and a disabled, fictional WhatsApp credential.
"""
import datetime
import hashlib
import inspect
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid


def run(product=None):
    """Never run lifecycle operations under the installed user's identity."""
    from maa import __version__
    from maa.install import require_container
    from maa.service import privileged
    require_container()
    archive = Path(product or Path.home() / '.local/share/my-ai-agent/maa.pyz').resolve()
    report = {'version': __version__, 'invoking_uid': os.getuid(),
              'kind': 'isolated native connector lifecycle, no official accounts',
              'product_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
              'status': 'failed', 'checks': []}
    path = Path.home() / ('maa-im-native-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') +
                          '-' + uuid.uuid4().hex[:8] + '.json')
    try:
        with tempfile.TemporaryDirectory(prefix='maa-im-native-helper-') as folder:
            source, result = Path(folder) / 'im_native.py', Path(folder) / 'result.json'
            source.write_text(inspect.getsource(sys.modules[__name__]))
            try:
                value = privileged([sys.executable, str(source), '--isolate', str(archive), str(result)],
                                   capture_output=True, text=True, timeout=300)
                print(value.stdout, end='', flush=True)
            except subprocess.CalledProcessError as exc:
                print(exc.stdout or '', end='', flush=True)
                print(exc.stderr or '', end='', file=sys.stderr, flush=True)
                report['error'] = 'Isolated connector helper exited ' + str(exc.returncode)
                raise
            finally:
                if result.exists():
                    report.update(json.loads(result.read_text()))
    finally:
        report['finished'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        path.chmod(0o600)
        print('报告：' + str(path), flush=True)
    assert report['status'] == 'passed', report
    return report


def isolate(product, result):
    """Root helper: allocate one private identity, then remove only its resources."""
    assert os.geteuid() == 0
    # The root helper also checks containment; calling this file directly cannot
    # allocate a test user on the host.
    sys.path.insert(0, str(product))
    from maa.install import require_container
    require_container()
    user = 'maa-im-test-' + uuid.uuid4().hex[:12]
    report = {'status': 'failed', 'test_user': user, 'checks': [], 'cleanup': []}
    child = None
    uid = None
    home = Path(tempfile.mkdtemp(prefix='maa-im-native-home-'))
    sudoers = Path('/etc/sudoers.d') / user
    unit_path = None
    claimed_unit = False
    authorization_created = False
    completed = False

    def command(*args):
        return subprocess.run(args, check=True, text=True, capture_output=True, timeout=20)

    def interrupted(signum, frame):
        raise KeyboardInterrupt('Native connector test interrupted')

    signal.signal(signal.SIGTERM, interrupted)
    try:
        command('useradd', '--system', '--no-create-home', '--no-user-group',
                '--home-dir', str(home), '--shell', '/usr/sbin/nologin', user)
        uid = pwd.getpwnam(user).pw_uid
        report['test_uid'] = uid
        unit = 'maa-connectors-' + str(uid) + '.service'
        unit_path = Path('/etc/systemd/system') / unit
        assert not unit_path.exists() and not unit_path.is_symlink() and not unit_path.with_suffix('.service.d').exists(), 'Test UID has an existing connector unit'
        assert command('systemctl', 'show', unit, '-p', 'LoadState', '--value').stdout.strip() == 'not-found', 'Test UID has an existing loaded unit'
        claimed_unit = True
        archive = home / '.local/share/my-ai-agent/maa.pyz'
        archive.parent.mkdir(parents=True)
        shutil.copyfile(product, archive)
        source = home / 'im_native.py'
        shutil.copyfile(__file__, source)
        # Only this temporary identity may manage this temporary connector unit.
        # No sudo authorization for another user's unit or native model services.
        rule = (f'{user} ALL=(root) NOPASSWD: /usr/bin/systemctl daemon-reload, '
                f'/usr/bin/systemctl start {unit}, /usr/bin/systemctl stop {unit}, '
                f'/usr/bin/systemctl enable {unit}, /usr/bin/systemctl disable {unit}, '
                f'/usr/bin/systemctl disable --now {unit}, '
                f'/usr/bin/install -D -m 644 {home}/.local/state/my-ai-agent-im/service.tmp {unit_path}, '
                f'/usr/bin/rm -- {unit_path}, '
                '/usr/bin/curl -fsS --unix-socket /dev/lxd/sock http\\://localhost/1.0/config/user.mas.managed\n')
        with sudoers.open('x') as file:
            authorization_created = True
            file.write(rule)
        sudoers.chmod(0o440)
        command('visudo', '-c', '-f', str(sudoers))
        for root, directories, files in os.walk(home):
            for item in [Path(root)] + [Path(root) / name for name in directories + files]:
                os.chown(item, uid, pwd.getpwnam(user).pw_gid)
        child = subprocess.Popen(['runuser', '-u', user, '--', 'env', '-i', 'HOME=' + str(home),
                                  'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                                  'LANG=C.UTF-8', sys.executable, str(source), '--worker'],
                                 cwd='/', start_new_session=True)
        code = child.wait(timeout=180)
        worker_result = home / 'worker-result.json'
        if worker_result.exists():
            report.update(json.loads(worker_result.read_text()))
        assert code == 0, 'Isolated connector worker exited ' + str(code)
        assert report['status'] == 'passed', report
        completed = True
    finally:
        # The privileged helper must finish its bounded cleanup even if another
        # interrupt arrives here. Its caller still retains the cancellation.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        errors = []
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        if claimed_unit:
            try:
                if unit_path.exists():
                    assert unit_path.read_text().startswith(f'# my-ai-agent IM owner uid={uid}\n'), 'Refusing cleanup of foreign test unit'
                    command('systemctl', 'disable', '--now', unit_path.name)
                    unit_path.unlink()
                    command('systemctl', 'daemon-reload')
                assert subprocess.run(['systemctl', 'is-active', '--quiet', unit_path.name]).returncode != 0
                report['cleanup'].append('connector-unit')
            except BaseException as exc:
                errors.append('connector-unit: ' + str(exc))
        try:
            if authorization_created:
                sudoers.unlink(missing_ok=True)
            report['cleanup'].append('test-sudo-authorization')
            if uid is not None and not errors:
                assert pwd.getpwnam(user).pw_uid == uid, 'Test user identity changed'
                command('userdel', user)
                report['cleanup'].append('test-user')
            if not errors:
                shutil.rmtree(home)
                report['cleanup'].append('test-home')
        except BaseException as exc:
            errors.append('test-identity: ' + str(exc))
        if not completed or errors:
            report['status'] = 'failed'
        if errors:
            report['cleanup_errors'] = errors
            report['retained_home'] = str(home)
        result.write_text(json.dumps(report, ensure_ascii=False) + '\n')
        result.chmod(0o600)
        owner = result.parent.stat()
        os.chown(result, owner.st_uid, owner.st_gid)
        if errors:
            raise RuntimeError('Native test cleanup failed: ' + '; '.join(errors))


def lifecycle():
    from maa import __version__
    from maa.im.state import State
    from maa.im.service import Controller
    from maa.service import privileged
    identity = pwd.getpwuid(os.getuid())
    assert identity.pw_name.startswith('maa-im-test-') and Path(identity.pw_dir) == Path.home(), 'Lifecycle worker requires its isolated test identity'
    assert Path('/dev/lxd/sock').exists(), 'Run inside an owned disposable mas container'
    archive = Path.home() / '.local/share/my-ai-agent/maa.pyz'
    store = State()
    controller = Controller(store)
    assert not store.config()['connections'], 'IM native tests require no existing accounts'
    assert not controller.check(), 'IM native tests require an uninstalled connector module'
    report = {'version': __version__, 'uid': os.getuid(), 'kind': 'native connector lifecycle, no official accounts',
              'product_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'checks': []}
    def command(*args):
        value = subprocess.run([sys.executable, str(archive), 'im', *args], text=True, capture_output=True, timeout=60)
        assert value.returncode == 0, value.stdout + value.stderr
        return json.loads(value.stdout)
    def check(name, action):
        detail = action()
        report['checks'].append({'name': name, 'status': 'passed', 'detail': detail})
        print('✓ ' + name, flush=True)
        return detail
    try:
        check('im-native-install', lambda: command('install'))
        def unit():
            value = controller.path.read_text()
            assert str(controller.executable) in value
            assert 'maa.pyz' not in value and 'codex' not in value
            assert controller.executable.exists()
            assert not controller.enabled() and not controller.active()
            return {'independent_runtime': True, 'initially_closed': True, 'unit': controller.unit}
        check('im-native-independent-unit', unit)
        def independent():
            # Empty supervisor makes no network requests, but is the unmodified
            # product runtime under the real system service.
            privileged(['systemctl', 'start', controller.unit])
            detached = archive.with_suffix('.detached')
            archive.rename(detached)
            try:
                time.sleep(.7)
                assert controller.active()
                assert store.path('supervisor.json').exists()
            finally:
                detached.rename(archive)
            return {'manager_archive_absent': True, 'empty_runtime_active': True, 'network_requests': 0}
        check('im-native-manager-independent', independent)
        check('im-native-close-all', lambda: command('off'))
        assert not controller.active() and not controller.enabled()
        with tempfile.TemporaryDirectory(prefix='maa-im-native-') as folder:
            token, backup = Path(folder) / 'credential', Path(folder) / 'backup.json'
            token.write_text('FICTIONAL_DISABLED_AGENT_KEY')
            token.chmod(0o600)
            row = check('im-native-disabled-account', lambda: command('add', 'whatsapp', '--name', 'native fixture', '--token-file', str(token)))
            assert not row['enabled'] and 'token' not in row
            check('im-native-private-export', lambda: command('export', str(backup)))
            assert backup.stat().st_mode & 0o777 == 0o600
            check('im-native-delete', lambda: command('delete', row['id'], '--yes'))
            check('im-native-import-closed', lambda: command('import', str(backup)))
            restored = command('status')['connections']
            assert len(restored) == 1 and not restored[0]['enabled']
            assert 'FICTIONAL_DISABLED_AGENT_KEY' not in json.dumps(restored)
        check('im-native-uninstall', lambda: command('uninstall', '--yes'))
        assert not controller.path.exists() and not controller.executable.exists() and not store.root.exists()
        assert subprocess.run(['systemctl', 'is-active', '--quiet', controller.unit]).returncode != 0
        report['status'] = 'passed'
    finally:
        if store.root.exists() and controller.check():
            command('uninstall', '--yes')
        report['finished'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        path = Path.home() / 'worker-result.json'
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    return report


if __name__ == '__main__':
    if sys.argv[1:2] == ['--isolate']:
        isolate(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        sys.path.insert(0, str(Path.home() / '.local/share/my-ai-agent/maa.pyz'))
        lifecycle() if sys.argv[1:] == ['--worker'] else run()
