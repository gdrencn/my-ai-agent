"""Native backend launch/configuration and runtime observation."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.parse import urlparse
from .http import request
from .settings import draft_kv, duration
from .store import Error


def binary(name):
    path = shutil.which(name)
    if not path:
        candidate = Path.home() / '.local/bin' / name
        path = str(candidate) if candidate.is_file() else None
    if not path:
        raise Error(f'{name} is not installed; use maa install')
    return path


def llama_command():
    try:
        return [binary('llama'), 'serve']
    except Error:
        return [binary('llama-server')]


def native_environment():
    # Inherited LLAMA_ARG_* must not covertly override saved settings, including
    # the deliberately unmanaged native speculative candidate default.
    managed = {'LLAMA_ARG_CTX_SIZE', 'LLAMA_ARG_CACHE_TYPE_K', 'LLAMA_ARG_CACHE_TYPE_V',
               'LLAMA_ARG_FLASH_ATTN', 'LLAMA_ARG_FIT', 'LLAMA_ARG_FIT_TARGET',
               'LLAMA_ARG_SPEC_TYPE', 'LLAMA_ARG_SPEC_DRAFT_CACHE_TYPE_K', 'LLAMA_ARG_SPEC_DRAFT_CACHE_TYPE_V',
               'LLAMA_ARG_SPEC_DRAFT_N_MAX', 'LLAMA_ARG_SPEC_DRAFT_N_MIN', 'LLAMA_ARG_DRAFT_MAX', 'LLAMA_ARG_DRAFT_MIN',
               'LLAMA_ARG_N_PARALLEL'}
    return {key: value for key, value in os.environ.items() if key not in managed}


def llama_endpoint():
    host = os.environ.get('LLAMA_ARG_HOST', '127.0.0.1')
    if host in ('0.0.0.0', '::'):
        host = '127.0.0.1'
    return f'http://{host}:{os.environ.get("LLAMA_ARG_PORT", "8080")}'


def ollama_endpoint():
    host = os.environ.get('OLLAMA_HOST', '127.0.0.1:11434')
    parsed = urlparse(host if '://' in host else 'http://' + host)
    address = parsed.hostname or '127.0.0.1'
    if address in ('0.0.0.0', '::'):
        address = '127.0.0.1'
    return f'http://{address}:{parsed.port or 11434}'


def ollama_environment(values=None):
    env = native_environment()
    if values:
        env.update(OLLAMA_CONTEXT_LENGTH=str(values['context']),
                   OLLAMA_KV_CACHE_TYPE=values['kv'],
                   OLLAMA_FLASH_ATTENTION='1' if values['flash_attention'] else '0',
                   OLLAMA_KEEP_ALIVE=values['keep_alive'],
                   LLAMA_ARG_FIT='on' if values['fit'] else 'off',
                   LLAMA_ARG_FIT_TARGET=str(values['reserve_mib']),
                   LLAMA_ARG_SPEC_DRAFT_CACHE_TYPE_K=draft_kv(values),
                   LLAMA_ARG_SPEC_DRAFT_CACHE_TYPE_V=draft_kv(values))
    return env


def ollama_capabilities():
    candidates = [Path('/usr/lib/ollama/llama-server'), Path('/usr/local/lib/ollama/llama-server')]
    candidates.extend(Path('/usr/lib/ollama').glob('**/llama-server'))
    for path in candidates:
        if path.is_file():
            proc = subprocess.run([str(path), '--help'], text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, timeout=30)
            if proc.returncode == 0:
                return proc.stdout
    raise Error('This Ollama runner does not expose the required llama-server fit/draft options. '
                'Install the current official Ollama version; legacy runners cannot apply this configuration.')


def check_options(help_text, options):
    missing = [option for option in options if option not in help_text]
    if missing:
        raise Error('Installed backend does not support: ' + ', '.join(missing))


def llama_arguments(model, values):
    command = llama_command()
    help_result = subprocess.run(command + ['--help'], capture_output=True, text=True, timeout=30)
    help_text = help_result.stdout + help_result.stderr
    if help_result.returncode:
        raise Error(help_text)
    check_options(help_text, ['--fit', '--fit-target', '--cache-type-k', '--cache-type-v',
                             '--flash-attn', '--sleep-idle-seconds', '--spec-type'])
    if values['mtp']:
        check_options(help_text, ['draft-mtp', '--spec-draft-type-k', '--spec-draft-type-v'])
    args = command + ['--model', model['path'], '--alias', model['key'],
                      '--parallel', '1',  # One local-agent slot; context is per conversation.
                      '--ctx-size', str(values['context']),
                      '--cache-type-k', values['kv'], '--cache-type-v', values['kv'],
                      '--flash-attn', 'on' if values['flash_attention'] else 'off',
                      '--fit', 'on' if values['fit'] else 'off', '--fit-target', str(values['reserve_mib']),
                      '--sleep-idle-seconds', str(duration(values['keep_alive'])),
                      '--spec-type', 'draft-mtp' if values['mtp'] else 'none']
    if values['mtp']:
        args += ['--spec-draft-type-k', draft_kv(values), '--spec-draft-type-v', draft_kv(values)]
    # No candidate override, GPU layers, sampling, or template overrides.
    return args


def wait_api(url, process, timeout=180):
    end = time.monotonic() + timeout
    last = ''
    while time.monotonic() < end:
        if process.poll() is not None:
            raise Error(f'Native backend exited with code {process.returncode}; inspect maa logs')
        try:
            return request(url, timeout=2)
        except Error as exc:
            last = str(exc)
            time.sleep(.2)
    raise Error(f'Backend readiness timed out: {last}')


def ollama_load(target):
    endpoint, model, values = ollama_endpoint(), target['model'], target['settings']
    info = request(endpoint + '/api/show', {'model': model['name']}, timeout=60)
    inventory = request(endpoint + '/api/tags')['models']
    entry = next((row for row in inventory if row['name'] == model['name']), None)
    if entry is None or entry.get('digest') != model.get('digest'):
        raise Error('Ollama model tag changed; refresh maa models and select the current model again')
    params = {'num_ctx': values['context']}
    if model['mtp_supported']:
        preset = re.search(r'^\s*draft_num_predict\s+(\d+)', info.get('parameters', ''), re.M)
        candidates = int(preset.group(1)) if preset else 0
        params['draft_num_predict'] = (candidates or 4) if values['mtp'] else 0
    alias = 'maa-' + model['key'] + ':latest'
    request(endpoint + '/api/create', {'model': alias, 'from': model['name'],
                                      'parameters': params, 'stream': False}, timeout=600)
    request(endpoint + '/api/generate', {'model': alias, 'prompt': '', 'stream': False,
                                        'keep_alive': values['keep_alive']}, timeout=600)
    result = ollama_observe(alias)
    result['preset_parameters'] = info.get('parameters', '')
    return result


def ollama_observe(alias):
    for model in request(ollama_endpoint() + '/api/ps')['models']:
        if model.get('name') == alias or model.get('model') == alias:
            context = model.get('context_length')
            if type(context) is not int or context <= 0:
                raise Error('Ollama /api/ps did not report effective context_length')
            return {'model': alias, 'context': context, 'upstream': ollama_endpoint(),
                    'resources': {k: model.get(k) for k in ('size', 'size_vram', 'expires_at')}}
    raise Error('Selected Ollama model is not loaded (it may have expired); start it again')


def llama_observe(key, endpoint=None):
    endpoint = endpoint or llama_endpoint()
    props = request(endpoint + '/props')
    # Sleep preserves configuration; generation wakes the model automatically.
    context = props.get('default_generation_settings', {}).get('n_ctx')
    if not context:
        slots = request(endpoint + '/slots')
        context = slots[0].get('n_ctx') if slots else None
    if type(context) is not int or context <= 0:
        raise Error('llama.cpp did not report effective per-slot n_ctx')
    return {'model': key, 'context': context, 'upstream': endpoint,
            'resources': {'sleeping': props.get('is_sleeping', False),
                          'total_slots': props.get('total_slots'), 'model_path': props.get('model_path')}}


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
