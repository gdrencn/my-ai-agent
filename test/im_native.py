"""Installed connector lifecycle inside a disposable mas container.

No official account credentials are used. Protocol send/receive fixtures run in
the paired portable suite; this file verifies actual units, ownership and local
cleanup with an empty runtime and a disabled, fictional WhatsApp credential.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def run():
    from maa import __version__
    from maa.im.state import State
    from maa.im.service import Controller
    from maa.service import privileged
    assert Path('/dev/lxd/sock').exists(), 'Run inside an owned disposable mas container'
    maa = str(Path.home() / '.local/bin/maa')
    archive = Path.home() / '.local/share/my-ai-agent/maa.pyz'
    store = State()
    controller = Controller(store)
    assert not store.config()['connections'], 'IM native tests require no existing accounts'
    assert not controller.check(), 'IM native tests require an uninstalled connector module'
    report = {'version': __version__, 'uid': os.getuid(), 'kind': 'native connector lifecycle, no official accounts',
              'product_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'checks': []}
    def command(*args):
        value = subprocess.run([maa, 'im', *args], text=True, capture_output=True, timeout=60)
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
        path = Path.home() / ('maa-im-native-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.json')
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        print('报告：' + str(path), flush=True)
    return report


if __name__ == '__main__':
    sys.path.insert(0, str(Path.home() / '.local/share/my-ai-agent/maa.pyz'))
    run()
