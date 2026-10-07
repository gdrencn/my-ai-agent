"""Task-oriented menus call the same Manager operations as CLI."""
import datetime
import subprocess
from . import __version__, codex, install, menu
from .i18n import t
from .manager import Manager
from .output import say, operation
from .settings import DEFAULTS, KV, KEEP, EFFORT, settings
from .store import Error

MODEL_KEYS = tuple(key for key in DEFAULTS if key != 'reasoning')


def value_line(label, value, tone='cyan'):
    return menu.Rich((menu.Cell(label + '：'), menu.Cell(str(value), tone)))


def state_line(state):
    tone = 'green' if state == 'running' else 'gray' if state in ('paused', 'idle', 'unselected') else 'red' if state == 'error' else 'cyan'
    return value_line(t('run_state'), t('state_error' if state == 'error' else state), tone)


def setting_line(key, value, model):
    if key in ('mtp', 'mtp_kv') and not model['mtp_supported']:
        return value_line(t(key), t('unavailable'), 'gray')
    if isinstance(value, bool):
        return value_line(t(key), t('on' if value else 'off'), 'green' if value else 'gray')
    return value_line(t(key), t(value) if value in ('follow', 'default') else value)


def choose(ui, title, options, default=None):
    if default is None and options:
        default = options[0][0]
    result = ui.choose(title, options + [(None, t('back'))], default=default)
    if result is None:
        raise menu.Cancelled
    return result


def backend(ui):
    return choose(ui, t('backend'), [('ollama', 'Ollama'), ('llamacpp', 'llama.cpp')])


def edit_settings(ui, model, values, keys=MODEL_KEYS, title=None, readonly=()):
    values = dict(values)
    original, focused = dict(values), keys[0]
    while True:
        options = [(key, setting_line(key, values[key], model)) for key in keys]
        action = ui.choose(title or t('configure'), options + list(readonly) + [('apply', t('apply')), (None, t('back'))],
                           default=focused, description=[t('dirty' if values != original else 'applied')])
        if action is None:
            raise menu.Cancelled
        focused = action
        if action == 'apply':
            return values
        if action not in keys:
            continue  # Read-only inherited context/compaction fields have no editor.
        try:
            if action in ('mtp', 'mtp_kv') and not model['mtp_supported']:
                say(t('unavailable'))
                continue
            if action in ('context', 'reserve_mib'):
                value = ui.input(t('integer', label=t(action), constraint=t('positive' if action == 'context' else 'nonnegative'),
                                   value=values[action]))
                if not value:
                    continue
                change = int(value)
            elif action in ('flash_attention', 'fit', 'mtp'):
                change = choose(ui, t(action), [(True, t('on')), (False, t('off'))], values[action])
            else:
                choices = KV if action == 'kv' else ('follow',) + KV if action == 'mtp_kv' else KEEP if action == 'keep_alive' else EFFORT
                change = choose(ui, t(action), [(v, t(v) if v in ('default', 'follow') else v) for v in choices], values[action])
            values = settings(values, {action: change}, model['mtp_supported'])
        except menu.Cancelled:
            continue
        except (Error, ValueError) as exc:
            say(t('error', error=exc))


def configure(ui, manager, codex_only=False):
    current = manager.store.selected()
    if not current:
        raise Error(t('no_target'))
    readonly = []
    if codex_only:
        observed = manager.model_status(include_gpu=False)
        context = observed['context']
        readonly = [('context_readonly', value_line(t('context_readonly'), f'{context} tokens' if context else t('unknown'))),
                    ('compact_readonly', value_line(t('compact_readonly'), f'{context * 90 // 100} tokens' if context else t('unknown')))]
    manager.configure(edit_settings(ui, current['model'], current['settings'],
                                    keys=('reasoning',) if codex_only else MODEL_KEYS,
                                    title=t('codex_config' if codex_only else 'configure'), readonly=readonly))


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


def status_lines(status):
    rows = [value_line(t('base_label'), {'ollama': 'Ollama', 'llamacpp': 'llama.cpp'}.get(status['backend'], t('unselected'))),
            value_line(t('current_model'), status['model'] or t('unselected')), state_line(status['state'])]
    if status.get('error'):
        rows.append(value_line('诊断', status['error'], 'red'))
    snapshot = status.get('allocations') or {}
    layers = snapshot.get('gpu_layers')
    rows.append(value_line(t('gpu_layers'), f'{layers[0]}/{layers[1]} 层（{layers[0]*100/layers[1]:.1f}%）' if layers else t('unknown')))
    def memory(kind, phase=None):
        found = [row for row in snapshot.get('buffers', []) if row['kind'] == kind and (phase is None or row['phase'] == phase)]
        if not found:
            return t('not_applicable') if kind == 'RS' and snapshot.get('rs_sequences') == 0 else t('unknown')
        grouped = {}
        for row in found:
            label = ('系统内存映射' if row['backend'] == 'CPU_Mapped' else
                     '系统内存 ' + row['backend'] if row['location'] == 'host' else 'GPU ' + row['backend'])
            label += ' / MTP' if row['phase'] == 'mtp' else ''
            grouped[label] = grouped.get(label, 0) + row['mib']
        return '；'.join(f'{key} {value:.2f} MiB' for key, value in grouped.items())
    for label, kind, phase in [('weights', 'model', 'main'), ('main_kv', 'KV', 'main'),
                               ('rs', 'RS', None), ('compute', 'compute', 'main'), ('output_buffer', 'output', None)]:
        rows.append(value_line(t(label), memory(kind, phase)))
    for label, kind in [('mtp_kv_status', 'KV'), ('mtp_compute', 'compute')]:
        mode = status['mtp']
        value = t('mtp_unavailable' if mode == 'unavailable' else 'not_enabled') if mode != 'on' else memory(kind, 'mtp')
        if mode == 'on' and kind == 'KV' and snapshot.get('mtp_shared_kv'):
            value = t('shared') + ('；额外分配 ' + value if value != t('unknown') else '')
        rows.append(value_line(t(label), value, 'gray' if mode != 'on' else 'cyan'))
    total = snapshot.get('gpu_identified_mib')
    rows.append(value_line(t('gpu_sum'), f'{total:.2f} MiB' if total is not None else t('unknown')))
    if snapshot.get('error'):
        rows.append(value_line('分配记录', snapshot['error'], 'gray'))
    rows.append(t('memory_note'))
    gpu = status.get('gpu_memory', {})
    for device in gpu.get('devices', []):
        def amount(key):
            return f'{device[key]:.0f} MiB' if device.get(key) is not None else t('unknown')
        rows.append(value_line(t('gpu_memory') + ' ' + device['index'] + ' / ' + device['name'],
                               '总量 ' + amount('total_mib') + '；已用 ' + amount('used_mib') +
                               '；可用 ' + amount('free_mib') + '；驱动预留 ' + amount('reserved_mib')))
    if gpu.get('error'):
        rows.append(value_line(t('gpu_memory'), t('unknown') + '：' + gpu['error'], 'gray'))
    rows.append(t('gpu_note'))
    context, usage = status.get('context'), status.get('usage') or {}
    rows.append(value_line(t('effective_context'), f'{context} tokens' if context else t('unknown')))
    tokens = usage.get('input_tokens')
    occupied = f'{tokens} / {context} tokens（{tokens*100/context:.1f}%）' if tokens is not None and context else t('unknown')
    rows.append(value_line(t('context_input'), occupied))
    output = usage.get('output_tokens')
    rows.append(value_line(t('last_output'), f'{output} tokens' if output is not None else t('unknown')))
    when = usage.get('recorded_at')
    rows.append(value_line(t('statistics_time'), datetime.datetime.fromtimestamp(when).astimezone().isoformat(timespec='seconds') if when else t('unknown')))
    if status.get('usage_note'):
        rows.append('直连模式：底座未提供可核验的最近请求 token 统计；未取得的字段不估算。')
    return rows


def model_status(ui, manager):
    while True:
        with operation(t('model_status')):
            status = manager.model_status()
        action = ui.choose(t('model_status'), [('refresh', t('refresh')), (None, t('back'))],
                           default=None, description=status_lines(status))
        if action is None:
            return


def global_settings(ui):
    while True:
        enabled = codex.yolo_state()['enabled']
        action = ui.choose(t('codex_global'), [('yolo', value_line(t('yolo'), t('on' if enabled else 'off'), 'green' if enabled else 'gray')),
                                             (None, t('back'))], default='yolo')
        if action is None:
            return
        try:
            value = choose(ui, t('yolo'), [(True, t('on')), (False, t('off_restore'))], enabled)
            with operation(t('yolo')):
                codex.yolo(value)
            say(t('done'))
        except menu.Cancelled:
            continue


def local_models(ui, manager):
    focused = 'select'
    actions = ('select', 'add', 'configure', 'model_status', 'pause', 'start')
    while True:
        try:
            action = ui.choose(t('models_menu'), [(key, t(key)) for key in actions] + [(None, t('back'))], default=focused)
        except menu.Cancelled:
            return
        if action is None:
            return
        focused = action
        try:
            ui.heading(t(action))
            if action == 'add':
                add_model(ui, manager)
            elif action == 'select':
                selected_backend = backend(ui)
                rows = manager.inventory(selected_backend)
                if not rows:
                    say(t('empty'))
                    continue
                key = choose(ui, t('ollama_model_title' if selected_backend == 'ollama' else 'model_title'),
                             [(row['key'], row['name']) for row in rows])
                select_model(ui, manager, key)
                say(t('done'))
            elif action == 'configure':
                configure(ui, manager)
                say(t('done'))
            elif action == 'model_status':
                model_status(ui, manager)
                continue
            elif action == 'pause':
                manager.pause()
                say(t('done'))
            elif action == 'start':
                manager.start()
                say(t('done'))
            choose(ui, t('result'), [])
        except menu.Cancelled:
            continue
        except (Error, OSError, ValueError, subprocess.SubprocessError) as exc:
            say(t('error', error=exc))


def main(ui):
    manager, focused = Manager(), 'models_menu'
    actions = ('models_menu', 'codex_global', 'codex_config', 'install', 'about', 'exit')
    while True:
        try:
            status = manager.model_status(include_gpu=False)
            description = [value_line(t('current_model'), status['model'] or t('unselected')), state_line(status['state'])]
            try:
                focused = ui.choose(t('title'), [(v, t(v)) for v in actions], default=focused, cancel='exit', description=description)
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
            elif focused == 'models_menu':
                local_models(ui, manager)
                continue
            elif focused == 'codex_config':
                configure(ui, manager, codex_only=True)
                say(t('done'))
            elif focused == 'codex_global':
                global_settings(ui)
                continue
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
