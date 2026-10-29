import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from maa import agent_status, backends, codex


class Independence(unittest.TestCase):
    def test_native_hosts_are_not_restricted(self):
        with patch.dict(os.environ, {'OLLAMA_HOST':'http://192.0.2.20:11435','LLAMA_ARG_HOST':'192.0.2.21','LLAMA_ARG_PORT':'18080'}):
            self.assertEqual(backends.ollama_endpoint(), 'http://192.0.2.20:11435')
            self.assertEqual(backends.llama_endpoint(), 'http://192.0.2.21:18080')

    def test_agent_query_only_requests_configuration_and_closes_process(self):
        with tempfile.TemporaryDirectory() as temp:
            command=Path(temp)/'codex'
            trace=Path(temp)/'trace'
            command.write_text('''#!/usr/bin/env python3
import json, os, sys
for line in sys.stdin:
    value=json.loads(line)
    with open(os.environ['MAA_QUERY_TRACE'],'a') as f: f.write(value['method']+'\\n')
    if value['method']=='initialize': print(json.dumps({'id':1,'result':{}}),flush=True)
    if value['method']=='config/read': print(json.dumps({'id':2,'result':{'config':{'approval_policy':'never','sandbox_mode':'danger-full-access','secret':'do not expose'}}}),flush=True)
''')
            command.chmod(0o755)
            with patch.dict(os.environ, {'MAA_QUERY_TRACE':str(trace)}), patch.object(agent_status,'binary',return_value=str(command)):
                value=agent_status.configuration()
            self.assertEqual(value, codex.YOLO)
            self.assertEqual(trace.read_text().splitlines(), ['initialize','initialized','config/read'])

    def test_agent_timeout_and_protocol_failure_are_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'codex';path.write_text('#!/bin/sh\nexec sleep 30\n');path.chmod(0o755)
            with patch.object(agent_status,'binary',return_value=str(path)):
                with self.assertRaisesRegex(Exception,'Timed out'): agent_status.configuration(timeout=.05)

    def test_installed_checks_refuse_a_different_product_before_agent_or_services(self):
        try:
            from maa_testing import native
        except ImportError:
            import importlib.util
            spec=importlib.util.spec_from_file_location('maa_readonly_native',Path(__file__).resolve().parents[1]/'test/native.py')
            native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
        from types import SimpleNamespace
        from maa.store import Store
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp);archive=home/'.local/share/my-ai-agent/maa.pyz'
            archive.parent.mkdir(parents=True);archive.write_bytes(b'old installed archive')
            paired=home/'paired.pyz';paired.write_bytes(b'new paired archive')
            state=Store(home/'state')
            with patch.dict(os.environ, {'CODEX_HOME':str(home/'codex'), 'XDG_CONFIG_HOME':str(home/'preferences')}), \
                 patch('pathlib.Path.home',return_value=home), patch('maa.manager.Manager',return_value=SimpleNamespace(store=state)), \
                 patch('maa.agent_status.configuration') as agent:
                with self.assertRaisesRegex(AssertionError,'differs'):native.run(paired)
                agent.assert_not_called()
            report=json.loads(next(home.glob('maa-native-*.json')).read_text())
            self.assertEqual(report['checks'][0]['status'],'failed')
            self.assertEqual(archive.read_bytes(),b'old installed archive')

    def test_public_help_has_no_removed_feature(self):
        from maa.cli import parser
        help_text=parser().format_help()
        self.assertNotIn('inside ',help_text)
        self.assertNotIn(' im ',help_text)
