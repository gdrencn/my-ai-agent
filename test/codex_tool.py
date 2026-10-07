#!/usr/bin/env python3
"""Real Codex execution against a deterministic native Responses test fixture.

This test server is never installed or shipped in the product. It verifies the
client contract without measuring a small model's tool-selection competence.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, str(Path.home() / '.local/share/my-ai-agent/maa.pyz'))
from maa import codex


def main():
    seen, declarations = [], []
    previous_home = os.environ.get('CODEX_HOME')
    class Native(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            assert self.path == '/v1/responses', self.path
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            outputs = [m for m in body.get('input', []) if m.get('type') == 'function_call_output']
            if outputs:
                seen.extend(outputs)
                item = {'id': 'msg_fixture', 'type': 'message', 'role': 'assistant', 'status': 'completed',
                        'content': [{'type': 'output_text', 'text': 'Done.', 'annotations': []}]}
            else:
                tools = body.get('tools', [])
                declarations.extend(tools)
                fn = next(t for t in tools if t['type'] == 'function' and t['name'].endswith(('exec_command', 'shell_command')))
                key = 'cmd' if fn['name'].endswith('exec_command') else 'command'
                item = {'id': 'fc_fixture', 'type': 'function_call', 'call_id': 'call_real_exec', 'status': 'completed',
                        'name': fn['name'], 'arguments': json.dumps({
                            key: 'printf MAA_REAL_CODEX_TOOL_OK > codex-proof.txt; cat codex-proof.txt'})}
            response = {'id': 'resp_fixture', 'object': 'response', 'status': 'completed',
                        'model': body['model'], 'output': [item], 'usage': {'input_tokens': 32, 'output_tokens': 4, 'total_tokens': 36}}
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            for event in [
                {'type': 'response.created', 'response': {**response, 'status': 'in_progress', 'output': []}},
                {'type': 'response.output_item.added', 'output_index': 0, 'item': {**item, 'status': 'in_progress'}},
                {'type': 'response.output_item.done', 'output_index': 0, 'item': item},
                {'type': 'response.completed', 'response': response}]:
                self.wfile.write(('event: '+event['type']+'\ndata: '+json.dumps(event)+'\n\n').encode())
                self.wfile.flush()
    native = ThreadingHTTPServer(('127.0.0.1', 0), Native)
    threading.Thread(target=native.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='.maa-real-codex-tool-', dir=Path.home()) as folder:
            folder = Path(folder)
            os.environ['CODEX_HOME'] = str(folder / 'codex')
            codex.home().mkdir()
            (codex.home() / 'config.toml').write_text('approval_policy="never"\nsandbox_mode="danger-full-access"\n')
            runtime = {'model': 'native_fixture', 'context': 32768, 'base_url': f'http://127.0.0.1:{native.server_port}/v1'}
            codex.profile(runtime, {'reasoning': 'default'})
            result = subprocess.run([codex.executable(), '--no-daemon', '--profile', 'maa-local', 'exec', '--skip-git-repo-check',
                '--ephemeral', '-C', str(folder), 'Use a shell tool to print MAA_REAL_CODEX_TOOL_OK, then answer done.'],
                capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
            assert result.returncode == 0, result.stdout + result.stderr
            assert (folder / 'codex-proof.txt').read_text() == 'MAA_REAL_CODEX_TOOL_OK'
            assert seen and 'MAA_REAL_CODEX_TOOL_OK' in str(seen[0]['output']), seen
            assert not any(t['type'] == 'custom' for t in declarations), declarations
            return {'status': 'passed', 'kind': 'real Codex / native Responses deterministic fixture',
                  'tool_output_replayed': True, 'file_created_by_codex_tool': True,
                  'declarations': [(t['type'], t.get('name')) for t in declarations],
                  'stdout': result.stdout, 'diagnostic': result.stderr[-8192:]}
    finally:
        if previous_home is None:
            os.environ.pop('CODEX_HOME', None)
        else:
            os.environ['CODEX_HOME'] = previous_home
        native.shutdown()
        native.server_close()


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
