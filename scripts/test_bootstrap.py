"""Delivery-only checks; keep the approved product and paired tester unchanged."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
import tempfile
import subprocess
import os
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from maa import __version__
spec = importlib.util.spec_from_file_location('maa_bootstrap', ROOT / 'bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def item(tag='v0.1.9', prerelease=True, draft=False):
    return {'tag_name': tag, 'prerelease': prerelease, 'draft': draft, 'assets': []}


class Delivery(unittest.TestCase):
    def test_generated_shell_prepares_bootstrap_tools_and_forwards_overrides(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);trace=root/'trace'
            python=root/'python3'
            python.write_text('#!/bin/sh\n[ "$1" != -c ] || exit 0\nprintf "%s\\n" "$@" >> "$MAA_BOOT_TRACE"\n')
            python.chmod(0o755)
            curl=root/'curl-stub'
            curl.write_text('#!/bin/sh\nwhile [ "$#" -gt 0 ]; do if [ "$1" = -o ]; then shift; printf "pass\\n" > "$1"; fi; shift; done\n')
            curl.chmod(0o755)
            (root/'id').write_text('#!/bin/sh\nprintf "0\\n"\n');(root/'id').chmod(0o755)
            (root/'apt-get').write_text('#!/bin/sh\nprintf "APT %s\\n" "$*" >> "$MAA_BOOT_TRACE"\n[ "$1" != install ] || /bin/cp "$MAA_BOOT_CURL" "${MAA_BOOT_TRACE%/*}/curl"\n')
            (root/'apt-get').chmod(0o755)
            for name in ('mktemp','rm'):(root/name).symlink_to('/usr/bin/'+name)
            result=subprocess.run(['/bin/sh',str(ROOT/'test/install.sh'),'--components','none','--version','0.1.9'],
                env={'PATH':str(root),'MAA_BOOT_TRACE':str(trace),'MAA_BOOT_CURL':str(curl)},capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            value=trace.read_text()
            self.assertIn('APT update',value)
            self.assertIn('APT install -y curl ca-certificates',value)
            self.assertIn('--version\n' + __version__,value)
            self.assertTrue(value.rstrip().endswith('--version\n0.1.9'),value)

    def test_numeric_test_discovery_excludes_other_channels_and_drafts(self):
        rows = [item('v0.1.8'), item('v0.1.10'), item('v0.2.0', draft=True),
                item('stable/0.9.0', False), item('v1.0.0-beta'), item('v0.3.0', False)]
        with patch.object(bootstrap, 'fetch', return_value=json.dumps(rows).encode()):
            self.assertEqual(bootstrap.release()['tag_name'], 'v0.1.10')

    def test_test_discovery_reads_later_pages(self):
        rows = [item('stable/0.1.9', False)] * 100
        with patch.object(bootstrap, 'fetch', side_effect=[json.dumps(rows).encode(),
                          json.dumps([item('v0.1.9')]).encode()]) as fetch:
            self.assertEqual(bootstrap.release()['tag_name'], 'v0.1.9')
        self.assertIn('page=2', fetch.call_args.args[0])

    def test_stable_uses_latest_official_release(self):
        with patch.object(bootstrap, 'fetch', return_value=json.dumps(item('stable/0.1.9', False)).encode()) as fetch:
            self.assertEqual(bootstrap.release(channel='stable')['tag_name'], 'stable/0.1.9')
        self.assertTrue(fetch.call_args.args[0].endswith('/latest'))

    def test_exact_version_uses_its_channel_tag(self):
        for channel, tag, ending in [('test', 'v0.1.9', '/tags/v0.1.9'),
                                     ('stable', 'stable/0.1.9', '/tags/stable%2F0.1.9')]:
            with self.subTest(channel=channel), patch.object(bootstrap, 'fetch', return_value=json.dumps(
                    item(tag, channel == 'test')).encode()) as fetch:
                self.assertEqual(bootstrap.release('v0.1.9', channel)['tag_name'], tag)
                self.assertTrue(fetch.call_args.args[0].endswith(ending))

    def test_wrong_channel_version_and_draft_are_refused(self):
        cases = [('stable', None, item()), ('stable', '0.1.9', item('stable/0.1.9', False, True)),
                 ('stable', '0.1.9', item('stable/0.1.9')), ('test', '0.1.9', item(prerelease=False)),
                 ('test', '0.1.9', item('v0.1.8'))]
        for channel, version, row in cases:
            with self.subTest(channel=channel, row=row), patch.object(bootstrap, 'fetch', return_value=json.dumps(row).encode()):
                with self.assertRaises(ValueError):
                    bootstrap.release(version, channel)

    def test_invalid_version_and_empty_test_channel(self):
        with patch.object(bootstrap, 'fetch', return_value=b'[]') as fetch:
            with self.assertRaises(ValueError):
                bootstrap.release('../other')
            fetch.assert_not_called()
            with self.assertRaises(ValueError):
                bootstrap.release()

    def fixture(self, channel, info=None, corrupt=None, version='0.1.9'):
        row = item(('v' if channel == 'test' else 'stable/') + version, channel == 'test')
        payloads = {'maa.pyz': b'approved-product', 'maa-test.pyz': b'approved-paired-tester',
                    'VERSION.json': json.dumps(info or {'version': version, 'channel': channel}).encode()}
        payloads['SHA256SUMS'] = ''.join(hashlib.sha256(blob).hexdigest() + '  ' + name + '\n'
                                        for name, blob in payloads.items()).encode()
        if corrupt:
            payloads[corrupt] += b'corrupt'
        row['assets'] = [{'name': name, 'browser_download_url': 'fixture://' + name} for name in payloads]
        def fetch(url):
            if url.startswith('fixture://'):
                return payloads[url.removeprefix('fixture://')]
            return json.dumps(row if channel == 'stable' else [row]).encode()
        return fetch

    def invoke(self, channel, fetch, paired=True):
        exists = Path.exists
        seen = []
        def command(args, **kwargs):
            seen.append({'name': Path(args[1]).name, 'blob': Path(args[1]).read_bytes(), 'args': args[2:]})
            self.assertTrue(kwargs['check'])
        with patch.object(bootstrap, 'fetch', side_effect=fetch), patch.object(
                bootstrap.subprocess, 'run', side_effect=command):
            bootstrap.run(['--channel', channel, '--components', 'none'] + (['--test'] if paired else []))
        return seen

    def test_verified_stable_and_test_keep_the_same_program_pair(self):
        for channel in ('stable', 'test'):
            with self.subTest(channel=channel):
                seen = self.invoke(channel, self.fixture(channel))
                self.assertEqual([row['blob'] for row in seen], [b'approved-product', b'approved-paired-tester'])
                self.assertEqual(seen[0]['args'], ['_install', '--components', 'none'])
                self.assertEqual(seen[1]['args'][0], '--native')
                self.assertEqual(seen[1]['args'][1], '--product')

    def test_unpaired_install_does_not_run_tester(self):
        seen = self.invoke('stable', self.fixture('stable'), paired=False)
        self.assertEqual([row['name'] for row in seen], ['maa.pyz'])

    def test_corrupt_payload_is_rejected_before_install(self):
        for name in ('maa.pyz', 'maa-test.pyz', 'VERSION.json'):
            with self.subTest(name=name), patch.object(bootstrap.subprocess, 'run') as command:
                # The inner patch must not hide the outer failure assertion.
                with patch.object(bootstrap, 'fetch', side_effect=self.fixture('stable', corrupt=name)), patch.object(
                        bootstrap.Path, 'exists', return_value=True):
                    with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
                        bootstrap.run(['--channel', 'stable', '--test'])
                command.assert_not_called()

    def test_metadata_pairing_mismatch_is_rejected_before_install(self):
        for info in ({'version': '0.1.8', 'channel': 'stable'}, {'version': '0.1.9', 'channel': 'test'}):
            with self.subTest(info=info), patch.object(bootstrap.subprocess, 'run') as command, patch.object(
                    bootstrap, 'fetch', side_effect=self.fixture('stable', info=info)), patch.object(
                    bootstrap.Path, 'exists', return_value=True):
                with self.assertRaisesRegex(ValueError, 'pairing mismatch'):
                    bootstrap.run(['--channel', 'stable'])
                command.assert_not_called()

    def test_new_release_forwards_language_only_after_asset_verification(self):
        with patch.object(bootstrap, 'fetch', side_effect=self.fixture('test', version='0.1.10')), \
                patch.object(bootstrap.Path, 'exists', return_value=True), patch.object(bootstrap.subprocess, 'run') as command:
            bootstrap.run(['--components', 'none', '--language', 'en_us'])
        self.assertEqual(command.call_count, 1)
        self.assertEqual(command.call_args.args[0][-2:], ['--language', 'en_us'])

    def test_frozen_release_does_not_receive_unsupported_language_flag(self):
        with patch.object(bootstrap, 'fetch', side_effect=self.fixture('stable')), \
                patch.object(bootstrap.Path, 'exists', return_value=True), patch.object(bootstrap.subprocess, 'run') as command:
            with self.assertRaisesRegex(ValueError, 'does not support --language'):
                bootstrap.run(['--channel', 'stable', '--components', 'none', '--language', 'en_us'])
        command.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2, buffer=True)
