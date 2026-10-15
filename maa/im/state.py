"""Private connector state and validated, portable connection records."""
import os
from contextlib import contextmanager
from pathlib import Path
import re
import time
import weakref
from urllib.parse import urlsplit
from ..store import Error, Store, read, write

PLATFORMS = ('telegram', 'whatsapp', 'wechat')
BASES = {'telegram': 'https://api.telegram.org', 'whatsapp': 'https://api.whatsapp.com',
         'wechat': 'https://ilinkai.weixin.qq.com'}
REPLY = 'my-ai-agent：消息收发测试成功。'
FIELDS = {'id', 'platform', 'name', 'token', 'owner_id', 'platform_id', 'api_base',
          'enabled', 'created_at', 'reply'}


def text(value, label, limit=256, empty=False):
    if not isinstance(value, str) or (not value and not empty) or len(value) > limit or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise Error('Invalid connector {v0}', v0=label)
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value):
        raise Error('Invalid connection ID')
    return value


def wechat_base(value):
    text(value, 'API address', 256)
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or
            not (parsed.hostname == 'weixin.qq.com' or parsed.hostname.endswith('.weixin.qq.com')) or
            parsed.username or parsed.password or parsed.port not in (None, 443) or
            parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise Error('Untrusted WeChat API address')
    return value.rstrip('/')


def connection(row):
    if not isinstance(row, dict) or set(row) != FIELDS:
        raise Error('Invalid connection fields')
    identifier(row['id'])
    platform = row['platform']
    if platform not in PLATFORMS:
        raise Error('Unknown connector platform')
    for name, limit, empty in [('name', 80, False), ('token', 4096, False),
                               ('owner_id', 256, True), ('platform_id', 256, True), ('reply', 512, False)]:
        text(row[name], name, limit, empty)
    if platform == 'telegram':
        if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', row['token']):
            raise Error('Invalid Telegram bot Token')
        if row['owner_id'] and not re.fullmatch(r'[1-9][0-9]{0,19}', row['owner_id']):
            raise Error('Telegram owner must be a numeric user ID')
    elif platform == 'whatsapp' and row['owner_id'] and not re.fullmatch(r'user:[0-9]+', row['owner_id']):
        raise Error('Invalid WhatsApp creator ID')
    if platform == 'wechat':
        wechat_base(row['api_base'])
        if not row['owner_id']:
            raise Error('WeChat requires the QR-authorized user ID')
    elif row['api_base'] != BASES[platform]:
        raise Error('Unexpected platform API address')
    if type(row['enabled']) is not bool or type(row['created_at']) not in (int, float) or not 0 < row['created_at'] < 10**12:
        raise Error('Invalid connection state')
    if row['enabled'] and platform == 'telegram' and not row['owner_id']:
        raise Error('Bind a Telegram test user before enabling')
    return dict(row)


def validate_config(value):
    if not isinstance(value, dict) or set(value) != {'version', 'connections'} or type(value['version']) is not int or value['version'] != 1 or not isinstance(value['connections'], dict):
        raise Error('Invalid connector configuration version/structure')
    rows = value['connections']
    if len(rows) > 100:
        raise Error('Too many connections')
    checked = {identifier(key): connection(row) for key, row in rows.items()}
    if any(key != row['id'] for key, row in checked.items()):
        raise Error('Connection ID mismatch')
    for platform in ('whatsapp', 'wechat'):
        if sum(row['platform'] == platform for row in checked.values()) > 1:
            raise Error('{v0}: only one connection is supported', v0=platform)
    identities = [(row['platform'], row['platform_id'] or row['token']) for row in checked.values()]
    tokens = [(row['platform'], row['token']) for row in checked.values()]
    if len(identities) != len(set(identities)) or len(tokens) != len(set(tokens)):
        raise Error('Duplicate platform account')
    return {'version': 1, 'connections': checked}


def delivery(value, platform):
    if not isinstance(value, dict) or set(value) - {'cursor', 'seen', 'received', 'sent', 'uncertain', 'last_received', 'last_sent', 'owner_id', 'state', 'error', 'updated_at'}:
        raise Error('Invalid receive state')
    cursor = value.get('cursor', '' if platform == 'wechat' else 0)
    if platform == 'wechat':
        if not isinstance(cursor, str) or len(cursor) > 32768:
            raise Error('Invalid WeChat receive cursor')
    elif type(cursor) is not int or cursor < 0 or cursor > 2**63-1:
        raise Error('Invalid receive cursor')
    seen = value.get('seen', [])
    if not isinstance(seen, list) or len(seen) > 2000:
        raise Error('Invalid message deduplication state')
    for item in seen:
        text(item, 'message ID', 256)
    for key in ('received', 'sent', 'uncertain'):
        if type(value.get(key, 0)) is not int or value.get(key, 0) < 0:
            raise Error('Invalid connector counter')
    for key in ('last_received', 'last_sent', 'updated_at'):
        if type(value.get(key, 0)) not in (int, float) or not 0 <= value.get(key, 0) < 10**12:
            raise Error('Invalid connector time')
    text(value.get('owner_id', ''), 'creator ID', 256, True)
    if value.get('state', 'stopped') not in ('connecting', 'connected', 'error', 'stopped'):
        raise Error('Invalid connector runtime state')
    text(value.get('error', ''), 'runtime error', 512, True)
    return dict(value, cursor=cursor, seen=seen)


class State(Store):
    @staticmethod
    def default_root():
        return Path(os.environ.get('MAA_IM_HOME') or
                    Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'my-ai-agent-im')

    def __init__(self, root=None):
        root = Path(root) if root is not None else self.default_root()
        if root.is_symlink():
            raise Error('Connector state directory must not be a symlink')
        super().__init__(root)
        if self.root.stat().st_uid != os.getuid():
            raise Error('Connector state belongs to another user')
        os.chmod(self.root, 0o700)
        # Keep the directory inode alive for this manager's lifetime. A dev/ino
        # pair alone can match an unrelated directory recreated after uninstall
        # when the filesystem immediately reuses the released inode.
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        self._directory_guard = weakref.finalize(self, os.close, descriptor)
        stat = os.fstat(descriptor)
        self.root_identity = (stat.st_dev, stat.st_ino)

    @contextmanager
    def lock(self, name='control'):
        with super().lock(name):
            try:
                stat = self.root.stat()
            except FileNotFoundError:
                raise Error('Connector installation was removed; retry the command') from None
            if self.root_identity != (stat.st_dev, stat.st_ino):
                raise Error('Connector installation changed; retry the command')
            yield

    def checked(self, name):
        path = self.path(name)
        if path.is_symlink():
            raise Error('Connector state file must not be a symlink')
        return path

    def config(self):
        return validate_config(read(self.checked('connections.json'), {'version': 1, 'connections': {}}))

    def save(self, value):
        write(self.checked('connections.json'), validate_config(value))

    def receive_path(self, key):
        folder = self.checked('runtime')
        folder.mkdir(exist_ok=True, mode=0o700)
        return self.checked('runtime/' + identifier(key) + '.json')

    def receive(self, row):
        return delivery(read(self.receive_path(row['id']), {}), row['platform'])

    def put_receive(self, row, value):
        write(self.receive_path(row['id']), delivery(dict(value, updated_at=time.time()), row['platform']))
