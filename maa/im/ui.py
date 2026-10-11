"""Basic connection menus reuse Screen and one-shot Connections operations."""
import datetime
from pathlib import Path
import shutil
from .. import menu
from ..i18n import t
from ..output import say, run, diagnostic
from ..store import Error
from ..ui import choose, value_line
from .manager import Connections
from .state import PLATFORMS

LABELS = {'telegram': 'Telegram', 'whatsapp': 'WhatsApp', 'wechat': '微信'}
STATES = {'connected': ('已连接', 'green'), 'connecting': ('连接中', 'cyan'),
          'stopped': ('已关闭', 'gray'), 'error': ('连接异常', 'red')}


def display_qr(link):
    # QR rendering is optional; Tencent's client also provides a fallback URL.
    diagnostic(t('im_qr') + '\n')
    if shutil.which('qrencode'):
        run(['qrencode', '-t', 'ANSIUTF8'], input=link, text=True, native=True, check=True)
    diagnostic(link + '\n')


def stamp(value):
    return datetime.datetime.fromtimestamp(value).astimezone().isoformat(timespec='seconds') if value else t('unknown')


def details(row):
    label, tone = STATES[row['state']]
    return [value_line(t('im_platform'), LABELS[row['platform']]), value_line(t('im_name'), row['name']),
            value_line(t('im_identity'), row['platform_id'] or t('unknown')),
            value_line(t('im_connection_state'), label, tone),
            value_line(t('im_received'), row['received']), value_line(t('im_sent'), row['sent']),
            value_line(t('im_uncertain'), row['uncertain']), value_line(t('im_last_received'), stamp(row['last_received'])),
            value_line(t('im_last_sent'), stamp(row['last_sent']))] + ([value_line(t('im_error'), row['error'], 'red')] if row['error'] else [])


def export(ui, manager, key=None):
    path = Path(ui.input(t('im_backup_path'))).expanduser()
    overwrite = path.exists() and ui.confirm(t('im_overwrite', path=path))
    if path.exists() and not overwrite:
        raise menu.Cancelled
    result = manager.export(path, key, overwrite)
    say(t('im_exported', path=result['path']))


def add(ui, manager, platform):
    name = ui.input(t('im_name_input')) or LABELS[platform]
    if platform == 'wechat':
        manager.wechat_login(display_qr, lambda: ui.input(t('im_verify'), secret=True), name)
    else:
        token = ui.input(t('im_token'), secret=True).strip()
        owner = ui.input(t('im_owner_input')) if platform == 'telegram' else ''
        manager.add(platform, name, token, owner)
    say(t('im_added'))


def account(ui, manager, key):
    focused = 'switch'
    while True:
        row = next((row for row in manager.status()['connections'] if row['id'] == key), None)
        if not row:
            return
        try:
            options = [('switch', value_line(t('im_switch'), t('on' if row['enabled'] else 'off'), 'green' if row['enabled'] else 'gray')),
                       ('name', value_line(t('im_name'), row['name'])), ('reply', value_line(t('im_reply'), row['reply'])),
                       ('credential', value_line(t('im_credential'), t('im_credential_set')))]
            if row['platform'] == 'telegram':
                options.append(('bind', value_line(t('im_owner'), row['owner_id'] or t('im_unbound'))))
            options += [('refresh', t('refresh')), ('export', t('im_export')), ('delete', t('im_delete'))]
            action = ui.choose(row['name'], options + [(None, t('back'))], default=focused, description=details(row))
            if action is None:
                return
            focused = action
        except menu.Cancelled:
            return
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
                if ui.confirm(t('im_confirm_delete', name=row['name'])):
                    manager.delete(key)
                    say(t('done'))
                    return
            elif action == 'refresh':
                continue
            say(t('done'))
        except menu.Cancelled:
            continue


def platform_menu(ui, manager, platform):
    while True:
        rows = [row for row in manager.status()['connections'] if row['platform'] == platform]
        options = [(row['id'], value_line(row['name'], *STATES[row['state']])) for row in rows]
        if platform == 'telegram' or not rows:
            options.append(('add', t('im_add')))
        try:
            action = choose(ui, LABELS[platform], options)
            if action == 'add':
                add(ui, manager, platform)
            else:
                account(ui, manager, action)
        except menu.Cancelled:
            return
        except (Error, OSError, ValueError) as exc:
            say(t('error', error=exc))


def main(ui, manager=None):
    manager, focused = manager or Connections(), 'telegram'
    while True:
        try:
            status = manager.status()
            count = {p: sum(row['platform'] == p for row in status['connections']) for p in PLATFORMS}
            options = [('switch', value_line(t('im_module_switch'), t('on' if status['autostart'] else 'off'), 'green' if status['autostart'] else 'gray'))]
            options += [(p, value_line(LABELS[p], str(count[p]) + t('im_connections'))) for p in PLATFORMS]
            options += [('install', value_line(t('im_install'), t('im_installed') if status['installed'] else t('im_not_installed'))),
                        ('refresh', t('refresh')), ('export', t('im_export_all')), ('import', t('im_import')),
                        ('uninstall', t('im_uninstall'))]
            description = [value_line(t('run_state'), t('running' if status['running'] else 'im_closed'), 'green' if status['running'] else 'gray'), t('im_test_only')]
            action = ui.choose(t('im_menu'), options + [(None, t('back'))], default=focused, description=description)
            if action is None:
                return
            focused = action
        except menu.Cancelled:
            return
        except (Error, OSError, ValueError) as exc:
            say(t('error', error=exc))
            return
        try:
            if action in PLATFORMS:
                platform_menu(ui, manager, action)
            elif action == 'switch':
                enabled = choose(ui, t('im_module_switch'), [(True, t('on')), (False, t('off'))], status['autostart'])
                manager.enable(enabled=enabled)
            elif action == 'install':
                manager.install()
            elif action == 'export':
                export(ui, manager)
            elif action == 'import':
                manager.import_file(ui.input(t('im_import_path')))
                say(t('im_imported'))
            elif action == 'uninstall':
                if ui.confirm(t('im_confirm_uninstall')):
                    manager.uninstall()
                    say(t('done'))
                    return
        except menu.Cancelled:
            continue
        except (Error, OSError, ValueError) as exc:
            say(t('error', error=exc))
