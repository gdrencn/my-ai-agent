"""Protect restored functional acceptance and private permission-test boundaries."""
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from maa import codex


def module(name):
    try:
        return importlib.import_module('maa_testing.' + name)
    except ImportError:
        return importlib.import_module('test.' + name)


class NativeCoverage(unittest.TestCase):
    def test_every_original_and_previous_portable_test_remains_discoverable(self):
        inventory = module('coverage')
        expected = set(inventory.PORTABLE_BASELINE + inventory.PORTABLE_0_1_10)
        actual = set()
        for path in sorted({value.split(':')[0] for value in expected}):
            imported = importlib.import_module(path[:-3].replace('/', '.'))
            for name in dir(imported):
                cls = getattr(imported, name)
                if isinstance(cls, type) and issubclass(cls, unittest.TestCase):
                    actual.update(path + ':' + name + '.' + item
                                  for item in unittest.defaultTestLoader.getTestCaseNames(cls))
        self.assertFalse(expected - actual, sorted(expected - actual))
        self.assertEqual(len(inventory.NATIVE_BASELINE), 35)
        self.assertEqual(len(set(inventory.NATIVE_BASELINE + inventory.INSTALLED_ADDITIONS)), 41)

    def test_yolo_enable_disable_and_restore_read_agent_configuration(self):
        native = module('native')
        for initial in ('', 'approval_policy="on-request"\nsandbox_mode="workspace-write"\n'):
            with self.subTest(initial=initial), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root / 'config.toml').write_text(initial)
                calls = []
                def command(*args):
                    self.assertEqual(args[0], 'yolo')
                    codex.yolo(args[1] == 'on')
                    return codex.yolo_state()
                def state():
                    calls.append('config/read')
                    document = codex.parse((root / 'config.toml').read_text())
                    return {key: document.get(key) for key in codex.YOLO}
                with patch.object(native, 'PERMISSIONS', root), patch.object(native, 'command', side_effect=command), \
                     patch('maa.agent_status.configuration', side_effect=state):
                    native.permission_change(True)
                    result = native.permission_change(False)
                self.assertEqual(calls, ['config/read', 'config/read'])
                self.assertFalse(result['managed'])
                self.assertFalse((root / 'maa-yolo-recovery.json').exists())
                self.assertEqual(codex.parse((root / 'config.toml').read_text()), codex.parse(initial))

    def test_agent_state_disagreement_fails_permission_acceptance(self):
        native = module('native')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'config.toml').write_text('approval_policy="never"\nsandbox_mode="danger-full-access"\n')
            with patch.object(native, 'PERMISSIONS', root), \
                 patch('maa.agent_status.configuration', return_value={'approval_policy': 'on-request', 'sandbox_mode': 'workspace-write'}):
                with self.assertRaises(AssertionError):
                    native.permission_state()

    def test_interrupted_native_phase_cleans_private_home_and_preserves_user_permissions(self):
        native, installed = module('native'), module('installed')
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            config = home / 'codex' / 'config.toml'
            config.parent.mkdir()
            config.write_text('approval_policy="on-request"\nsandbox_mode="workspace-write"\n')
            before = config.read_bytes()
            with patch.dict(os.environ, {'CODEX_HOME': str(config.parent)}), patch('pathlib.Path.home', return_value=home), \
                 patch.object(installed, 'run'), patch('maa.backends.binary', return_value='/native/tool'), \
                 patch.object(native, 'main', side_effect=KeyboardInterrupt), patch.object(native, 'command') as command:
                with self.assertRaises(KeyboardInterrupt):
                    native.run()
            command.assert_called_once_with('pause', structured=False)
            self.assertEqual(config.read_bytes(), before)
            self.assertFalse(list(home.glob('.maa-native-permissions-*')))
            report = json.loads(next(home.glob('maa-native-*.json')).read_text())
            self.assertEqual(report['status'], 'failed')
            self.assertIsNone(native.PERMISSIONS)

    def test_missing_original_native_check_cannot_pass(self):
        native, installed = module('native'), module('installed')
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            with patch.dict(os.environ, {'CODEX_HOME': str(home / 'codex')}), patch('pathlib.Path.home', return_value=home), \
                 patch.object(installed, 'run'), patch('maa.backends.binary', return_value='/native/tool'), \
                 patch.object(native, 'main'), patch.object(native, 'command'):
                with self.assertRaisesRegex(AssertionError, 'Missing acceptance coverage'):
                    native.run()
            report = json.loads(next(home.glob('maa-native-*.json')).read_text())
            self.assertEqual(report['status'], 'failed')
