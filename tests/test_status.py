import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from maa import backends, bridge, menu, ui
from maa.manager import Manager
from maa.service import fingerprint
from maa.settings import settings
from maa.store import Error, Store, read, write
from maa.telemetry import allocations, native_allocations, launch_reference, UsageRecorder, last_usage, nvidia_memory

MAIN = b'''print_info: no_alloc = 0
load_tensors: loading model tensors
load_tensors: offloaded 29/29 layers to GPU
load_tensors: CPU_Mapped model buffer size = 83.46 MiB
load_tensors: CUDA0 model buffer size = 409.29 MiB
llama_context: n_rs_seq = 0
llama_context: CUDA_Host output buffer size = 0.58 MiB
llama_kv_cache: CUDA0 KV buffer size = 1904.00 MiB
sched_reserve: CUDA0 compute buffer size = 200.00 MiB
sched_reserve: CUDA0 compute buffer size = 216.10 MiB
sched_reserve: CUDA_Host compute buffer size = 72.10 MiB
'''
MTP = b'''common_speculative_init_result: creating MTP draft context against the target model 'test.gguf'
llama_kv_cache: CUDA0 KV buffer size = 702.00 MiB
sched_reserve: CUDA0 compute buffer size = 487.03 MiB
'''


class Status(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name))
        self.model = {'key': 'fixture-key', 'backend': 'ollama', 'name': 'qwen:test', 'mtp_supported': False}
        self.target = {'model': self.model, 'settings': settings()}
        self.log = self.store.path('native.log')
        self.log.write_bytes(MAIN)
        self.runtime = {'fingerprint': fingerprint(self.target), 'key': self.model['key'], 'backend': 'ollama',
                        'model': 'private-route', 'display_name': self.model['name'], 'context': 8192,
                        'upstream': 'http://localhost:11434', 'launch': launch_reference(self.log, 0, 'service-one')}
        write(self.store.path('runtime.json'), self.runtime)
        write(self.store.path('selected.json'), self.target)
    def tearDown(self):
        self.temp.cleanup()

    def test_actual_buffers_replace_probes_retries_and_deduplicate(self):
        probe = b'print_info: no_alloc = 1\nload_tensors: loading model tensors\nload_tensors: CUDA0 model buffer size = 9999 MiB\n'
        result = allocations(MAIN + MTP + probe + MAIN)
        self.assertEqual(result['gpu_identified_mib'], 2529.39)
        self.assertEqual(result['gpu_layers'], [29, 29])
        self.assertFalse(any(row['phase'] == 'mtp' for row in result['buffers']))
        self.assertEqual(len(result['buffers']), 6)
        self.assertEqual(allocations(b'common_fit: projected to use 9999 MiB\n')['buffers'], [])
        self.assertEqual(allocations(MAIN[MAIN.find(b'llama_kv_cache'):])['buffers'], [])
        initialized = MAIN + b'srv llama_server: model loaded\n' + MTP
        self.assertEqual(allocations(initialized)['gpu_identified_mib'], 2529.39)
        self.assertEqual(allocations(initialized)['rs_sequences'], 0)

    def test_mtp_rs_and_host_memory_have_distinct_allocations(self):
        result = allocations(MAIN + b'llama_memory_recurrent: CUDA0 RS buffer size = 748.12 MiB\n' + MTP)
        self.assertEqual(result['gpu_identified_mib'], 4466.54)
        self.assertEqual([row['mib'] for row in result['buffers'] if row['kind'] == 'KV'], [1904, 702])
        shared = allocations(MAIN + MTP.split(b'llama_kv_cache:')[0] + b'llama_kv_cache: layer 0: sharing with layer 0. k = 0x1, v = 0x2\n')
        self.assertTrue(shared['mtp_shared_kv'])
        self.assertEqual(shared['gpu_identified_mib'], 2529.39)
        self.assertEqual([row['location'] for row in result['buffers'] if row['backend'] == 'CUDA_Host'], ['host', 'host'])

    def test_current_launch_replaced_logs_and_bounded_window(self):
        ref = native_allocations(self.store, self.runtime)
        self.assertEqual(ref['gpu_identified_mib'], 2529.39)
        self.log.rename(self.log.with_suffix('.old'))
        self.log.write_bytes(MAIN)
        self.assertIsNotNone(native_allocations(self.store, self.runtime)['error'])
        self.runtime['launch'] = launch_reference(self.log, 0, 'two')
        with patch('maa.telemetry.LOG_LIMIT', 100):
            result = native_allocations(self.store, self.runtime)
        self.assertIsNone(result['gpu_identified_mib'])

    def test_ollama_and_llama_queries_are_backend_specific_and_read_only(self):
        with patch('maa.backends.request', return_value={'models': []}) as call:
            self.assertEqual(backends.ollama_status(self.runtime)['state'], 'idle')
            call.assert_called_once_with('http://localhost:11434/api/ps', timeout=2)
        with patch('maa.backends.request', return_value={'is_sleeping': True, 'default_generation_settings': {'n_ctx': 8192}}) as call:
            self.assertEqual(backends.llama_status(self.runtime)['state'], 'idle')
            call.assert_called_once_with('http://localhost:11434/props', timeout=2)
        with patch('maa.backends.request', return_value={'default_generation_settings': {}}) as call:
            with self.assertRaises(Error):
                backends.llama_status(self.runtime)
            self.assertEqual(call.call_count, 1)  # Never fall back to wake-inducing /slots.
        for payload in ([], {'models': ['bad-entry']}):
            with patch('maa.backends.request', return_value=payload), self.assertRaises(Error):
                backends.ollama_status(self.runtime)
        with patch('maa.backends.request', return_value={'default_generation_settings': []}), self.assertRaises(Error):
            backends.llama_status(self.runtime)

    def test_status_hides_old_allocations_on_pause_idle_switch_and_failure(self):
        class Controller:
            def running(self):
                return True
        manager = Manager(self.store, Controller())
        with patch('maa.manager.ollama_status', return_value={'state': 'running', 'context': 8192}):
            self.assertEqual(manager.model_status(False)['allocations']['gpu_identified_mib'], 2529.39)
        with patch('maa.manager.ollama_status', return_value={'state': 'idle', 'context': None}):
            value = manager.model_status(False)
            self.assertEqual(value['state'], 'idle')
            self.assertIsNone(value['allocations'])
        with patch('maa.manager.ollama_status', side_effect=Error('unreachable')):
            value = manager.model_status(False)
            self.assertEqual(value['state'], 'error')
            self.assertIn('unreachable', value['error'])
        self.runtime['fingerprint'] = 'old-target'
        write(self.store.path('runtime.json'), self.runtime)
        self.assertEqual(manager.model_status(False)['state'], 'loading')
        with patch.object(manager.controller, 'running', return_value=False), patch('maa.manager.ollama_status') as call:
            self.assertEqual(manager.model_status(False)['state'], 'paused')
            call.assert_not_called()

    def test_usage_counts_only_current_load_without_conversation_data(self):
        recorder = UsageRecorder(self.store, self.runtime)
        recorder({'usage': {'input_tokens': 123, 'output_tokens': 4}, 'output': ['must not persist']})
        value = last_usage(self.store, self.runtime, native_allocations(self.store, self.runtime)['load_id'])
        self.assertEqual(value['input_tokens'], 123)
        self.assertNotIn('must not persist', self.store.path('usage.json').read_text())
        with self.log.open('ab') as log:
            log.write(MAIN)
        self.assertIsNone(last_usage(self.store, self.runtime, native_allocations(self.store, self.runtime)['load_id']))
        recorder({'usage': None})
        self.assertIsNone(read(self.store.path('usage.json'))['input_tokens'])
        self.runtime['launch']['service_id'] = 'retired'
        recorder({'usage': {'input_tokens': 99}})
        self.assertIsNone(read(self.store.path('usage.json'))['input_tokens'])

    def test_partial_native_usage_keeps_missing_counts_unknown(self):
        response = bridge.Responses('original-model', {}, lambda event: None)
        response.delta({'usage': {'prompt_tokens': 17}, 'choices': []})
        self.assertIsNone(response.finish()['usage'])
        UsageRecorder(self.store, self.runtime)({'usage': response.native_usage})
        counters = last_usage(self.store, self.runtime, native_allocations(self.store, self.runtime)['load_id'])
        self.assertEqual(counters['input_tokens'], 17)
        self.assertIsNone(counters['output_tokens'])
        response.delta({'usage': {'prompt_tokens': True, 'completion_tokens': -1}, 'choices': []})
        self.assertIsNone(response.value['usage'])
        self.assertEqual(response.native_usage, {'input_tokens': None, 'output_tokens': None})
        response.delta({'usage': 'malformed', 'choices': []})
        self.assertIsNone(response.value['usage'])

    def test_driver_free_is_not_derived_and_unavailable_is_not_zero(self):
        result = type('Result', (), {'returncode': 0, 'stdout': '0, GPU, 24463, 0, 24137, 326\n', 'stderr': ''})()
        with patch('maa.telemetry.shutil.which', return_value='/fixture/nvidia-smi'), patch('maa.telemetry.subprocess.run', return_value=result):
            row = nvidia_memory()['devices'][0]
        self.assertEqual(row['free_mib'], 24137)
        self.assertEqual(row['reserved_mib'], 326)
        self.assertNotEqual(row['total_mib'] - row['used_mib'], row['free_mib'])

    def test_display_preserves_units_order_unknowns_and_color_contract(self):
        value = {'backend': 'llamacpp', 'model': 'real-model.gguf', 'state': 'running', 'mtp': 'unavailable',
                 'allocations': allocations(MAIN), 'context': 8192,
                 'usage': {'input_tokens': 1024, 'output_tokens': 4, 'recorded_at': 1}, 'gpu_memory': {}}
        lines = [menu.rendered(line, 10000, color=False) for line in ui.status_lines(value)]
        self.assertTrue(lines[0].startswith('底座：llama.cpp'))
        self.assertTrue(lines[1].startswith('当前模型：real-model.gguf'))
        self.assertIn('上下文占用（最近一次输入）：1024 / 8192 tokens（12.5%）', lines)
        self.assertNotIn('MTP 权重', '\n'.join(lines))
        label = ui.value_line('上下文大小', '8192')
        self.assertEqual(menu.rendered(label, 100), '上下文大小：\x1b[36m8192\x1b[39m')
        chunks = menu.wrapped(label, 12)
        self.assertEqual(''.join(menu.rendered(line, 100, color=False) for line in chunks), '上下文大小：8192')
