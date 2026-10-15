"""Project user preferences; independent from models, Codex and IM state."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
from .store import Error, atomic

LANGUAGES = ('zh_cn', 'en_us')
LABELS = {'zh_cn': '简体中文 (zh_cn)', 'en_us': 'English (en_us)'}
DEFAULT_LANGUAGE = 'zh_cn'
override = ContextVar('maa_language', default=None)


def path():
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'my-ai-agent/config.json'


def load():
    if path().is_symlink():
        raise Error('Language configuration must not be a symbolic link: {v0}', v0=path())
    try:
        value = json.loads(path().read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise Error('Cannot read language configuration {v0}: {v1}', v0=path(), v1=exc) from exc
    if not isinstance(value, dict) or value.get('language', DEFAULT_LANGUAGE) not in LANGUAGES:
        raise Error('Invalid language configuration: {v0}', v0=path())
    return value


def language():
    if override.get():
        return override.get()
    try:
        return load().get('language', DEFAULT_LANGUAGE)
    except Error:
        return DEFAULT_LANGUAGE  # Report a broken file without recursive errors.


def set_language(selected):
    if selected not in LANGUAGES:
        raise Error('Language must be zh_cn or en_us')
    value = load()
    value['language'] = selected
    atomic(path(), json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return selected


@contextmanager
def using(selected):
    token = override.set(selected)
    try:
        yield
    finally:
        override.reset(token)


def choose(ui, current=None):
    from .i18n import t
    return ui.choose(t('language_title'), [(value, LABELS[value]) for value in LANGUAGES],
                     default=current or DEFAULT_LANGUAGE, radio=True, cancel='cancel')


def installation_language(selected=None):
    selected = selected or os.environ.get('MAA_LANGUAGE')
    if selected is not None:
        if selected not in LANGUAGES:
            raise Error('Language must be zh_cn or en_us')
        load()  # A supplied value must not silently overwrite corrupt settings.
        return selected
    saved = load().get('language')
    if saved:
        return saved
    from . import menu
    try:
        return menu.interactive(choose)
    except OSError as exc:
        raise Error('No saved language and no controlling terminal; use --language zh_cn or --language en_us') from exc
