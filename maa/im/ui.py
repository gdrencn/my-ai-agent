"""Basic connection menus reuse Screen and one-shot Connections operations."""
import datetime
from pathlib import Path
import shutil
import subprocess
from .. import menu
from ..i18n import t, error_text
from ..output import say, run, diagnostic
from ..store import Error
from ..ui import choose, value_line
from .manager import Connections
from .state import PLATFORMS

STATES = {'connected': ('im_connected', 'green'), 'connecting': ('im_connecting', 'cyan'),
          'stopped': ('im_closed', 'gray'), 'error': ('im_connection_error', 'red')}
READ_ERRORS = (Error, OSError, ValueError, subprocess.SubprocessError)


def platform_label(platform):
    return t('wechat_label') if platform == 'wechat' else {'telegram': 'Telegram', 'whatsapp': 'WhatsApp'}[platform]


def connection_state(state):
    label, tone = STATES[state]
    return t(label), tone


def live(ui, manager, title, render, default=None):
    """All connector pages share read-only snapshots and Screen's inline timer."""
    previous = menu.MenuView(title, [(None, t('back'))])
    status = None

    def snapshot():
        nonlocal previous, status
        try:
            status = manager.status()
            previous = render(status)
            return previous
        except READ_ERRORS as exc:
            status = None
            return menu.MenuView(previous.title, previous.options,
                                 (value_line(t('im_read_error'), error_text(exc), 'red'),
                                  t('im_stale') if any(key is not None for key, _ in previous.options) else t('unknown')),
                                 tuple(key for key, _ in previous.options if key is not None))

    view = snapshot()
    if default is None:
        default = view.options[0][0]
    action = ui.choose(view.title, view.options, description=view.description, disabled=view.disabled,
                       default=default, refresh=snapshot)
    if action is None:
        raise menu.Cancelled
    return action, status


def display_qr(link):
    # QR rendering is optional; Tencent's client also provides a fallback URL.
    diagnostic(t('im_qr') + '\n')
    if shutil.which('qrencode'):
        run(['qrencode', '-t', 'ANSIUTF8'], input=link, text=True, native=True, check=True)
    diagnostic(link + '\n')


def stamp(value):
    return datetime.datetime.fromtimestamp(value).astimezone().isoformat(timespec='seconds') if value else t('unknown')


def details(row):
    label, tone = connection_state(row['state'])
    diagnostics = [value_line(t('im_error'), row['error'], 'red')] if row['error'] else []
    return diagnostics + [value_line(t('im_platform'), platform_label(row['platform'])),
            value_line(t('im_identity'), row['platform_id'] or t('unknown')),
            value_line(t('im_connection_state'), label, tone),
            value_line(t('im_received'), row['received']), value_line(t('im_sent'), row['sent']),
            value_line(t('im_uncertain'), row['uncertain']), value_line(t('im_last_received'), stamp(row['last_received'])),
            value_line(t('im_last_sent'), stamp(row['last_sent']))]


def export(ui, manager, key=None):
    path = Path(ui.input(t('im_backup_path'))).expanduser()
    overwrite = path.exists() and ui.confirm(t('im_overwrite', path=path))
    if path.exists() and not overwrite:
        raise menu.Cancelled
    result = manager.export(path, key, overwrite)
    say(t('im_exported', path=result['path']))


def add(ui, manager, platform):
    name = ui.input(t('im_name_input')) or platform_label(platform)
    if platform == 'wechat':
        manager.wechat_login(display_qr, lambda: ui.input(t('im_verify'), secret=True), name)
    else:
        token = ui.input(t('im_token'), secret=True).strip()
        owner = ui.input(t('im_owner_input')) if platform == 'telegram' else ''
        manager.add(platform, name, token, owner)
    say(t('im_added'))


def account(ui, manager, key):
    focused = 'switch'

    def view(status):
        row = next((row for row in status['connections'] if row['id'] == key), None)
        if not row:
            return menu.MenuView(t('im_menu'), [(None, t('back'))], (t('im_removed'),))
        options = [('switch', value_line(t('im_switch'), t('on' if row['enabled'] else 'off'), 'green' if row['enabled'] else 'gray')),
                   ('name', value_line(t('im_name'), row['name'])), ('reply', value_line(t('im_reply'), row['reply'])),
                   ('credential', value_line(t('im_credential'), t('im_credential_set')))]
        if row['platform'] == 'telegram':
            options.append(('bind', value_line(t('im_owner'), row['owner_id'] or t('im_unbound'))))
        options += [('export', t('im_export')), ('delete', t('im_delete')), (None, t('back'))]
        return menu.MenuView(row['name'], options, tuple(details(row)))

    while True:
        try:
            action, status = live(ui, manager, t('im_menu'), view, focused)
        except menu.Cancelled:
            return
        row = next(row for row in status['connections'] if row['id'] == key)
        focused = action
        try:
            if action == 'switch':
                enabled = choose(ui, t('im_switch'), [(True, t('on')), (False, t('off'))], row['enabled'])
                manager.enable(key, enabled)
            elif action in ('name', 'reply'):
                value = ui.input(t('im_edit', value=row[action]))
                if value:
                    manager.update(key, **{action: value})
            elif action == 'credential':
                if row['platform'] == 'wechat':
                    manager.wechat_login(display_qr, lambda: ui.input(t('im_verify'), secret=True), row['name'], key)
                else:
                    manager.update(key, token=ui.input(t('im_token'), secret=True).strip())
            elif action == 'bind':
                if row['enabled']:
                    raise Error(t('im_close_to_bind'))
                method = choose(ui, t('im_owner'), [('input', t('im_owner_manual')), ('receive', t('im_owner_receive'))])
                if method == 'input':
                    owner = ui.input(t('im_owner_input'))
                else:
                    say(t('im_send_private'))
                    owner = manager.bind_telegram(key)
                    if not ui.confirm(t('im_confirm_owner', owner=owner)):
                        continue
                if owner:
                    manager.update(key, owner_id=owner)
            elif action == 'export':
                export(ui, manager, key)
            elif action == 'delete':
                if not ui.confirm(t('im_confirm_delete', name=row['name'])):
                    continue
                manager.delete(key)
                say(t('done'))
                return
            say(t('done'))
        except menu.Cancelled:
            continue
        except READ_ERRORS as exc:
            say(t('error', error=exc))


def platform_menu(ui, manager, platform):
    focused = None

    def view(status):
        rows = [row for row in status['connections'] if row['platform'] == platform]
        options = [(row['id'], value_line(row['name'], *connection_state(row['state']))) for row in rows]
        if platform == 'telegram' or not rows:
            options.append(('add', t('im_add')))
        return menu.MenuView(platform_label(platform), options + [(None, t('back'))])

    while True:
        try:
            action, _ = live(ui, manager, platform_label(platform), view, focused)
        except menu.Cancelled:
            return
        focused = action
        try:
            if action == 'add':
                add(ui, manager, platform)
            else:
                account(ui, manager, action)
        except menu.Cancelled:
            continue
        except READ_ERRORS as exc:
            say(t('error', error=exc))


def platforms(ui, manager):
    focused = 'telegram'

    def view(status):
        counts = {p: sum(row['platform'] == p for row in status['connections']) for p in PLATFORMS}
        options = [(p, value_line(platform_label(p), str(counts[p]) + t('im_connections'))) for p in PLATFORMS]
        return menu.MenuView(t('im_platforms'), options + [(None, t('back'))])

    while True:
        try:
            focused, _ = live(ui, manager, t('im_platforms'), view, focused)
            platform_menu(ui, manager, focused)
        except menu.Cancelled:
            return


def program(ui, manager):
    focused = 'install'

    def view(status):
        options = [('install', value_line(t('im_install'), t('im_installed') if status['installed'] else t('im_not_installed'))),
                   ('state', value_line(t('im_runtime_state'), t('running' if status['running'] else 'im_closed'),
                                        'green' if status['running'] else 'gray')),
                   ('switch', value_line(t('im_module_switch'), t('on' if status['autostart'] else 'off'),
                                         'green' if status['autostart'] else 'gray')),
                   ('uninstall', t('im_uninstall')), (None, t('back'))]
        return menu.MenuView(t('im_program'), options, disabled=('state',))

    while True:
        try:
            focused, status = live(ui, manager, t('im_program'), view, focused)
        except menu.Cancelled:
            return
        try:
            if focused == 'switch':
                enabled = choose(ui, t('im_module_switch'), [(True, t('on')), (False, t('off'))], status['autostart'])
                manager.enable(enabled=enabled)
            elif focused == 'install':
                manager.install()
            elif focused == 'uninstall':
                if ui.confirm(t('im_confirm_uninstall')):
                    manager.uninstall()
                    say(t('done'))
                    return True
        except menu.Cancelled:
            continue
        except READ_ERRORS as exc:
            say(t('error', error=exc))


def backups(ui, manager):
    focused = 'export'
    while True:
        try:
            focused = choose(ui, t('im_backups'), [('export', t('im_export_all')), ('import', t('im_import'))], focused)
        except menu.Cancelled:
            return
        try:
            if focused == 'export':
                export(ui, manager)
            else:
                manager.import_file(ui.input(t('im_import_path')))
                say(t('im_imported'))
        except menu.Cancelled:
            continue
        except READ_ERRORS as exc:
            say(t('error', error=exc))


def main(ui, manager=None):
    manager, focused = manager or Connections(), 'platforms'
    while True:
        try:
            focused = ui.choose(t('im_menu'), [('platforms', t('im_platforms')), ('program', t('im_program')),
                                             ('backups', t('im_backups')), (None, t('back'))],
                                default=focused, description=[t('im_test_only')])
            if focused is None:
                return
            if focused == 'platforms':
                platforms(ui, manager)
            elif focused == 'program':
                if program(ui, manager):
                    return
            else:
                backups(ui, manager)
        except menu.Cancelled:
            return
