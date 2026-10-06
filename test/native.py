#!/usr/bin/env python3
"""Actual installed-product smoke test inside a disposable mas container.

It downloads two small models, changes the selected target and leaves it
paused. Run inside a fresh disposable container, not one with user workloads.
"""
import datetime
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
sys.path.insert(0, str(Path.home() / '.local/share/my-ai-agent/maa.pyz'))
from maa import __version__
from maa.store import Store, read, write

MAA = str(Path.home() / '.local/bin/maa')
LOCAL = str(Path.home() / '.local/bin/codex-local')
REPORT = {'version': __version__, 'started': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'checks': [], 'cleanup': []}


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
        assert 'fallback metadata' not in result.stderr and 'requires embedded mode' not in result.stderr, result.stderr
        return {'output': result.stdout, 'diagnostic': result.stderr[-8192:]}


@contextmanager
def invalid_fixture():
    import struct
    store, key = Store(), None
    previous = store.selected()
    with tempfile.TemporaryDirectory(prefix='maa-native-invalid-') as folder:
        path = Path(folder) / 'bad-native.gguf'
        path.write_bytes(b'GGUF' + struct.pack('<IQQ', 3, 0, 0))
        try:
            bad = command('add', 'llamacpp', '--path', str(path))
            key = bad['key']
            yield bad
        finally:
            selected = store.selected()
            if key and selected and selected['model']['key'] == key:
                if previous:
                    command('select', previous['model']['key'])
                else:
                    command('pause', structured=False)
                    with store.lock():
                        store.path('selected.json').unlink(missing_ok=True)
                        store.path('target.json').unlink(missing_ok=True)
            with store.lock():
                rows = store.models()
                if key:
                    selected = store.selected()
                    if selected and selected['model']['key'] == key:
                        raise RuntimeError('Invalid fixture unexpectedly selected; refusing to remove an active model')
                    rows.pop(key, None)
                    write(store.path('models.json'), rows)
                    (store.path('configs') / (key + '.json')).unlink(missing_ok=True)
            REPORT['cleanup'].append({'fixture': 'bad-native.gguf', 'key': key, 'registry_removed': key not in store.models(),
                                      'temporary_directory': True})


def cleanup_legacy_fixture():
    """Recognize only the exact weight-less fixture created by the 0.1.1 tester."""
    import hashlib
    import struct
    store = Store()
    path = store.path('bad-native.gguf')
    signature = b'GGUF' + struct.pack('<IQQ', 3, 0, 0)
    if not path.is_file() or path.stat().st_size != len(signature) or path.read_bytes() != signature:
        return
    digest = hashlib.sha256(signature).hexdigest()
    with store.lock():
        rows = store.models()
        owned = [key for key, row in rows.items() if row.get('path') == str(path)
                 and row.get('source') == 'local' and row.get('sha256') == digest]
        selected = store.selected()
        if selected and selected['model']['key'] in owned:
            REPORT['cleanup'].append({'legacy_fixture_removed': False, 'reason': 'Fixture is selected; retained'})
            return
        for key in owned:
            rows.pop(key)
            (store.path('configs') / (key + '.json')).unlink(missing_ok=True)
        write(store.path('models.json'), rows)
        path.unlink()
        REPORT['cleanup'].append({'legacy_fixture_removed': True, 'keys': owned})


def catalog_metadata():
    from maa.codex import parse, profile_path
    state = command('status')
    config = parse(profile_path().read_text())
    models = read(config['model_catalog_json'])['models']
    assert len(models) == 1 and models[0]['slug'] == state['runtime']['model'], models
    assert models[0]['display_name'] == state['selected']['model']['name'], models
    assert models[0]['context_window'] == state['runtime']['context'], models
    return {'model': models[0]['slug'], 'display_name': models[0]['display_name'], 'context': models[0]['context_window']}


def ollama_entry_reuse(wake=False):
    import time
    runtime = command('status')['runtime']
    url = runtime['upstream']
    def native_api(route, body=None):
        req = urllib.request.Request(url + route, data=None if body is None else json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)
    before = next(row for row in native_api('/api/tags')['models'] if row['name'] == runtime['model'])
    if wake:
        native_api('/api/generate', {'model': runtime['model'], 'keep_alive': 0})
        assert not any(row['name'] == runtime['model'] for row in native_api('/api/ps')['models'])
    started = time.monotonic()
    diagnostic = codex_exec()
    after = next(row for row in native_api('/api/tags')['models'] if row['name'] == runtime['model'])
    assert before['digest'] == after['digest'] and before['modified_at'] == after['modified_at'], (before, after)
    assert any(row['name'] == runtime['model'] for row in native_api('/api/ps')['models'])
    return {'alias_unchanged': True, 'woke': wake, 'elapsed_seconds': round(time.monotonic() - started, 3),
            'diagnostic': diagnostic['diagnostic']}


def main():
    assert Path('/dev/lxd/sock').exists(), 'Run in a disposable mas container'
    cleanup_legacy_fixture()
    check('installed-version', lambda: command('--version', structured=False).strip())
    llama = check('hf-exact-download', lambda: command('add', 'llamacpp', '--repo', 'unsloth/Qwen3-0.6B-GGUF',
                                                       '--file', 'Qwen3-0.6B-Q4_K_M.gguf'))
    ollama = check('ollama-native-pull', lambda: command('add', 'ollama', '--name', 'qwen3:0.6b'))
    check('hf-invalid-file-rejected', lambda: command('add', 'llamacpp', '--repo', 'unsloth/Qwen3-0.6B-GGUF',
                                                      '--file', 'not-present.gguf', success=False))
    for model in (llama, ollama):
        check(model['backend'] + '-select', lambda: command('select', model['key'], '--set', 'context=32768',
                                                          '--set', 'kv=q8_0', '--set', 'keep_alive=5m'))
        check(model['backend'] + '-catalog', catalog_metadata)
        check(model['backend'] + '-responses', inference)
        check(model['backend'] + '-native-function-call', native_tool_call)
        check(model['backend'] + '-codex-cli', codex_exec)
        try:
            from maa_testing.codex_ui import picker
        except ImportError:
            from codex_ui import picker
        check(model['backend'] + '-codex-model-picker', lambda: picker(LOCAL, model['name']))
    check('ollama-resident-entry-reuses-alias', ollama_entry_reuse)
    check('ollama-expired-entry-wakes-existing-alias', lambda: ollama_entry_reuse(True))
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
        with invalid_fixture() as bad:
            error = command('select', bad['key'], success=False)
            state = command('status')
            assert state['running'] and state['selected']['model']['key'] == ollama['key'], state
            return error
    check('native-load-failure-rollback', rollback)
    def cleaned():
        rows = command('models', 'llamacpp')
        removed = [row['key'] for row in REPORT['cleanup'] if row.get('fixture') == 'bad-native.gguf']
        assert not any(row['key'] in removed for row in rows)
        return {'cleaned': True}
    check('invalid-fixture-cleaned', cleaned)
    check('yolo-off', lambda: command('yolo', 'off'))
    check('yolo-on', lambda: command('yolo', 'on'))
    command('pause', structured=False)


def run():
    try:
        main()
    finally:
        try:
            command('pause', structured=False)
            REPORT['cleanup'].append({'selected_target_paused': True})
        except Exception as exc:
            REPORT['cleanup'].append({'selected_target_paused': False, 'error': str(exc)})
        REPORT['finished'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report = Path.home() / ('maa-native-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.json')
        report.write_text(json.dumps(REPORT, ensure_ascii=False, indent=2) + '\n')
        print('报告：' + str(report), flush=True)


if __name__ == '__main__':
    run()
