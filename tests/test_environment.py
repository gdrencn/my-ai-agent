import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from maa import environment
from maa.store import Error


class Environment(unittest.TestCase):
    def test_capabilities_not_container_identity(self):
        with patch.object(environment.sys, 'platform', 'linux'), \
             patch.object(environment.shutil, 'which', return_value='/bin/systemctl'), \
             patch.object(Path, 'is_dir', return_value=True), \
             patch.object(environment.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='255\n', stderr='')) as call:
            environment.require_systemd()
        self.assertEqual(call.call_args.args[0], ['systemctl', 'show', '--property=Version', '--value'])

    def test_missing_or_unreachable_systemd_is_explicit(self):
        with patch.object(environment.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(Error, 'systemd'): environment.require_systemd()
        with patch.object(environment.shutil, 'which', return_value='/bin/systemctl'), \
             patch.object(Path, 'is_dir', return_value=True), \
             patch.object(environment.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='', stderr='bus unavailable')):
            with self.assertRaisesRegex(Error, 'bus unavailable'): environment.require_systemd()

    def test_dependencies_install_only_missing_and_verify_again(self):
        for uid in (0, 1001):
            with self.subTest(uid=uid), patch.object(environment, 'require_systemd'), \
                 patch.object(environment.os, 'geteuid', return_value=uid), \
                 patch.object(environment.shutil, 'which', side_effect=lambda x: '/bin/'+x if x in ('sudo','apt-get') else None), \
                 patch.object(environment, 'missing_dependencies', side_effect=[['curl'], []]), \
                 patch('maa.service.privileged') as execute:
                environment.prepare_dependencies()
                self.assertEqual([c.args[0] for c in execute.call_args_list],
                                 [['apt-get','update'], ['apt-get','install','-y','curl']])

    def test_complete_environment_does_not_mutate_packages(self):
        with patch.object(environment, 'require_systemd'), patch.object(environment, 'missing_dependencies', return_value=[]), \
             patch('maa.service.privileged') as execute:
            environment.prepare_dependencies()
            execute.assert_not_called()

    def test_package_failure_and_remaining_dependencies_are_not_success(self):
        with patch.object(environment, 'require_systemd'), patch.object(environment.os, 'geteuid', return_value=0), \
             patch.object(environment, 'missing_dependencies', return_value=['curl']), \
             patch.object(environment, 'package_commands', return_value=[['tool','install','curl']]), \
             patch('maa.service.privileged'):
            with self.assertRaisesRegex(Error, 'remain unavailable'): environment.prepare_dependencies()

    def test_supported_package_managers_do_not_upgrade_system(self):
        for tool in ('apt-get','dnf','yum','zypper','pacman'):
            with self.subTest(tool=tool), patch.object(environment.shutil, 'which', side_effect=lambda x: x if x==tool else None):
                commands=environment.package_commands(['curl'])
                self.assertIn('curl', commands[-1])
                self.assertNotIn('-Syu', commands[-1])
                python = environment.package_commands(['python3'])[-1]
                self.assertIn('python' if tool == 'pacman' else 'python3', python)
        with patch.object(environment.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(Error, 'curl'): environment.package_commands(['curl'])

    def test_missing_privilege_is_not_silently_ignored(self):
        with patch.object(environment, 'require_systemd'), patch.object(environment, 'missing_dependencies', return_value=['curl']), \
             patch.object(environment.os, 'geteuid', return_value=1001), patch.object(environment.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(Error, 'root or sudo'): environment.prepare_dependencies()

    def trust_fixture(self):
        import tempfile
        from tests.certificates import CA_HASH, CA_PEM
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        directory = root / 'certs'
        directory.mkdir()
        pem = root / 'ca.pem'
        pem.write_text(CA_PEM)
        (directory / (CA_HASH + '.0')).symlink_to(pem)
        env = patch.dict(os.environ, {'SSL_CERT_FILE': str(root / 'absent.pem'), 'SSL_CERT_DIR': str(directory)})
        env.start()
        self.addCleanup(env.stop)
        return root, directory, pem

    def test_lazy_hashed_ca_directory_is_available_without_loading_or_installing(self):
        import ssl
        root, directory, pem = self.trust_fixture()
        self.assertEqual(ssl.create_default_context().get_ca_certs(), [])
        with patch.object(environment.shutil, 'which', return_value='/native/tool'), \
             patch.object(environment, 'require_systemd'), patch('maa.service.privileged') as install:
            self.assertEqual(environment.missing_dependencies('all'), [])
            environment.prepare_dependencies('all')
        install.assert_not_called()
        context = ssl.create_default_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(context.get_ca_certs(), [])

    def test_loaded_ca_file_remains_supported(self):
        root, directory, pem = self.trust_fixture()
        with patch.dict(os.environ, {'SSL_CERT_FILE': str(pem), 'SSL_CERT_DIR': str(root / 'missing')}), \
             patch.object(Path, 'iterdir', side_effect=AssertionError('A loaded CA file needs no directory scan')):
            self.assertTrue(environment.ca_available())

    def test_empty_missing_invalid_unindexed_and_leaf_stores_are_missing(self):
        from tests.certificates import CA_HASH, CA_PEM, LEAF_HASH, LEAF_PEM
        root, directory, pem = self.trust_fixture()
        for item in directory.iterdir():
            item.unlink()
        for name, contents in (('empty', None), ('unindexed.pem', CA_PEM),
                               (CA_HASH + '.r0', CA_PEM), (CA_HASH + '.0', 'invalid PEM'),
                               (LEAF_HASH + '.0', LEAF_PEM)):
            with self.subTest(name=name):
                path = directory / name
                if contents is not None:
                    path.write_text(contents)
                self.assertFalse(environment.ca_available())
                if path.exists():
                    path.unlink()
        with patch.dict(os.environ, {'SSL_CERT_DIR': str(root / 'missing')}):
            self.assertFalse(environment.ca_available())
        with patch.object(environment.shutil, 'which', return_value='/native/tool'):
            self.assertEqual(environment.missing_dependencies(), ['ca-certificates'])

    def test_multiple_ca_directories_and_native_default_path_are_respected(self):
        import ssl
        root, directory, pem = self.trust_fixture()
        with patch.dict(os.environ, {'SSL_CERT_DIR': str(root / 'missing') + os.pathsep + str(directory)}):
            self.assertIsNone(ssl.get_default_verify_paths().capath)
            self.assertTrue(environment.ca_available())
        with patch.dict(os.environ):
            os.environ.pop('SSL_CERT_DIR', None)
            defaults = ssl.get_default_verify_paths()._replace(openssl_capath=str(directory))
            with patch.object(environment.ssl, 'create_default_context', return_value=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)), \
                 patch.object(environment.ssl, 'get_default_verify_paths', return_value=defaults):
                self.assertTrue(environment.ca_available())

    def test_bad_entries_do_not_hide_a_valid_native_ca(self):
        root, directory, pem = self.trust_fixture()
        (directory / '00000000.0').write_text('not a certificate')
        (directory / '00000001.0').symlink_to(root / 'absent.pem')
        self.assertTrue(environment.ca_available())
        with patch.object(Path, 'iterdir', side_effect=PermissionError('not readable')):
            self.assertFalse(environment.ca_available())
