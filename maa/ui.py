"""Task-oriented menus call the same Manager operations as CLI."""
import json
import subprocess
from . import __version__, codex, install, menu
from .i18n import t
from .manager import Manager
from .output import say, operation
from .settings import DEFAULTS, KV, KEEP, EFFORT, settings
from .store import Error


def choose(ui, title, options, default=None):
    if default is None and options:
        default = options[0][0]
    result = ui.choose(title, options + [(None, t('back'))], default=default)
    if result is None:
        raise menu.Cancelled
    return result


def backend(ui):
    return choose(ui, t('backend'), [('ollama', 'Ollama'), ('llamacpp', 'llama.cpp')])


def edit_settings(ui, model, values):
    values = dict(values)
    focused = 'context'
    while True:
        options = []
        for key in DEFAULTS:
            value = values[key]
            label = t('unavailable') if key == 'mtp' and not model['mtp_supported'] else (
                t('on' if value else 'off') if isinstance(value, bool) else t(value) if value in ('follow', 'default') else str(value))
            options.append((key, t(key) + '：' + label))
        action = choose(ui, t('configure'), options + [('apply', t('apply'))], focused)
        focused = action
        if action == 'apply':
            return values
        if action in ('context', 'reserve_mib'):
            value = ui.input(t('integer', label=t(action), constraint=t('positive' if action == 'context' else 'nonnegative'),
                               value=values[action]))
            if not value:
                continue
            try:
                change = int(value)
            except ValueError:
                say(t('error', error='请输入整数。'))
                continue
        elif action in ('flash_attention', 'fit', 'mtp'):
            if action == 'mtp' and not model['mtp_supported']:
                say(t('unavailable'))
                continue
            change = choose(ui, t(action), [(True, t('on')), (False, t('off'))], values[action])
        else:
            choices = KV if action == 'kv' else ('follow',) + KV if action == 'mtp_kv' else KEEP if action == 'keep_alive' else EFFORT
            change = choose(ui, t(action), [(v, t(v) if v in ('default', 'follow') else v) for v in choices], values[action])
        try:
            values = settings(values, {action: change}, model['mtp_supported'])
        except Error as exc:
            say(t('error', error=exc))


def configure(ui, manager):
    current = manager.store.selected()
    if not current:
        raise Error(t('no_target'))
    manager.configure(edit_settings(ui, current['model'], current['settings']))


def select_model(ui, manager, key):
    model = manager.store.model(key)
    saved = manager.store.path('configs') / (key + '.json')
    values = edit_settings(ui, model, manager.config(model)) if not saved.exists() else None
    manager.select(key, values)


def add_model(ui, manager):
    selected = backend(ui)
    sources = [('official', t('official')), ('local', t('local'))] if selected == 'ollama' else [('hf', t('hf')), ('local', t('local'))]
    source = choose(ui, t('source'), sources)
    if selected == 'ollama':
        name = ui.input(t('model_name'))
        path = ui.input(t('path')) if source == 'local' else None
        row = manager.add_model(selected, name=name, path=path)
    elif source == 'hf':
        repo, filename = ui.input(t('repo')), ui.input(t('filename'))
        row = manager.add_model(selected, repo=repo, filename=filename)
    else:
        row = manager.add_model(selected, path=ui.input(t('path')))
    say(row['name'] + ' — ' + t('done'))


def main(ui):
    manager, focused = Manager(), 'select'
    actions = ('install', 'add', 'select', 'configure', 'pause', 'start', 'yolo', 'status', 'about', 'exit')
    while True:
        selected = manager.store.selected()
        title = t('title')
        if selected:
            title += '\n' + t('current', backend=selected['model']['backend'], model=selected['model']['name'],
                                status=t('running' if manager.controller.running() else 'stopped'))
        try:
            try:
                focused = ui.choose(title, [(v, t(v)) for v in actions], default=focused, cancel='exit')
            except menu.Cancelled:
                return
            if focused == 'exit':
                return
            ui.heading(t(focused))
            if focused == 'install':
                component = choose(ui, t('install'), [('all', '全部安装'), ('ollama', 'Ollama'),
                                                      ('llamacpp', 'llama.cpp'), ('codex', 'Codex CLI')])
                with operation(t('install')), manager.store.lock(), manager.maintenance():
                    install.component(component)
                say(t('done'))
            elif focused == 'add':
                add_model(ui, manager)
            elif focused == 'select':
                selected_backend = backend(ui)
                rows = manager.inventory(selected_backend)
                if not rows:
                    say(t('empty'))
                    continue
                key = choose(ui, t('ollama_model_title' if selected_backend == 'ollama' else 'model_title'),
                             [(row['key'], row['name']) for row in rows])
                select_model(ui, manager, key)
                say(t('done'))
            elif focused == 'configure':
                configure(ui, manager)
                say(t('done'))
            elif focused == 'pause':
                manager.pause()
                say(t('done'))
            elif focused == 'start':
                manager.start()
                say(t('done'))
            elif focused == 'yolo':
                enabled = choose(ui, t('yolo'), [(True, t('on')), (False, t('off'))], codex.yolo_state()['enabled'])
                with operation(t('yolo')):
                    codex.yolo(enabled)
                say(t('done'))
            elif focused == 'status':
                with operation(t('status')):
                    result = manager.status()
                say(json.dumps(result, ensure_ascii=False, indent=2))
            elif focused == 'about':
                say('my-ai-agent / maa ' + __version__)
            choose(ui, t('result'), [])
        except menu.Cancelled:
            if focused == 'exit':
                return
        except (Error, OSError, ValueError, subprocess.SubprocessError) as exc:
            say(t('error', error=exc))


def run():
    menu.interactive(main)
