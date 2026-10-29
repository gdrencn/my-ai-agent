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
