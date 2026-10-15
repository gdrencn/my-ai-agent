"""Public basic connector commands; credentials never occur in argv."""
import getpass
from pathlib import Path
import sys
from ..store import Error
from .manager import Connections
from ..i18n import t


def arguments(actions):
    root = actions.add_parser('im', help='basic Telegram/WhatsApp/WeChat connectors; no Codex integration')
    commands = root.add_subparsers(dest='im_action', required=True)
    for name in ('status', 'install'):
        commands.add_parser(name)
    for name in ('on', 'off'):
        commands.add_parser(name).add_argument('id', nargs='?', help='connection ID; omitted means all')
    for name in ('delete', 'uninstall'):
        command = commands.add_parser(name)
        if name == 'delete':
            command.add_argument('id')
        command.add_argument('--yes', action='store_true', help='confirm local deletion; does not modify remote accounts')
    add = commands.add_parser('add')
    add.add_argument('platform', choices=('telegram', 'whatsapp'))
    add.add_argument('--name', required=True)
    add.add_argument('--token-file', help='private credential file; otherwise prompt without echo')
    add.add_argument('--owner-id', default='', help='Telegram allowed numeric user ID')
    login = commands.add_parser('wechat', help='official QR login; add or renew existing connection')
    login.add_argument('--name', default=t('wechat_label'))
    login.add_argument('--id', help='renew an existing WeChat connection')
    bind = commands.add_parser('bind', help='receive one Telegram private message and display candidate user ID')
    bind.add_argument('id')
    config = commands.add_parser('config')
    config.add_argument('id')
    config.add_argument('--name')
    config.add_argument('--reply')
    config.add_argument('--owner-id')
    config.add_argument('--token-file')
    export = commands.add_parser('export', help='private JSON backup containing credentials')
    export.add_argument('path')
    export.add_argument('--id')
    export.add_argument('--overwrite', action='store_true')
    commands.add_parser('import', help='validate and import; connections remain closed').add_argument('path')


def credential(path=None):
    if path:
        value = Path(path).expanduser()
        if not value.is_file() or value.stat().st_size > 8192:
            raise Error('Invalid credential file')
        with value.open('r') as source:
            return source.read(8193).strip()
    if not sys.stdin.isatty():
        raise Error('Use --token-file in noninteractive mode')
    return getpass.getpass(t('credential_prompt')).strip()


def execute(args):
    manager = Connections()
    action = args.im_action
    if action == 'status':
        return manager.status()
    if action == 'install':
        manager.install()
    elif action in ('on', 'off'):
        manager.enable(args.id, action == 'on')
    elif action == 'add':
        return manager.add(args.platform, args.name, credential(args.token_file), args.owner_id)
    elif action in ('delete', 'uninstall'):
        if not args.yes:
            raise Error('Local deletion requires --yes')
        if action == 'delete':
            manager.delete(args.id)
        else:
            manager.uninstall()
        return {'deleted': args.id if action == 'delete' else 'connector-module', 'remote_changed': False}
    elif action == 'config':
        changes = {key: getattr(args, key) for key in ('name', 'reply', 'owner_id') if getattr(args, key) is not None}
        if args.token_file:
            changes['token'] = credential(args.token_file)
        manager.update(args.id, **changes)
        return manager.public(manager.row(args.id))
    elif action == 'bind':
        candidate = manager.bind_telegram(args.id)
        return {'candidate_owner_id': candidate, 'bound': False,
                'next': 'Confirm this user, then use maa im config ID --owner-id USER_ID'}
    elif action == 'export':
        return manager.export(args.path, args.id, args.overwrite)
    elif action == 'import':
        return manager.import_file(args.path)
    elif action == 'wechat':
        if not sys.stdin.isatty():
            raise Error('Run WeChat QR authorization in an interactive terminal')
        from .ui import display_qr
        return manager.wechat_login(display_qr, lambda: getpass.getpass(t('wechat_pairing_prompt')), args.name, args.id)
    return {'ok': True}
