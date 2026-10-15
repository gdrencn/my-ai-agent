"""Native tester orchestration without host users, services or credentials."""
from contextlib import ExitStack
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from maa_testing import im_native
except ImportError:
    spec = importlib.util.spec_from_file_location('maa_im_native_test', Path(__file__).resolve().parents[1] / 'test/im_native.py')
    im_native = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = im_native
    spec.loader.exec_module(im_native)


class NativeIsolation(unittest.TestCase):
    def test_parent_uses_product_copy_and_never_opens_installed_accounts(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            product = home / 'paired-product.pyz'
            product.write_bytes(b'paired fixture')
            account = home / '.local/state/my-ai-agent-im/connections.json'
            account.parent.mkdir(parents=True)
            account.write_bytes(b'existing credential fixture; must remain untouched')
            calls = []

            def privileged(args, **kwargs):
                calls.append(args)
                self.assertEqual(Path(args[-2]), product)
                Path(args[-1]).write_text(json.dumps({'status': 'passed', 'test_uid': 999,
                                                     'checks': [{'name': 'lifecycle', 'status': 'passed'}]}))
                return SimpleNamespace(stdout='native fixture passed\n')

            with patch('pathlib.Path.home', return_value=home), patch('maa.install.require_container') as guard, \
                    patch('maa.service.privileged', side_effect=privileged), \
                    patch('maa.im.state.State', side_effect=AssertionError('Installed state accessed')), \
                    patch('sys.stdout', new_callable=io.StringIO):
                report = im_native.run(product)
            guard.assert_called_once()
            self.assertEqual(len(calls), 1)
            self.assertEqual(report['status'], 'passed')
            self.assertEqual(account.read_bytes(), b'existing credential fixture; must remain untouched')
            self.assertEqual(product.read_bytes(), b'paired fixture')
            receipt = next(home.glob('maa-im-native-*.json'))
            self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)

    def test_failed_worker_and_interrupt_clean_only_owned_identity(self):
        for failure in (subprocess.TimeoutExpired('fixture', 1), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
                base = Path(folder)
                home = base / 'isolated-home'
                home.mkdir()
                (base / 'sudoers').mkdir()
                (base / 'units').mkdir()
                real_path = Path

                def path(value):
                    if str(value) == '/etc/sudoers.d':
                        return base / 'sudoers'
                    if str(value) == '/etc/systemd/system':
                        return base / 'units'
                    return real_path(value)

                product = base / 'product.pyz'
                product.write_bytes(b'fixture product')
                source = base / 'source.py'
                source.write_text('# extracted root helper fixture\n')
                result = base / 'result.json'
                operations = []
                def command(args, **kwargs):
                    operations.append(args)
                    return SimpleNamespace(stdout='not-found\n', returncode=1 if args[:2] == ['systemctl', 'is-active'] else 0)

                class Child:
                    pid = 43210
                    stopped = False
                    def wait(self, **kwargs):
                        if not self.stopped:
                            self.stopped = True
                            raise failure
                        return -15
                    def poll(self):
                        return None

                def start(*args, **kwargs):
                    (base / 'units/maa-connectors-999.service').write_text('# my-ai-agent IM owner uid=999\nfixture')
                    return Child()

                stack.enter_context(patch.object(im_native, 'Path', side_effect=path))
                stack.enter_context(patch.object(im_native, '__file__', str(source)))
                stack.enter_context(patch.object(im_native.tempfile, 'mkdtemp', return_value=str(home)))
                stack.enter_context(patch.object(im_native.os, 'geteuid', return_value=0))
                stack.enter_context(patch.object(im_native.os, 'chown'))
                kill = stack.enter_context(patch.object(im_native.os, 'killpg'))
                stack.enter_context(patch.object(im_native.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=999, pw_gid=999)))
                stack.enter_context(patch.object(im_native.subprocess, 'run', side_effect=command))
                stack.enter_context(patch.object(im_native.subprocess, 'Popen', side_effect=start))
                stack.enter_context(patch.object(im_native.signal, 'signal'))
                stack.enter_context(patch('maa.install.require_container'))
                with self.assertRaises(type(failure)):
                    im_native.isolate(product, result)
                self.assertEqual(json.loads(result.read_text())['status'], 'failed')
                self.assertFalse(home.exists())
                self.assertEqual(list((base / 'sudoers').iterdir()), [])
                self.assertEqual(list((base / 'units').iterdir()), [])
                self.assertIn(('systemctl', 'disable', '--now', 'maa-connectors-999.service'), operations)
                self.assertTrue(any(args[0] == 'userdel' for args in operations))
                kill.assert_called_once()

    def test_helper_refuses_host_before_allocating_identity(self):
        with patch('maa.install.require_container', side_effect=RuntimeError('not mas')), \
                patch.object(im_native.os, 'geteuid', return_value=0), \
                patch.object(im_native.tempfile, 'mkdtemp') as allocate:
            with self.assertRaisesRegex(RuntimeError, 'not mas'):
                im_native.isolate(Path('/fixture/product.pyz'), Path('/fixture/result.json'))
            allocate.assert_not_called()
