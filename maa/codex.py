"""Lossless two-key YOLO recovery and isolated local-model profiles."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).parent / '_vendor'))
import tomlkit
from .store import Error, atomic, read, write

YOLO = {'approval_policy': 'never', 'sandbox_mode': 'danger-full-access'}


def home():
    return Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex')


def parse(text):
    try:
        return tomlkit.parse(text)
    except Exception as exc:
        raise Error(f'Invalid Codex TOML: {exc}') from exc


@contextmanager
def lock():
    root = home()
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.maa-config.lock').open('a') as out:
        fcntl.flock(out, fcntl.LOCK_EX)
        yield root


def yolo(enable):
    with lock() as root:
        config, backup = root / 'config.toml', root / 'maa-yolo-recovery.json'
        text = config.read_text() if config.exists() else ''
        document = parse(text)
        saved = read(backup)
        if enable:
            if saved is None:
                saved = {'version': 1, 'values': {}}
                for key in YOLO:
                    saved['values'][key] = {'exists': key in document,
                                             'toml': tomlkit.dumps({key: document[key]}) if key in document else ''}
                write(backup, saved)  # Durable recovery precedes the first mutation.
            for key, value in YOLO.items():
                document[key] = value
        elif saved is not None:
            for key in YOLO:
                item = saved['values'][key]
                if item['exists']:
                    document[key] = parse(item['toml'])[key]
                else:
                    document.pop(key, None)
        else:
            return
        atomic(config, tomlkit.dumps(document))
        if not enable:
            backup.unlink(missing_ok=True)


def yolo_state():
    path = home() / 'config.toml'
    doc = parse(path.read_text() if path.exists() else '')
    return {'enabled': all(doc.get(k) == v for k, v in YOLO.items()),
            'managed': (home() / 'maa-yolo-recovery.json').exists()}


def profile_path():
    return home() / 'maa-local.config.toml'


def catalog_path(runtime):
    # Immutable model/context entries let profile replacement select a complete
    # catalog atomically, including when a switch subsequently rolls back.
    import hashlib
    entry = catalog(runtime)
    blob = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(blob.encode()).hexdigest()
    return home() / 'maa-model-catalogs' / (digest + '.json'), blob


def catalog(runtime):
    from .settings import EFFORT
    context = runtime['context']
    model = {
        'slug': runtime.get('display_name', runtime['model']), 'display_name': runtime.get('display_name', runtime['model']),
        'description': 'Local model selected by my-ai-agent; native reasoning support varies.',
        'default_reasoning_level': None,
        'supported_reasoning_levels': [{'effort': value, 'description': 'Passed unchanged to the local backend.'}
                                       for value in EFFORT if value != 'default'],
        'shell_type': 'shell_command', 'visibility': 'list', 'supported_in_api': True, 'priority': 0,
        'base_instructions': ('You are Codex, a coding agent running with a local model. '
                              'Follow the user request and applicable project instructions. '
                              'Use the provided tools and their schemas to inspect, edit and verify work. '
                              'Report actual tool results accurately; do not claim unperformed checks. '
                              'The local model serving this session is ' +
                              json.dumps(runtime.get('display_name', runtime['model']), ensure_ascii=False) +
                              '. Use this model name when identifying the local model; '
                              'internal routing aliases are not model names.'),
        'include_skills_usage_instructions': True, 'include_plugin_usage_instructions': True,
        'include_apps_usage_instructions': True, 'supports_reasoning_summary_parameter': False,
        'default_reasoning_summary': 'none', 'support_verbosity': False, 'default_verbosity': None,
        'apply_patch_tool_type': 'freeform', 'web_search_tool_type': 'text',
        'truncation_policy': {'mode': 'tokens', 'limit': 10000},
        'supports_image_detail_original': False, 'context_window': context,
        'max_context_window': context, 'auto_compact_token_limit': context * 90 // 100,
        'effective_context_window_percent': 100, 'experimental_supported_tools': [],
        'input_modalities': ['text'], 'supports_search_tool': False,
        'supports_experimental_context': False, 'use_responses_lite': False,
        'supports_reasoning_effort_updates': True,
    }
    return {'models': [model]}


def profile(runtime, settings):
    context = runtime['context']
    if type(context) is not int or context < 1:
        raise Error('Native backend did not report a valid effective context')
    doc = tomlkit.document()
    doc.add(tomlkit.comment('Managed by my-ai-agent. Global permissions and web_search are inherited.'))
    doc['model'] = runtime.get('display_name', runtime['model'])
    doc['model_provider'] = 'maa_local'
    doc['model_context_window'] = context
    doc['model_auto_compact_token_limit'] = context * 90 // 100
    path, catalog_json = catalog_path(runtime)
    doc['model_catalog_json'] = str(path)
    if settings['reasoning'] != 'default':
        doc['model_reasoning_effort'] = settings['reasoning']
    doc['model_providers'] = {'maa_local': {'name': 'my-ai-agent local',
                             'base_url': runtime['base_url'], 'wire_api': 'responses',
                             'requires_openai_auth': False}}
    parse(tomlkit.dumps(doc))
    with lock():
        if profile_path().exists() and not profile_path().read_text().startswith('# Managed by my-ai-agent.'):
            raise Error('maa-local.config.toml already exists and is not owned by maa; refusing to overwrite it')
        if path.exists() and path.read_text() != catalog_json:
            raise Error('Local model catalog was modified; refusing to overwrite it')
        if not path.exists():
            atomic(path, catalog_json)
        atomic(profile_path(), tomlkit.dumps(doc))


def executable():
    value = shutil.which('codex') or str(Path.home() / '.local/bin/codex')
    if not Path(value).is_file():
        raise Error('Codex CLI is not installed; run maa install codex')
    return value
