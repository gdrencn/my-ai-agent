import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from maa import codex, backends
from maa.cli import change_pairs
from maa.gguf import metadata
from maa.manager import Manager
from maa.models import hf_input, local_model
from maa.service import fingerprint
from maa.settings import settings, draft_kv
from maa.store import Error, Store, read, write


def gguf(path, mtp=False):
    pairs = [('general.architecture', 'qwen35'), ('qwen35.nextn_predict_layers', int(mtp))]
    def string(value):
        blob = value.encode()
        return struct.pack('<Q', len(blob)) + blob
    data = b'GGUF' + struct.pack('<IQQ', 3, 0, len(pairs))
    for key, value in pairs:
        data += string(key)
        data += struct.pack('<I', 8) + string(value) if isinstance(value, str) else struct.pack('<II', 4, value)
    Path(path).write_bytes(data)


def native_runner():
    try:
        from maa_testing import native
        return native
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location('maa_native_checks', Path(__file__).resolve().parent.parent / 'test/native.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


class FakeController:
    def __init__(self):
        self.active, self.fail, self.stops, self.starts = False, 0, 0, 0
    def ensure(self):
        pass
    def running(self):
        return self.active
    def stop(self):
        self.active = False
        self.stops += 1
    def start(self):
        self.active = True
        self.starts += 1
    def wait(self, target):
        if self.fail:
            self.fail -= 1
            raise Error('Injected load failure')
        return {'context': 8192, 'model': target['model']['key'], 'backend': target['model']['backend'],
                'upstream': 'http://127.0.0.1:8080',
                'base_url': 'http://127.0.0.1:18443/v1', 'fingerprint': fingerprint(target)}


class Core(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'MAA_HOME': str(self.root / 'state'), 'CODEX_HOME': str(self.root / 'codex')})
        self.env.start()
        self.store = Store()
    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()
    def model(self, name, mtp=False):
        path = self.root / (name + '.gguf')
        gguf(path, mtp)
        model = local_model(path)
        self.store.register(model)
        return model

    def test_yolo_restore_existing_and_absent_keys(self):
        codex.home().mkdir()
        original = '# preserve\napproval_policy = "on-request" # policy\n[other]\ntext = """line1\nline2"""\ndate = 2026-10-06\n'
        path = codex.home() / 'config.toml'
        path.write_text(original)
        codex.yolo(True)
        snapshot = (codex.home() / 'maa-yolo-recovery.json').read_bytes()
        codex.yolo(True)
        self.assertEqual(snapshot, (codex.home() / 'maa-yolo-recovery.json').read_bytes())
        document = codex.parse(path.read_text())
        document['other']['new'] = 'external change'
        path.write_text(str(codex.tomlkit.dumps(document)))
        codex.yolo(False)
        restored = codex.parse(path.read_text())
        self.assertEqual(restored['approval_policy'], 'on-request')
        self.assertNotIn('sandbox_mode', restored)
        self.assertEqual(restored['other']['new'], 'external change')
        self.assertEqual(restored['other']['text'], 'line1\nline2')
        self.assertIn('# preserve', path.read_text())
        self.assertFalse((codex.home() / 'maa-yolo-recovery.json').exists())

    def test_yolo_recovery_cross_process(self):
        codex.yolo(True)
        root = str(Path(__file__).resolve().parent.parent)
        code = f'import sys;sys.path.insert(0,{root!r});from maa.codex import yolo;yolo(False)'
        subprocess.run([sys.executable, '-I', '-c', code], check=True)
        self.assertNotIn('approval_policy', codex.parse((codex.home() / 'config.toml').read_text()))

    def test_invalid_toml_is_not_overwritten(self):
        codex.home().mkdir()
        path = codex.home() / 'config.toml'
        path.write_text('broken = [')
        with self.assertRaises(Error):
            codex.yolo(True)
        self.assertEqual(path.read_text(), 'broken = [')

    def test_profile_has_no_global_permissions_or_websearch(self):
        values = settings(mtp_supported=True)
        values['reasoning'] = 'ultra'
        codex.profile({'context': 262144, 'model': 'exact', 'base_url': 'http://localhost:18443/v1'}, values)
        doc = codex.parse(codex.profile_path().read_text())
        self.assertEqual(doc['model_auto_compact_token_limit'], 235929)
        self.assertEqual(doc['model_reasoning_effort'], 'ultra')
        self.assertFalse(set(('approval_policy', 'sandbox_mode', 'web_search')) & set(doc))
        values['reasoning'] = 'default'
        codex.profile({'context': 8192, 'model': 'exact', 'base_url': 'http://localhost:18443/v1'}, values)
        doc = codex.parse(codex.profile_path().read_text())
        self.assertNotIn('model_reasoning_effort', doc)
        self.assertEqual(doc['model_auto_compact_token_limit'], 7372)

    def test_kv_follow_override_and_restore(self):
        v = settings(mtp_supported=True)
        self.assertEqual(draft_kv(v), 'q8_0')
        v = settings(v, {'kv': 'q4_0'}, True)
        self.assertEqual(draft_kv(v), 'q4_0')
        v = settings(v, {'mtp_kv': 'f16', 'kv': 'q8_0'}, True)
        self.assertEqual(draft_kv(v), 'f16')
        v = settings(v, {'mtp_kv': 'follow'}, True)
        self.assertEqual(draft_kv(v), 'q8_0')

    def test_bad_settings_and_unavailable_mtp(self):
        for changes in ({'context': 0}, {'context': True}, {'reserve_mib': -1}, {'keep_alive': 'auto'},
                        {'kv': 'q2'}, {'flash_attention': False}, {'draft_candidates': 4}):
            with self.subTest(changes=changes), self.assertRaises(Error):
                settings(changes=changes)
        self.assertFalse(settings()['mtp'])
        with self.assertRaises(Error):
            settings(changes={'mtp': True})

    def test_hf_exact_file_and_traversal_validation(self):
        hf_input('publisher/repo', 'folder/model-Q4_K_M.gguf')
        for repo, file in [('repo', 'model.gguf'), ('org/repo', '../model.gguf'), ('org/repo', '/model.gguf'),
                           ('org/repo', 'model.safetensors'), ('org/repo', 'folder\\model.gguf')]:
            with self.subTest(repo=repo, file=file), self.assertRaises(Error):
                hf_input(repo, file)

    def test_gguf_mtp_metadata_and_corruption(self):
        model = self.model('mtp', True)
        self.assertTrue(model['mtp_supported'])
        Path(model['path']).write_bytes(b'GGUF')
        with self.assertRaises(Error):
            metadata(model['path'])

    def test_switch_syncs_actual_context_and_persists_per_model(self):
        first, second = self.model('one'), self.model('two')
        ctrl = FakeController()
        manager = Manager(self.store, ctrl)
        manager.select(first['key'], {'context': 262144, 'kv': 'q4_0'})
        self.assertEqual(codex.parse(codex.profile_path().read_text())['model_context_window'], 8192)
        manager.select(second['key'], {'context': 16384})
        manager.select(first['key'])
        self.assertEqual(self.store.selected()['settings']['kv'], 'q4_0')
        self.assertEqual(self.store.selected(), self.store.target())

    def test_failed_switch_restores_service_selection_and_profile(self):
        first, second = self.model('one'), self.model('two')
        ctrl = FakeController()
        manager = Manager(self.store, ctrl)
        manager.select(first['key'])
        old = codex.profile_path().read_bytes()
        ctrl.fail = 1
        with self.assertRaisesRegex(Error, 'Previous service restored'):
            manager.select(second['key'])
        self.assertEqual(self.store.selected()['model']['key'], first['key'])
        self.assertEqual(self.store.target(), self.store.selected())
        self.assertEqual(codex.profile_path().read_bytes(), old)
        self.assertTrue(ctrl.active)
        profile = codex.parse(old.decode())
        catalog = read(profile['model_catalog_json'])
        self.assertEqual(catalog['models'][0]['slug'], first['key'])
        self.assertEqual(catalog['models'][0]['display_name'], first['name'])
        with patch.object(manager, 'save_config', side_effect=Error('Commit failed after catalog publication')):
            with self.assertRaisesRegex(Error, 'Previous service restored'):
                manager.select(second['key'])
        self.assertEqual(codex.profile_path().read_bytes(), old)
        self.assertEqual(read(profile['model_catalog_json']), catalog)

    def test_failed_first_switch_restores_empty_stopped_state(self):
        model = self.model('one')
        ctrl = FakeController()
        ctrl.fail = 1
        with self.assertRaises(Error):
            Manager(self.store, ctrl).select(model['key'])
        self.assertIsNone(self.store.selected())
        self.assertIsNone(self.store.target())
        self.assertFalse(codex.profile_path().exists())
        self.assertFalse(ctrl.active)

    def test_pause_preserves_boot_target_and_start_restores(self):
        model = self.model('one')
        manager = Manager(self.store, FakeController())
        manager.select(model['key'])
        target = self.store.target()
        manager.pause()
        self.assertFalse(manager.controller.running())
        self.assertEqual(self.store.target(), target)
        manager.start()
        self.assertTrue(manager.controller.running())

    def test_changed_registered_file_refused_before_service_stop(self):
        model = self.model('one')
        manager = Manager(self.store, FakeController())
        manager.select(model['key'])
        before = manager.controller.stops
        Path(model['path']).write_bytes(b'different')
        with self.assertRaises(Error):
            manager.select(model['key'])
        self.assertEqual(manager.controller.stops, before)

    def test_cli_integer_and_boolean_types(self):
        self.assertEqual(change_pairs(['context=8192', 'fit=off']), {'context': 8192, 'fit': False})
        with self.assertRaises(Error):
            change_pairs(['fit=maybe'])

    def test_local_entry_rejects_compact_and_long_routing_overrides(self):
        manager = Manager(self.store, FakeController())
        for args in (['-mother'], ['-pother'], ['--model=other'], ['-cmodel="other"'],
                     ['--config=model_provider="other"'], ['-c', 'profiles.other.model="other"'],
                     ['--remote=unix:///other.sock']):
            with self.subTest(args=args), self.assertRaisesRegex(Error, 'managed by maa|changed through maa'):
                manager.local_command(args)

    def test_catalog_tracks_exact_alias_context_and_preserves_base_config(self):
        codex.home().mkdir()
        base = codex.home() / 'config.toml'
        base.write_text('model = "ordinary-cloud-model"\n')
        values = settings()
        runtime = {'model': 'maa-exact:latest', 'display_name': 'qwen:latest',
                   'context': 4096, 'base_url': 'http://localhost:18443/v1'}
        codex.profile(runtime, values)
        first = codex.parse(codex.profile_path().read_text())
        metadata = read(first['model_catalog_json'])['models']
        self.assertEqual(len(metadata), 1)
        self.assertEqual(metadata[0]['slug'], runtime['model'])
        self.assertEqual(metadata[0]['display_name'], 'qwen:latest')
        self.assertEqual(metadata[0]['context_window'], 4096)
        self.assertEqual(metadata[0]['input_modalities'], ['text'])
        self.assertFalse(metadata[0]['supports_search_tool'])
        runtime['context'] = 8192
        codex.profile(runtime, values)
        second = codex.parse(codex.profile_path().read_text())
        self.assertNotEqual(first['model_catalog_json'], second['model_catalog_json'])
        self.assertEqual(read(first['model_catalog_json'])['models'], metadata)
        self.assertEqual(base.read_text(), 'model = "ordinary-cloud-model"\n')

    def test_ollama_resident_entry_never_creates_or_loads(self):
        target = {'model': {'name': 'native:latest', 'digest': 'original'}, 'settings': settings()}
        runtime = {'model': 'maa-alias:latest', 'native_digest': 'adapted'}
        calls = []
        def api(url, value=None, **kwargs):
            calls.append((url, value))
            if url.endswith('/api/tags'):
                return {'models': [{'name': 'native:latest', 'digest': 'original'},
                                   {'name': runtime['model'], 'digest': 'adapted'}]}
            if url.endswith('/api/ps'):
                return {'models': [{'name': runtime['model'], 'context_length': 4096, 'digest': 'adapted'}]}
            raise AssertionError('Unexpected mutation: ' + url)
        with patch('maa.backends.request', side_effect=api):
            observed = backends.ollama_current(target, runtime)
        self.assertEqual(observed['context'], 4096)
        self.assertEqual(len(calls), 2)

    def test_ollama_expired_entry_wakes_without_creating(self):
        target = {'model': {'name': 'native:latest', 'digest': 'original'}, 'settings': settings()}
        runtime = {'model': 'maa-alias:latest', 'native_digest': 'adapted'}
        calls, resident = [], False
        def api(url, value=None, **kwargs):
            nonlocal resident
            calls.append((url, value))
            if url.endswith('/api/tags'):
                return {'models': [{'name': 'native:latest', 'digest': 'original'},
                                   {'name': runtime['model'], 'digest': 'adapted'}]}
            if url.endswith('/api/ps'):
                return {'models': [{'name': runtime['model'], 'context_length': 4096}] if resident else []}
            if url.endswith('/api/generate'):
                resident = True
                return {}
            raise AssertionError('Unexpected mutation: ' + url)
        with patch('maa.backends.request', side_effect=api):
            backends.ollama_current(target, runtime)
        mutations = [(url, body) for url, body in calls if body is not None]
        self.assertEqual(len(mutations), 1)
        self.assertEqual(mutations[0][1]['keep_alive'], '5m')

    def test_ollama_modified_alias_refused_before_wake(self):
        target = {'model': {'name': 'native:latest', 'digest': 'original'}, 'settings': settings()}
        with patch('maa.backends.request', return_value={'models': [
                {'name': 'native:latest', 'digest': 'original'}, {'name': 'alias', 'digest': 'changed'}]}) as api:
            with self.assertRaisesRegex(Error, 'configuration changed'):
                backends.ollama_current(target, {'model': 'alias', 'native_digest': 'accepted'})
            self.assertEqual(api.call_count, 1)

    def test_local_launch_explicit_embedded_and_pause_refusal(self):
        model = self.model('one')
        manager = Manager(self.store, FakeController())
        manager.select(model['key'])
        observed = {'context': 4096, 'upstream': 'http://localhost:8080', 'resources': {'sleeping': False}}
        with patch('maa.manager.llama_observe', return_value=observed), patch('maa.manager.request'), \
             patch('maa.codex.executable', return_value='/test/codex'), patch('maa.manager.subprocess.call', return_value=0) as launch:
            self.assertEqual(manager.local_command(['exec', 'hello']), 0)
            self.assertEqual(launch.call_args.args[0], ['/test/codex', '--no-daemon', '--profile', 'maa-local', 'exec', 'hello'])
            manager.pause()
            with self.assertRaisesRegex(Error, 'stopped'):
                manager.local_command([])
            self.assertEqual(launch.call_count, 1)

    def test_redirected_progress_keeps_json_clean_without_duplicate_ticks(self):
        from maa.output import operation, stage
        err, out = io.StringIO(), io.StringIO()
        with patch('sys.stderr', err), patch('sys.stdout', out):
            with operation('测试操作') as progress:
                stage('读取配置')
                with operation('嵌套操作'):
                    stage('等待加载')
                self.assertIsNone(progress.thread)
            print(json.dumps({'ok': True}))
        self.assertEqual(json.loads(out.getvalue()), {'ok': True})
        self.assertEqual(len(err.getvalue().splitlines()), 2)
        self.assertNotIn('\x1b', err.getvalue())

    def test_sleeping_llama_is_woken_once_and_context_is_synchronized(self):
        model = self.model('sleeping')
        manager = Manager(self.store, FakeController())
        manager.select(model['key'])
        sleeping = {'context': 8192, 'resources': {'sleeping': True}}
        awake = {'context': 4096, 'resources': {'sleeping': False}}
        with patch('maa.manager.llama_observe', side_effect=[sleeping, awake]), \
             patch('maa.manager.request') as api, patch('maa.codex.executable', return_value='/test/codex'), \
             patch('maa.manager.subprocess.call', return_value=0):
            manager.local_command([])
        self.assertEqual(api.call_count, 2)
        self.assertEqual(api.call_args_list[0].args[1]['max_tokens'], 1)
        self.assertEqual(codex.parse(codex.profile_path().read_text())['model_context_window'], 4096)

    def test_native_bad_fixture_is_removed_after_interrupted_check(self):
        native = native_runner()
        user_model = self.model('user-kept')
        def register(*args, **kwargs):
            model = local_model(args[-1])
            self.store.register(model)
            return model
        key, path = None, None
        with patch.object(native, 'command', side_effect=register), patch.object(native, 'REPORT', {'cleanup': []}):
            with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                with native.invalid_fixture() as bad:
                    key, path = bad['key'], bad['path']
                    write(self.store.path('configs') / (key + '.json'), {'context': 1})
                    raise RuntimeError('interrupted')
        self.assertNotIn(key, self.store.models())
        self.assertIn(user_model['key'], self.store.models())
        self.assertFalse(Path(path).exists())
        self.assertFalse((self.store.path('configs') / (key + '.json')).exists())

    def test_legacy_cleanup_recognizes_exact_fixture_and_keeps_real_gguf(self):
        native = native_runner()
        path = self.store.path('bad-native.gguf')
        path.write_bytes(b'GGUF' + struct.pack('<IQQ', 3, 0, 0))
        legacy = local_model(path)
        self.store.register(legacy)
        with patch.object(native, 'REPORT', {'cleanup': []}):
            native.cleanup_legacy_fixture()
        self.assertFalse(path.exists())
        self.assertNotIn(legacy['key'], self.store.models())
        gguf(path)
        real = local_model(path)
        self.store.register(real)
        with patch.object(native, 'REPORT', {'cleanup': []}):
            native.cleanup_legacy_fixture()
        self.assertTrue(path.exists())
        self.assertIn(real['key'], self.store.models())

    def test_first_menu_selection_cancel_and_preload_configuration(self):
        from maa import menu, ui
        model = self.model('first')
        manager = Manager(self.store, FakeController())
        with patch('maa.ui.edit_settings', side_effect=menu.Cancelled), self.assertRaises(menu.Cancelled):
            ui.select_model(None, manager, model['key'])
        self.assertIsNone(self.store.selected())
        self.assertEqual(manager.controller.starts, 0)
        configured = settings(changes={'context': 4096, 'kv': 'q4_0'})
        with patch('maa.ui.edit_settings', return_value=configured) as editor:
            ui.select_model(None, manager, model['key'])
            editor.assert_called_once()
        self.assertEqual(self.store.selected()['settings']['context'], 4096)
        with patch('maa.ui.edit_settings', side_effect=AssertionError('Saved config should be reused')):
            ui.select_model(None, manager, model['key'])
        self.assertEqual(self.store.selected()['settings']['kv'], 'q4_0')

    def test_boot_ignores_crashed_uncommitted_target(self):
        from maa.service import boot_target
        old, candidate = {'name': 'accepted'}, {'name': 'unaccepted'}
        write(self.store.path('selected.json'), old)
        write(self.store.path('target.json'), candidate)
        self.assertEqual(boot_target(self.store), old)
        pending = {'pid': os.getpid(), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                   'process_start': Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]}
        write(self.store.path('pending.json'), pending)
        self.assertEqual(boot_target(self.store), candidate)
        pending['process_start'] = 'wrong-recycled-pid'
        write(self.store.path('pending.json'), pending)
        self.assertEqual(boot_target(self.store), old)


if __name__ == '__main__':
    unittest.main()
