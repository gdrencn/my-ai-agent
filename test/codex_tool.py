#!/usr/bin/env python3
"""Real Codex shell-tool execution over a deterministic native SSE fixture.

This proves client/protocol execution semantics, independently of tiny model
tool-selection quality. It is fault-injected evidence, not model performance.
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
from maa import bridge, codex


def main():
    seen = []
    class Native(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            outputs = [m for m in body['messages'] if m['role'] == 'tool']
            if outputs:
                seen.extend(outputs)
                chunk = {'choices': [{'delta': {'content': 'Done.'}, 'finish_reason': 'stop'}]}
            else:
                tools = body.get('tools', [])
                fn = next(t['function'] for t in tools if t['function']['name'].endswith('exec_command'))
                chunk = {'choices': [{'delta': {'tool_calls': [{'index': 0, 'id': 'call_real_exec',
                     'function': {'name': fn['name'], 'arguments': json.dumps({
                         'cmd': 'printf MAA_REAL_CODEX_TOOL_OK > codex-proof.txt; cat codex-proof.txt'})}}]},
                     'finish_reason': 'tool_calls'}]}
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            self.wfile.write(('data: ' + json.dumps(chunk) + '\n\ndata: [DONE]\n\n').encode())
    native = ThreadingHTTPServer(('127.0.0.1', 0), Native)
    runtime = {'model': 'maa_tool_fixture', 'upstream': f'http://127.0.0.1:{native.server_port}', 'context': 32768}
    adapter = bridge.server(runtime, port=0)
    runtime['base_url'] = f'http://127.0.0.1:{adapter.server_port}/v1'
    for instance in (native, adapter):
        threading.Thread(target=instance.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='maa-real-codex-tool-') as folder:
            folder = Path(folder)
            os.environ['CODEX_HOME'] = str(folder / 'codex')
            codex.home().mkdir()
            (codex.home() / 'config.toml').write_text('approval_policy="never"\nsandbox_mode="danger-full-access"\n')
            codex.profile(runtime, {'reasoning': 'default'})
            result = subprocess.run([codex.executable(), '--profile', 'maa-local', 'exec', '--skip-git-repo-check',
                '--ephemeral', '-C', str(folder), 'Use a shell tool to print MAA_REAL_CODEX_TOOL_OK, then answer done.'],
                capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
            assert result.returncode == 0, result.stdout + result.stderr
            assert (folder / 'codex-proof.txt').read_text() == 'MAA_REAL_CODEX_TOOL_OK'
            assert seen and 'MAA_REAL_CODEX_TOOL_OK' in seen[0]['content'], seen
            report = {'status': 'passed', 'kind': 'real Codex / deterministic upstream fixture',
                      'tool_output_replayed': True, 'file_created_by_codex_tool': True,
                      'stdout': result.stdout, 'diagnostic': result.stderr[-8192:]}
            print(json.dumps(report, indent=2))
    finally:
        for instance in (adapter, native):
            instance.shutdown()
            instance.server_close()


if __name__ == '__main__':
    main()
