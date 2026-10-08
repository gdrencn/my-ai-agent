"""Delivery-only checks; keep the approved product and paired tester unchanged."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('maa_bootstrap', ROOT / 'bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def item(tag='v0.1.9', prerelease=True, draft=False):
    return {'tag_name': tag, 'prerelease': prerelease, 'draft': draft, 'assets': []}


class Delivery(unittest.TestCase):
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

    def fixture(self, channel, info=None, corrupt=None):
        row = item('v0.1.9' if channel == 'test' else 'stable/0.1.9', channel == 'test')
        payloads = {'maa.pyz': b'approved-product', 'maa-test.pyz': b'approved-paired-tester',
                    'VERSION.json': json.dumps(info or {'version': '0.1.9', 'channel': channel}).encode()}
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
                bootstrap.Path, 'exists', lambda path: str(path) == '/dev/lxd/sock' or exists(path)), patch.object(
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


if __name__ == '__main__':
    unittest.main(verbosity=2, buffer=True)
