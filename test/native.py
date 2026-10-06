#!/usr/bin/env python3
"""Actual installed-product smoke test inside a disposable mas container.

It downloads two small models, changes the selected target and leaves it
paused. Run inside a fresh disposable container, not one with user workloads.
"""
import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request

MAA = str(Path.home() / '.local/bin/maa')
LOCAL = str(Path.home() / '.local/bin/codex-local')
REPORT = {'version': '0.1.1', 'started': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'checks': []}


def command(*args, structured=True, success=True, timeout=900):
    result = subprocess.run([MAA, *args], text=True, capture_output=True, timeout=timeout)
    if success and result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    if not success:
        if result.returncode == 0:
            raise RuntimeError('Expected command to fail: ' + str(args))
        return result.stderr
    return json.loads(result.stdout) if structured else result.stdout


def check(name, function):
    try:
        detail = function()
        REPORT['checks'].append({'name': name, 'status': 'passed', 'detail': detail})
        print('✓ ' + name, flush=True)
        return detail
    except Exception as exc:
        REPORT['checks'].append({'name': name, 'status': 'failed', 'error': str(exc)})
        raise


def api(body):
    req = urllib.request.Request('http://127.0.0.1:18443/v1/responses',
                                 data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=300).read()


def inference():
    result = json.loads(api({'input': 'Reply with the word hello.', 'max_output_tokens': 64,
                             'reasoning': {'effort': 'none'}}))
    assert result['status'] == 'completed' and result['output'], result
    wire = api({'input': 'Reply with the word hello.', 'stream': True, 'max_output_tokens': 64,
                'reasoning': {'effort': 'none'}}).decode()
    assert 'response.output_text.delta' in wire and 'response.completed' in wire, wire
    return {'nonstream': result, 'stream_completed': True}


def native_tool_call():
    prompt = 'What is the weather in London? Use get_weather.'
    tools = [{'type': 'function', 'name': 'get_weather', 'description': 'Get weather for a city.',
              'parameters': {'type': 'object', 'properties': {'city': {'type': 'string'}},
                             'required': ['city'], 'additionalProperties': False}}]
    result = json.loads(api({'input': prompt,
                             'reasoning': {'effort': 'none'}, 'max_output_tokens': 128,
                             'tools': tools, 'tool_choice': {'type': 'function', 'name': 'get_weather'}}))
    calls = [item for item in result['output'] if item['type'] == 'function_call']
    assert calls and calls[0]['name'] == 'get_weather', result
    assert isinstance(json.loads(calls[0]['arguments']).get('city'), str), calls
    followup = json.loads(api({'input': [{'role': 'user', 'content': prompt}, calls[0],
          {'type': 'function_call_output', 'call_id': calls[0]['call_id'], 'output': '18 degrees Celsius.'}],
          'tools': tools, 'max_output_tokens': 128, 'reasoning': {'effort': 'none'}}))
    assert any(item['type'] == 'message' for item in followup['output']), followup
    return {'call': result, 'replay': followup}


def codex_exec():
    with tempfile.TemporaryDirectory(prefix='maa-codex-native-') as folder:
        result = subprocess.run([LOCAL, 'exec', '--skip-git-repo-check', '--ephemeral', '-C', folder,
                                 'Reply with MAA_NATIVE_OK. Do not use tools.'], capture_output=True,
                                text=True, timeout=600, stdin=subprocess.DEVNULL)
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip(), result.stderr
        return {'output': result.stdout, 'diagnostic': result.stderr[-8192:]}


def main():
    assert Path('/dev/lxd/sock').exists(), 'Run in a disposable mas container'
    check('installed-version', lambda: command('--version', structured=False).strip())
    llama = check('hf-exact-download', lambda: command('add', 'llamacpp', '--repo', 'unsloth/Qwen3-0.6B-GGUF',
                                                       '--file', 'Qwen3-0.6B-Q4_K_M.gguf'))
    ollama = check('ollama-native-pull', lambda: command('add', 'ollama', '--name', 'qwen3:0.6b'))
    check('hf-invalid-file-rejected', lambda: command('add', 'llamacpp', '--repo', 'unsloth/Qwen3-0.6B-GGUF',
                                                      '--file', 'not-present.gguf', success=False))
    for model in (llama, ollama):
        check(model['backend'] + '-select', lambda: command('select', model['key'], '--set', 'context=32768'))
        check(model['backend'] + '-responses', inference)
        check(model['backend'] + '-native-function-call', native_tool_call)
        check(model['backend'] + '-codex-cli', codex_exec)
    def retained():
        command('pause', structured=False)
        state = command('status')
        assert not state['running'] and state['selected']['model']['key'] == ollama['key']
        state = command('start')
        assert state['running'] and state['selected']['model']['key'] == ollama['key']
        return state
    check('pause-start-retains-target', retained)
    def rollback():
        # A metadata-valid but weight-less file reaches native loading and fails.
        import struct
        root = Path.home() / '.local/state/my-ai-agent'
        path = root / 'bad-native.gguf'
        path.write_bytes(b'GGUF' + struct.pack('<IQQ', 3, 0, 0))
        bad = command('add', 'llamacpp', '--path', str(path))
        error = command('select', bad['key'], success=False)
        state = command('status')
        assert state['running'] and state['selected']['model']['key'] == ollama['key'], state
        return error
    check('native-load-failure-rollback', rollback)
    check('yolo-off', lambda: command('yolo', 'off'))
    check('yolo-on', lambda: command('yolo', 'on'))
    command('pause', structured=False)


def run():
    try:
        main()
    finally:
        REPORT['finished'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report = Path.home() / ('maa-native-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.json')
        report.write_text(json.dumps(REPORT, ensure_ascii=False, indent=2) + '\n')
        print('报告：' + str(report), flush=True)


if __name__ == '__main__':
    run()
