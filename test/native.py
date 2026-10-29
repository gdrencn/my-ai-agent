"""Full installed functional acceptance, independent of environment origin."""
import datetime
from contextlib import contextmanager
import json
import os
import stat
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
sys.path.insert(0, str(Path.home() / '.local/share/my-ai-agent/maa.pyz'))
from maa import __version__
from maa.store import Store, read, write
from maa.processes import run as run_owned

MAA = str(Path.home() / '.local/bin/maa')
LOCAL = str(Path.home() / '.local/bin/codex-local')
REPORT = {'version': __version__, 'started': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'checks': [], 'cleanup': []}
PERMISSIONS = None


@contextmanager
def codex_home(path):
    previous = os.environ.get('CODEX_HOME')
    os.environ['CODEX_HOME'] = str(path)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop('CODEX_HOME', None)
        else:
            os.environ['CODEX_HOME'] = previous


def permission_command(*args, **kwargs):
    with codex_home(PERMISSIONS):
        return command(*args, **kwargs)


def permission_state():
    from maa import codex
    from maa.agent_status import configuration
    with codex_home(PERMISSIONS):
        actual = configuration()
        path = PERMISSIONS / 'config.toml'
        document = codex.parse(path.read_text() if path.exists() else '')
        expected = {key: document.get(key) for key in codex.YOLO}
        assert actual == expected, (actual, expected)
    return actual


def permission_change(enabled):
    from maa import codex
    with codex_home(PERMISSIONS):
        backup = read(PERMISSIONS / 'maa-yolo-recovery.json')
    expected = dict(codex.YOLO) if enabled else {
        key: codex.parse(item['toml']).get(key) if item['exists'] else None
        for key, item in backup['values'].items()}
    state = permission_command('yolo', 'on' if enabled else 'off')
    actual = permission_state()
    assert actual == expected, (actual, expected)
    assert state['managed'] == enabled, state
    return {'agent_configuration': actual, 'managed': state['managed'], 'confirmation_probe': False}


def permission_profile():
    from maa import codex
    store = Store()
    with codex_home(PERMISSIONS):
        codex.profile(read(store.path('runtime.json')), store.selected()['settings'])


@contextmanager
def client():
    from maa import codex
    # Exercise the profile actually committed by the configuration transaction.
    # Regenerating here would hide a wrong URL/provider/catalog in that file.
    profile = codex.profile_path().read_bytes()
    with tempfile.TemporaryDirectory(prefix='.maa-native-client-', dir=Path.home()) as folder:
        folder = Path(folder)
        with codex_home(folder / 'codex'):
            codex.home().mkdir(mode=0o700)
            # This is a private integration client, not a permission-state probe.
            (codex.home() / 'config.toml').write_text('approval_policy="never"\nsandbox_mode="danger-full-access"\n')
            (codex.home() / 'maa-local.config.toml').write_bytes(profile)
            yield folder


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
    runtime = read(Store().path('runtime.json'))
    body = {'model': runtime['model'], **body}
    req = urllib.request.Request(runtime['base_url'] + '/responses',
                                 data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=300).read()


def inference():
    result = json.loads(api({'input': 'Reply with the word hello.', 'max_output_tokens': 64,
                             'reasoning': {'effort': 'none'}}))
    assert result['status'] == 'completed' and result['output'], result
    assert result['model'] == command('status')['selected']['model']['name'], result
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
    with client() as folder:
        # Reproduce installation from an existing shell: the official installer
        # cannot add ~/.local/bin to this already-running process's PATH.
        env = dict(os.environ, PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin')
        result = run_owned([LOCAL, 'exec', '--skip-git-repo-check', '--ephemeral', '-C', str(folder),
                                 'Reply with MAA_NATIVE_OK. Do not use tools.'], capture_output=True,
                                text=True, timeout=600, stdin=subprocess.DEVNULL, env=env)
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip(), result.stderr
        assert 'fallback metadata' not in result.stderr and 'requires embedded mode' not in result.stderr, result.stderr
        return {'output': result.stdout, 'diagnostic': result.stderr[-8192:],
                'launcher_path_without_user_bin': env['PATH']}


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
    assert len(models) == 1 and models[0]['slug'] == state['selected']['model']['name'], models
    assert models[0]['display_name'] == state['selected']['model']['name'], models
    assert models[0]['context_window'] == state['runtime']['context'], models
    assert config['model'] == state['selected']['model']['name'], config
    return {'model': models[0]['slug'], 'display_name': models[0]['display_name'], 'context': models[0]['context_window']}


def model_status_native():
    state = command('status')
    snapshot = state['model_status']
    assert snapshot['state'] == 'running' and snapshot['model'] == state['selected']['model']['name'], snapshot
    assert snapshot['context'] == state['runtime']['context'], snapshot
    allocation = snapshot['allocations']
    assert allocation['load_id'] is not None, allocation
    devices = snapshot['gpu_memory']['devices']
    location = 'gpu' if devices else 'host'
    if devices:
        assert allocation['gpu_layers'], allocation
        assert devices[0]['free_mib'] is not None, snapshot
    for kind in ('model', 'KV', 'compute'):
        assert any(row['kind'] == kind and row['location'] == location for row in allocation['buffers']), allocation
    assert snapshot['usage'] is None and 'no maa conversation interceptor' in snapshot['usage_note'], snapshot
    again = command('status')['model_status']
    assert again['usage'] is None, 'Native status invented conversation usage'
    assert again['allocations']['load_id'] == allocation['load_id'], (snapshot, again)
    assert again['allocations']['gpu_identified_mib'] == allocation['gpu_identified_mib'], (snapshot, again)
    snapshot['acceptance'] = {'allocation_location': location,
                              'gpu_assertions': 'passed' if devices else 'unavailable; not verified'}
    return snapshot


def configuration_without_reload():
    from maa.service import Controller
    store, controller = Store(), Controller(Store())
    selected = store.selected()
    before = controller.unit_info()
    command('config', 'reasoning=none')
    command('config', 'reasoning=none')  # Unchanged apply is also inert.
    permission_change(False)
    permission_change(True)
    command('start')  # Already resident: no restart or inference.
    if selected['model']['backend'] == 'ollama':
        rows = command('models', 'ollama')
        assert any(row['key'] == selected['model']['key'] for row in rows), rows
    after = controller.unit_info()
    assert after['InvocationID'] == before['InvocationID'] and after['MainPID'] == before['MainPID'], (before, after)
    command('pause', structured=False)
    command('config', 'reasoning=default')
    state = command('status')
    assert not state['running'] and state['model_status']['saved_context'], state
    assert state['model_status']['state'] == 'paused', state
    command('start')
    assert controller.configuration_matches(store.selected())
    return {'resident_instance_unchanged': True, 'paused_configuration_did_not_wake': True,
            'saved_context': state['model_status']['saved_context'], 'before': before, 'after': after}


def ollama_start_idle_without_restart():
    from maa.service import Controller
    store, controller = Store(), Controller(Store())
    selected = store.selected()
    before = controller.unit_info()
    runtime = read(store.path('runtime.json'))
    manifest = catalog_metadata()
    req = urllib.request.Request(runtime['upstream'] + '/api/generate',
        data=json.dumps({'model': selected['model']['name'], 'keep_alive': 0}).encode(),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as response:
        response.read()
    assert command('status')['model_status']['state'] == 'idle'
    state = command('start')
    after = controller.unit_info()
    assert state['model_status']['state'] == 'running', state
    assert before['InvocationID'] == after['InvocationID'] and before['MainPID'] == after['MainPID'], (before, after)
    assert catalog_metadata() == manifest
    return {'native_instance_unchanged': True, 'woke_existing_model': True, 'before': before, 'after': after}


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
        idle = command('status')['model_status']
        assert idle['state'] == 'idle' and idle['allocations'] is None and idle['usage'] is None, idle
        assert not any(row['name'] == runtime['model'] for row in native_api('/api/ps')['models']), 'Status woke an idle model'
    started = time.monotonic()
    diagnostic = codex_exec()
    after = next(row for row in native_api('/api/tags')['models'] if row['name'] == runtime['model'])
    assert before['digest'] == after['digest'] and before['modified_at'] == after['modified_at'], (before, after)
    assert any(row['name'] == runtime['model'] for row in native_api('/api/ps')['models'])
    return {'native_tag_unchanged': True, 'woke': wake, 'elapsed_seconds': round(time.monotonic() - started, 3),
            'diagnostic': diagnostic['diagnostic']}


def main():
    cleanup_legacy_fixture()
    def yolo_baseline():
        state = permission_change(True)
        return {'private_configuration': state, 'agent_configuration': permission_state(),
                'user_configuration_changed': False, 'confirmation_probe': False}
    check('explicit-yolo-test-baseline', yolo_baseline)
    llama = check('hf-exact-download', lambda: command('add', 'llamacpp', '--repo', 'unsloth/Qwen3-0.6B-GGUF',
                                                       '--file', 'Qwen3-0.6B-Q4_K_M.gguf'))
    ollama = check('ollama-native-pull', lambda: command('add', 'ollama', '--name', 'qwen2.5:3b'))
    check('hf-invalid-file-rejected', lambda: command('add', 'llamacpp', '--repo', 'unsloth/Qwen3-0.6B-GGUF',
                                                      '--file', 'not-present.gguf', success=False))
    def independent():
        archive = Path.home() / '.local/share/my-ai-agent/maa.pyz'
        detached = archive.with_suffix('.detached')
        archive.rename(detached)
        try:
            result = codex_exec()
            assert not Path('/etc/systemd/system/maa.service').exists()
            assert 'maa.pyz' not in Path(LOCAL).read_text()
            return {'archive_absent': True, 'codex': result}
        finally:
            detached.rename(archive)
    for model in (llama, ollama):
        check(model['backend'] + '-select', lambda: command('select', model['key'], '--set', 'context=32768',
                                                          '--set', 'kv=q8_0', '--set', 'keep_alive=5m'))
        check(model['backend'] + '-catalog', catalog_metadata)
        check(model['backend'] + '-responses', inference)
        check(model['backend'] + '-native-function-call', native_tool_call)
        check(model['backend'] + '-codex-cli', codex_exec)
        check(model['backend'] + '-manager-independent', independent)
        check(model['backend'] + '-model-status', model_status_native)
        check(model['backend'] + '-configuration-without-reload', configuration_without_reload)
        try:
            from maa_testing.codex_ui import picker
        except ImportError:
            from test.codex_ui import picker
        def model_picker():
            with client() as folder:
                return picker(LOCAL, model['name'], cwd=folder)
        check(model['backend'] + '-codex-model-picker', model_picker)
    check('ollama-resident-entry-reuses-alias', ollama_entry_reuse)
    check('ollama-expired-entry-wakes-existing-alias', lambda: ollama_entry_reuse(True))
    check('ollama-explicit-start-wakes-without-restart', ollama_start_idle_without_restart)
    def inventory_reuse():
        from maa.service import Controller
        store = Store()
        controller = Controller(store)
        before = controller.unit_info()
        first = command('models', 'ollama')
        registry = store.path('models.json').read_bytes()
        stat = store.path('models.json').stat()
        second = command('models', 'ollama')
        after = controller.unit_info()
        assert first == second
        assert store.path('models.json').read_bytes() == registry
        assert store.path('models.json').stat().st_mtime_ns == stat.st_mtime_ns
        assert before['MainPID'] == after['MainPID'] and before['InvocationID'] == after['InvocationID']
        return {'unchanged_registry_not_written': True, 'native_instance_unchanged': True}
    check('ollama-unchanged-inventory-reuses-registry', inventory_reuse)
    try:
        from maa_testing.codex_tool import main as tool_fixture
    except ImportError:
        from test.codex_tool import main as tool_fixture
    check('codex-direct-shell-and-result-replay', tool_fixture)
    def retained():
        command('pause', structured=False)
        state = command('status')
        assert not state['running'] and state['selected']['model']['key'] == ollama['key']
        assert state['model_status']['state'] == 'paused' and state['model_status']['allocations'] is None, state
        state = command('start')
        assert state['running'] and state['selected']['model']['key'] == ollama['key']
        return state
    check('pause-start-retains-target', retained)
    def recovery():
        from maa.service import Controller
        store = Store()
        accepted = store.selected()
        command('pause', structured=False)
        candidate = {'model': llama, 'settings': accepted['settings']}
        write(store.path('target.json'), candidate)
        write(store.path('pending.json'), candidate)
        state = command('start')
        assert state['running'] and state['selected'] == accepted, state
        assert store.target() == accepted and not store.path('pending.json').exists()
        info = Controller(store).unit_info(candidate)
        assert info['ActiveState'] == 'inactive', info
        return {'injected_uncommitted_target': True, 'accepted_native_backend_restored': True,
                'candidate_backend_not_started': True}
    check('interrupted-candidate-restores-accepted-native-target', recovery)
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
    check('yolo-off', lambda: permission_change(False))
    def upgrade_yolo():
        from maa import codex
        from maa.service import Controller
        controller = Controller(Store())
        before = controller.unit_info()
        actual_profile = codex.profile_path()
        permission_profile()
        paths = [PERMISSIONS / 'config.toml', PERMISSIONS / 'maa-yolo-recovery.json',
                 PERMISSIONS / 'maa-local.config.toml', actual_profile]
        saved = {path: path.read_bytes() if path.exists() else None for path in paths}
        result = permission_command('_install', '--components', 'none', structured=False)
        # Also exercise reinstallation in the real configured home. The private
        # off-state check must not replace this original profile-preservation path.
        real_paths = [codex.home() / name for name in ('config.toml', 'maa-yolo-recovery.json')]
        real_saved = {path: path.read_bytes() if path.exists() else None for path in real_paths}
        result += command('_install', '--components', 'none', structured=False)
        assert real_saved == {path: path.read_bytes() if path.exists() else None for path in real_paths}
        after = controller.unit_info()
        assert saved == {path: path.read_bytes() if path.exists() else None for path in paths}
        assert not permission_command('status')['yolo']['managed']
        permission_state()
        assert before['MainPID'] == after['MainPID'] and before['InvocationID'] == after['InvocationID']
        return {'global_config_and_recovery_unchanged': True, 'profile_and_native_instance_unchanged': True,
                'real_home_and_private_off_reinstall_both_executed': True,
                'diagnostic': result}
    check('product-reinstall-retains-yolo-off-and-native-instance', upgrade_yolo)
    check('yolo-on', lambda: permission_change(True))
    command('pause', structured=False)


def run(product=None):
    global REPORT, PERMISSIONS
    from maa import codex
    try:
        from maa_testing.installed import run as installed
        from maa_testing.coverage import NATIVE_BASELINE, INSTALLED_ADDITIONS
    except ImportError:
        from test.installed import run as installed
        from test.coverage import NATIVE_BASELINE, INSTALLED_ADDITIONS
    REPORT = {'version': __version__, 'kind': 'complete installed functional acceptance',
              'started': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'checks': [], 'cleanup': [], 'status': 'failed'}
    report_path = Path.home() / ('maa-native-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.json')
    paths = [codex.home() / name for name in ('config.toml', 'maa-yolo-recovery.json')]
    def snapshot():
        return {path: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) if path.exists() else None for path in paths}
    before = snapshot()
    started = False
    try:
        installed(product, report=REPORT, write_report=False)
        REPORT['status'] = 'failed'  # The read-only phase is only part of acceptance.
        from maa.backends import binary
        for tool in ('codex', 'ollama', 'llama'):
            binary(tool)
        with tempfile.TemporaryDirectory(prefix='.maa-native-permissions-', dir=Path.home()) as folder:
            PERMISSIONS = Path(folder) / 'codex'
            PERMISSIONS.mkdir(mode=0o700)
            original = codex.parse(paths[0].read_text() if paths[0].exists() else '')
            # Copy only the two public permission fields; no auth, plugins or instructions.
            text = ''.join(json.dumps(key) + '=' + json.dumps(str(original[key])) + '\n'
                           for key in codex.YOLO if key in original)
            (PERMISSIONS / 'config.toml').write_text(text)
            started = True
            main()
        PERMISSIONS = None
        check('user-permissions-retained', lambda: assert_permissions(before, snapshot()))
        completed = {row['name'] for row in REPORT['checks'] if row['status'] == 'passed'}
        required = NATIVE_BASELINE + INSTALLED_ADDITIONS
        missing = sorted(set(required) - completed)
        assert not missing, 'Missing acceptance coverage: ' + ', '.join(missing)
        REPORT['coverage'] = {'baseline': 'stable/0.1.9', 'baseline_checks': len(NATIVE_BASELINE),
                              'retained': sorted(set(NATIVE_BASELINE) & completed), 'missing': missing,
                              'added': sorted(completed - set(NATIVE_BASELINE))}
        REPORT['status'] = 'passed'
        return REPORT
    finally:
        PERMISSIONS = None
        try:
            if started:
                command('pause', structured=False)
                REPORT['cleanup'].append({'test_target_paused': True, 'private_homes_removed': True})
            assert_permissions(before, snapshot())
        except BaseException as exc:
            REPORT['status'] = 'failed'
            REPORT['cleanup'].append({'status': 'failed', 'error': str(exc)})
            raise
        finally:
            if sys.exc_info()[0] is not None:
                REPORT['status'] = 'failed'
            REPORT['finished'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            write(report_path, REPORT)
            print('报告：' + str(report_path), flush=True)


def assert_permissions(before, after):
    assert before == after, 'Invoking user permission/recovery files changed'
    return {'config_and_recovery_bytes_and_modes_unchanged': True}


if __name__ == '__main__':
    run()
