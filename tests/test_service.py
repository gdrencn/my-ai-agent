"""Native configuration and independent-entrypoint regression checks."""
from contextlib import nullcontext
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from maa import backends, codex
from maa.service import Controller
from maa.settings import settings
from maa.store import Error, Store, read


class Service(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'state')
        self.controller = Controller(self.store)
    def tearDown(self):
        self.temp.cleanup()

    def test_launcher_executes_codex_after_manager_is_removed(self):
        folder = self.root / 'bin'; folder.mkdir()
        fake = folder / 'codex'
        fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\nprintf "PID=%s\\n" "$$"\n')
        fake.chmod(0o755)
        entry = folder / 'codex-local';entry.write_text(codex.launcher());entry.chmod(0o755)
        # No installed manager, state, model registry or Python path is present.
        env = {'PATH': str(folder) + ':/usr/bin:/bin', 'HOME': str(self.root)}
        process = subprocess.Popen([str(entry), 'exec', 'text with spaces'], env=env, stdout=subprocess.PIPE, text=True)
        out = process.communicate(timeout=5)[0]
        self.assertEqual(process.returncode, 0)
        self.assertEqual(out.splitlines(), ['--no-daemon', '--profile', 'maa-local', 'exec', 'text with spaces', f'PID={process.pid}'])
        self.assertCountEqual(self.root.iterdir(), [folder, self.store.root])

    def test_native_units_execute_only_native_programs(self):
        paths = {b: self.root / (b + '.service') for b in ('ollama', 'llamacpp')}
        def write_unit(path, text):path.write_text(text)
        values = settings()
        for backend in paths:
            target = {'model': {'backend': backend, 'name': 'model:tag'}, 'settings': values}
            with patch.object(self.controller, 'ensure'), patch.object(self.controller, 'unit_path', side_effect=lambda b: paths[b]), \
                 patch.object(self.controller, 'write_unit', side_effect=write_unit), patch('maa.service.privileged'), \
                 patch('maa.service.ollama_capabilities', return_value='--fit --fit-target'), \
                 patch('maa.models.ollama_session', return_value=nullcontext()), patch('maa.service.ollama_prepare'), \
                 patch('maa.service.request'), \
                 patch('socket.create_connection', side_effect=ConnectionRefusedError), \
                 patch('maa.service.binary', return_value='/usr/local/bin/ollama'), \
                 patch('maa.service.llama_arguments', return_value=['/usr/local/bin/llama', 'serve', '--model', '/models/my model.gguf']):
                self.controller.prepare(target)
            text = paths[backend].read_text()
            commands = [line for line in text.splitlines() if line.startswith('Exec') and line.split('=', 1)[1]]
            self.assertTrue(commands)
            for command in commands:
                self.assertNotIn('maa', command)
                self.assertNotIn('python', command)
                self.assertNotIn('.pyz', command)
            self.assertNotIn('18443', text)
        self.assertIn('ollama" serve', paths['ollama'].read_text())
        self.assertIn('"/usr/local/bin/llama" "serve"', paths['llamacpp'].read_text())

    def test_foreign_native_unit_refused_before_mutation(self):
        path = self.root / 'foreign.service'; path.write_text('[Service]\nExecStart=/user/program\n')
        with patch('maa.install.require_container'), patch.object(self.controller, 'unit_path', return_value=path), \
             patch('maa.service.privileged') as mutate:
            with self.assertRaisesRegex(Error, 'not owned'):
                self.controller.ensure()
            mutate.assert_not_called()
        self.assertEqual(path.read_text(), '[Service]\nExecStart=/user/program\n')

    def test_ollama_preserves_original_presets_and_public_model_name(self):
        model = {'name': 'qwen:tag', 'key': 'a'*24, 'digest': 'original', 'mtp_supported': True}
        target = {'model': model, 'settings': settings(changes={'context': 4096}, mtp_supported=True)}
        rows = [{'name': model['name'], 'digest': 'original'}]
        calls = []
        def api(url, value=None, **kwargs):
            calls.append((url, value))
            if url.endswith('/api/tags'):return {'models': list(rows)}
            if url.endswith('/api/show'):return {'parameters': 'temperature 0.7\ndraft_num_predict 16\n'}
            if url.endswith('/api/copy'):
                rows.append({'name': value['destination'], 'digest': 'original'})
                return {}
            if url.endswith('/api/create'):
                rows[0]['digest'] = 'configured'
                return {'status': 'success'}
            raise AssertionError(url)
        with patch('maa.backends.request', side_effect=api):
            name, _ = backends.ollama_prepare(target, self.store)
            backends.ollama_prepare(target, self.store)
        self.assertEqual(name, model['name'])
        mutations = [value for _, value in calls if value and 'parameters' in value]
        self.assertEqual(mutations[0]['parameters'], {'num_ctx': 4096, 'draft_num_predict': 16})
        self.assertEqual(len([url for url, _ in calls if url.endswith('/api/copy')]), 1)
        self.assertEqual(read(self.store.path('ollama-originals.json'))[model['name']]['configured_digest'], 'configured')

    def test_private_original_backup_collision_is_refused(self):
        model = {'name': 'qwen:tag', 'key': 'a'*24, 'digest': 'original', 'mtp_supported': False}
        rows = [{'name': model['name'], 'digest': 'original'}, {'name': 'maa-source-'+'a'*24+':latest', 'digest': 'foreign'}]
        def api(url, value=None, **kwargs):
            return {'models': rows} if url.endswith('/api/tags') else {}
        with patch('maa.backends.request', side_effect=api) as call:
            with self.assertRaisesRegex(Error, 'backup changed'):
                backends.ollama_prepare({'model': model, 'settings': settings()}, self.store)
            self.assertFalse(any('api/create' in c.args[0] for c in call.call_args_list))

    def test_candidate_does_not_enable_autostart_before_commit(self):
        target = {'model': {'backend': 'llamacpp'}}
        with patch.object(self.store, 'target', return_value=target), \
             patch.object(self.controller, 'owned', return_value=True), patch('maa.service.privileged') as native:
            self.controller.begin()
            self.controller.start()
            self.assertFalse(any('enable' in c.args[0] for c in native.call_args_list))
            self.controller.commit(target)
            self.assertEqual(native.call_args.args[0], ['systemctl', 'enable', 'llama-server.service'])

    def test_crashed_candidate_is_reported_before_retry_delay(self):
        with patch.object(self.controller, 'unit_info', return_value={
                'ActiveState': 'activating', 'SubState': 'auto-restart', 'Result': 'exit-code'}), \
             patch.object(self.controller, 'observe') as observe:
            with self.assertRaisesRegex(Error, 'Native service failed'):
                self.controller.wait({'model': {'backend': 'llamacpp'}})
            observe.assert_not_called()

    def test_unmanaged_llama_endpoint_refused_before_unit_write(self):
        target = {'model': {'backend': 'llamacpp', 'name': 'model'}, 'settings': settings()}
        with patch.object(self.controller, 'ensure'), patch('socket.create_connection', return_value=nullcontext()), \
             patch.object(self.controller, 'write_unit') as write_unit:
            with self.assertRaisesRegex(Error, 'unmanaged llama.cpp'):
                self.controller.prepare(target)
            write_unit.assert_not_called()

    def test_restore_restores_exact_native_tag_and_runtime_snapshot(self):
        original = self.store.path('runtime.json'); original.write_text('old runtime')
        self.controller.model_backup = ('qwen:tag', 'maa-rollback-'+'a'*32+':latest')
        snapshot = {'files': {str(original): b'old runtime'}, 'enabled': {}}
        original.write_text('candidate runtime')
        with patch('maa.models.ollama_session', return_value=nullcontext()), \
             patch('maa.service.request') as native, patch('maa.service.privileged'):
            self.controller.restore(snapshot)
        self.assertEqual(original.read_text(), 'old runtime')
        self.assertEqual(native.call_args_list[0].args[1], {
            'source': 'maa-rollback-'+'a'*32+':latest', 'destination': 'qwen:tag'})
        self.assertIsNone(self.controller.model_backup)
