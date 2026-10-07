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
from maa.models import hf_input, local_model, verify_file, hf_download
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
        self.valid = False
    def owned(self, backend):
        return True
    def configuration_matches(self, target):
        return self.valid
    def ensure(self):
        pass
    def snapshot(self):
        return {}
    def restore(self, snapshot):
        pass
    def prepare(self, target):
        pass
    def begin(self):
        pass
    def commit(self, target):
        pass
    def finish(self):
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
        self.entry = patch("maa.codex.launcher_path", return_value=self.root / "bin/codex-local")
        self.entry.start()
        self.store = Store()
    def tearDown(self):
        self.entry.stop()
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
        self.assertEqual(catalog['models'][0]['slug'], first['name'])
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
        self.assertEqual(metadata[0]['slug'], runtime['display_name'])
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

    def test_reasoning_only_and_unchanged_preserve_running_and_paused(self):
        model, ctrl = self.model('one'), FakeController()
        manager = Manager(self.store, ctrl)
        manager.select(model['key'])
        for active in (True, False):
            ctrl.active = active
            before = (ctrl.starts, ctrl.stops)
            manager.configure({'reasoning': 'high' if active else 'low'})
            manager.configure({})
            self.assertEqual((ctrl.starts, ctrl.stops), before)
            self.assertEqual(ctrl.active, active)
            self.assertEqual(self.store.selected(), self.store.target())
            runtime = read(self.store.path('runtime.json'))
            self.assertEqual(runtime['fingerprint'], fingerprint(self.store.selected()))
            self.assertEqual(codex.parse(codex.profile_path().read_text())['model_context_window'], 8192)
        manager.configure({'reasoning': 'default'})
        self.assertNotIn('model_reasoning_effort', codex.parse(codex.profile_path().read_text()))

    def test_reasoning_failure_restores_profile_and_saved_state_without_service_calls(self):
        model, ctrl = self.model('one'), FakeController()
        manager = Manager(self.store, ctrl)
        manager.select(model['key'])
        old = self.store.selected()
        profile = codex.profile_path().read_bytes()
        before = (ctrl.starts, ctrl.stops)
        with patch.object(manager, 'save_config', side_effect=Error('injected save failure')):
            with self.assertRaises(Error):
                manager.configure({'reasoning': 'high'})
        self.assertEqual(self.store.selected(), old)
        self.assertEqual(codex.profile_path().read_bytes(), profile)
        self.assertEqual(read(self.store.path('runtime.json'))['fingerprint'], fingerprint(old))
        self.assertEqual((ctrl.starts, ctrl.stops), before)

    def test_configure_rejects_changed_target_during_menu_editing(self):
        first, second, ctrl = self.model('one'), self.model('two'), FakeController()
        manager = Manager(self.store, ctrl)
        manager.select(first['key'])
        original = self.store.selected()
        manager.select(second['key'])
        before = ctrl.starts
        with self.assertRaisesRegex(Error, 'changed during editing'):
            manager.configure({'reasoning': 'high'}, expected=original)
        self.assertEqual(ctrl.starts, before)
        self.assertEqual(self.store.selected()['model']['key'], second['key'])

    def test_start_running_reuses_instance_and_paused_reuses_native_configuration(self):
        model, ctrl = self.model('one'), FakeController()
        manager = Manager(self.store, ctrl)
        manager.select(model['key'])
        ctrl.valid = True
        before = (ctrl.starts, ctrl.stops)
        with patch('maa.manager.llama_status', return_value={'state': 'running', 'context': 8192}):
            manager.start()
            manager.select(model['key'])
        self.assertEqual((ctrl.starts, ctrl.stops), before)
        manager.pause()
        with patch.object(ctrl, 'prepare', side_effect=AssertionError('Must reuse saved unit')):
            manager.start()
        self.assertEqual(ctrl.starts, before[0] + 1)

    def test_ctrl_c_rolls_back_and_keeps_exit_code_130(self):
        from maa.cli import run
        first, second, ctrl = self.model('one'), self.model('two'), FakeController()
        manager = Manager(self.store, ctrl)
        manager.select(first['key'])
        original_wait = ctrl.wait
        def interrupted(target):
            if target['model']['key'] == second['key']:
                raise KeyboardInterrupt
            return original_wait(target)
        with patch.object(ctrl, 'wait', side_effect=interrupted), patch('maa.cli.Manager', return_value=manager), \
                patch('sys.stderr', new_callable=io.StringIO) as output:
            self.assertEqual(run(['select', second['key']]), 130)
        self.assertIn('已中断', output.getvalue())
        self.assertIn('Previous service restored', output.getvalue())
        self.assertTrue(ctrl.active)
        self.assertEqual(self.store.selected()['model']['key'], first['key'])

    def test_running_ollama_inventory_and_codex_install_do_not_stop_backend(self):
        model, ctrl = self.model('one'), FakeController()
        model.update(backend='ollama', name='fixture:latest')
        self.store.register(model)
        manager = Manager(self.store, ctrl)
        manager.select(model['key'])
        before = (ctrl.starts, ctrl.stops)
        with patch('maa.manager.ollama_inventory', return_value=[model]), patch('maa.manager.ollama_session') as session:
            self.assertEqual(manager.inventory('ollama'), [model])
            session.assert_not_called()
        with patch('maa.install.component') as installer:
            manager.install('codex')
            installer.assert_called_once_with('codex')
        self.assertEqual((ctrl.starts, ctrl.stops), before)
        with self.assertRaises(Error):
            manager.add_model('ollama', name='../invalid')
        self.assertEqual((ctrl.starts, ctrl.stops), before)

    def test_running_ollama_download_allows_pause_without_restoring_stale_state(self):
        model, ctrl = self.model('one'), FakeController()
        model.update(backend='ollama', name='fixture:latest')
        self.store.register(model)
        manager = Manager(self.store, ctrl)
        manager.select(model['key'])
        before = ctrl.starts
        def transfer(*args):
            manager.pause()  # Would deadlock if the transfer kept control.lock.
            raise Error('Native transfer interrupted by service stop')
        with patch('maa.manager.ollama_install', side_effect=transfer), self.assertRaisesRegex(Error, 'transfer interrupted'):
            manager.add_model('ollama', name='other:latest')
        self.assertEqual(ctrl.starts, before)
        self.assertFalse(ctrl.active)
        self.assertEqual(self.store.selected()['model']['key'], model['key'])

    def test_product_upgrade_keeps_backend_for_none_codex_and_inactive_component(self):
        from maa.install import product
        model, ctrl = self.model('one'), FakeController()
        manager = Manager(self.store, ctrl)
        manager.select(model['key'])
        before = (ctrl.starts, ctrl.stops)
        saved = self.store.selected()
        profile = codex.profile_path().read_bytes()
        source = self.root / 'upgrade.pyz'
        source.write_bytes(b'owned upgrade fixture')
        with patch('maa.install.require_container'), patch('maa.install.Controller', return_value=ctrl), \
             patch('maa.manager.Controller', return_value=ctrl), patch.object(ctrl, 'legacy_path', return_value=None, create=True), \
             patch.object(ctrl, 'migrate', create=True), patch('maa.install.Path.home', return_value=self.root):
            for component in ('none', 'codex', 'ollama'):
                with self.subTest(component=component), patch('maa.install.component') as installer:
                    product(source, components=component)
                    if component == 'none':
                        installer.assert_not_called()
                    else:
                        installer.assert_called_once_with(component)
                    self.assertEqual((ctrl.starts, ctrl.stops), before)
                    self.assertTrue(ctrl.active)
                    self.assertEqual(self.store.selected(), saved)
                    self.assertEqual(codex.profile_path().read_bytes(), profile)
                    self.assertEqual((self.root / '.local/share/my-ai-agent/maa.pyz').read_bytes(), source.read_bytes())

    def test_saved_start_failure_returns_to_paused_state(self):
        model, ctrl = self.model('one'), FakeController()
        manager = Manager(self.store, ctrl)
        manager.select(model['key'])
        manager.pause()
        ctrl.valid, ctrl.fail = True, 1
        with self.assertRaisesRegex(Error, 'Previous stopped state restored'):
            manager.start()
        self.assertFalse(ctrl.active)

    def test_current_ollama_tag_download_invalidates_native_reuse_without_reloading(self):
        model, ctrl = self.model('one'), FakeController()
        model.update(backend='ollama', name='fixture:latest')
        self.store.register(model)
        manager = Manager(self.store, ctrl)
        manager.select(model['key'])
        before = (ctrl.starts, ctrl.stops)
        with patch('maa.manager.ollama_install', return_value=model['name']), \
             patch('maa.manager.ollama_inventory', return_value=[model]):
            manager.add_model('ollama', name=model['name'])
        self.assertEqual((ctrl.starts, ctrl.stops), before)
        self.assertIsNone(read(self.store.path('runtime.json'))['native_config'])

    def test_all_gguf_shards_checked_before_service_stop(self):
        first, second = self.root / 'model-00001-of-00002.gguf', self.root / 'model-00002-of-00002.gguf'
        gguf(first)
        gguf(second)
        model = local_model(first)
        self.store.register(model)
        self.assertEqual(len(model['files']), 2)
        ctrl, manager = FakeController(), None
        manager = Manager(self.store, ctrl)
        for damage in ('deleted', 'replaced'):
            if damage == 'deleted':
                second.unlink()
            else:
                gguf(second, True)
            with self.assertRaisesRegex(Error, 'GGUF changed'):
                manager.select(model['key'])
            self.assertEqual(ctrl.stops, 0)
        legacy = {key: value for key, value in model.items() if key != 'files'}
        with self.assertRaisesRegex(Error, 'Legacy GGUF'):
            verify_file(legacy)

    def test_hf_cache_repairs_only_damaged_shard_and_releases_control_lock(self):
        names = ['model-00001-of-00002.gguf', 'model-00002-of-00002.gguf']
        import hashlib
        sample = self.root / 'sample.gguf'
        gguf(sample)
        blob = sample.read_bytes()
        document = {'sha': 'pinned-commit', 'siblings': [{'rfilename': name, 'size': len(blob),
                    'lfs': {'size': len(blob), 'sha256': hashlib.sha256(blob).hexdigest()}} for name in names]}
        downloaded = []
        run_process = subprocess.run
        def transfer(args, **kwargs):
            path = Path(args[args.index('--output') + 1])
            downloaded.append(path.name)
            probe = run_process([sys.executable, '-c',
                'import fcntl,sys; fcntl.flock(open(sys.argv[1],"a"),fcntl.LOCK_EX|fcntl.LOCK_NB)',
                str(self.store.path('control.lock'))], capture_output=True)
            self.assertEqual(probe.returncode, 0, probe.stderr)
            gguf(path)
            return subprocess.CompletedProcess(args, 0)
        from contextlib import nullcontext
        with patch('maa.models.urllib.request.urlopen', side_effect=lambda *a, **k: nullcontext(io.StringIO(json.dumps(document)))), \
                patch('maa.models.subprocess.run', side_effect=transfer):
            # transfer uses the unpatched subprocess call for its independent lock probe.
            model = hf_download(self.store, 'publisher/repo', names[0])
            gguf(Path(model['files'][1]['path']), True)  # Valid header and size, wrong content hash.
            restored = hf_download(self.store, 'publisher/repo', names[0])
        self.assertEqual(len(downloaded), 3)
        self.assertEqual(downloaded[-1], names[1] + '.part')
        verify_file(restored)



if __name__ == '__main__':
    unittest.main()
