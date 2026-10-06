"""Lossless two-key YOLO recovery and isolated local-model profiles."""
from contextlib import contextmanager
import fcntl
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


def profile(runtime, settings):
    context = runtime['context']
    if type(context) is not int or context < 1:
        raise Error('Native backend did not report a valid effective context')
    doc = tomlkit.document()
    doc.add(tomlkit.comment('Managed by my-ai-agent. Global permissions and web_search are inherited.'))
    doc['model'] = runtime['model']
    doc['model_provider'] = 'maa_local'
    doc['model_context_window'] = context
    doc['model_auto_compact_token_limit'] = context * 90 // 100
    if settings['reasoning'] != 'default':
        doc['model_reasoning_effort'] = settings['reasoning']
    doc['model_providers'] = {'maa_local': {'name': 'my-ai-agent local',
                             'base_url': runtime['base_url'], 'wire_api': 'responses',
                             'requires_openai_auth': False}}
    parse(tomlkit.dumps(doc))
    with lock():
        if profile_path().exists() and not profile_path().read_text().startswith('# Managed by my-ai-agent.'):
            raise Error('maa-local.config.toml already exists and is not owned by maa; refusing to overwrite it')
        atomic(profile_path(), tomlkit.dumps(doc))


def executable():
    value = shutil.which('codex') or str(Path.home() / '.local/bin/codex')
    if not Path(value).is_file():
        raise Error('Codex CLI is not installed; run maa install codex')
    return value
