"""One-shot connector management shared by CLI and menu."""
import json
from pathlib import Path
import shutil
import time
import uuid
from ..output import operation, native_output
from ..store import Error, atomic, read, write
from .adapters import adapter, WeChat
from .service import Controller
from .state import State, BASES, REPLY, connection, delivery, identifier, text, validate_config, wechat_base


class Connections:
    def __init__(self, state=None, controller=None, guard=None):
        from ..install import require_container
        self.store = state or State()
        self.controller = controller or Controller(self.store)
        self.guard = guard or require_container

    def install(self):
        self.guard()
        with operation('安装聊天连接器'), self.store.lock():
            self.controller.install()

    def row(self, key):
        try:
            return self.store.config()['connections'][identifier(key)]
        except KeyError:
            raise Error('Connection does not exist') from None

    def add(self, platform, name, token, owner_id='', platform_id='', api_base=None):
        self.guard()
        row = connection({'id': uuid.uuid4().hex, 'platform': platform, 'name': name,
                          'token': token, 'owner_id': owner_id, 'platform_id': platform_id,
                          'api_base': api_base or BASES.get(platform), 'enabled': False,
                          'created_at': time.time(), 'reply': REPLY})
        with operation('添加聊天接入'):
            if platform == 'telegram':
                row['platform_id'] = adapter(row).identity()
            with self.store.lock():
                config = self.store.config()
                config['connections'][row['id']] = row
                validate_config(config)
                if not self.controller.check():
                    self.controller.install()
                self.store.save(config)
        return self.public(row)

    @staticmethod
    def public(row):
        return {key: value for key, value in row.items() if key != 'token'} | {'credential_set': bool(row['token'])}

    def status(self):
        rows = self.store.config()['connections']
        installed = bool(self.controller.check())
        active = self.controller.active() if installed else False
        result = []
        for row in rows.values():
            value = self.store.receive(row)
            health = value.get('state', 'connecting') if row['enabled'] and active else 'error' if row['enabled'] else 'stopped'
            if row['enabled'] and active and time.time() - value.get('updated_at', 0) > 120:
                health = 'connecting'
            result.append(dict(self.public(row), state=health,
                               received=value.get('received', 0), sent=value.get('sent', 0),
                               uncertain=value.get('uncertain', 0), last_received=value.get('last_received'),
                               last_sent=value.get('last_sent'), error=value.get('error', '') if row['enabled'] else ''))
        return {'installed': installed, 'running': active, 'autostart': self.controller.enabled() if installed else False,
                'connections': result}

    def _quiesce(self, rows):
        request = uuid.uuid4().hex
        write(self.store.checked('control-request.json'), {'id': request})
        keys = {row['id'] for row in rows}
        deadline = time.monotonic() + 15
        while self.controller.active():
            ack = read(self.store.checked('supervisor.json'), {})
            if ack.get('request') == request and not keys.intersection(ack.get('active', [])):
                return
            if time.monotonic() >= deadline:
                raise Error('Connection shutdown not confirmed; local data retained')
            time.sleep(.1)

    def enable(self, key=None, enabled=True):
        self.guard()
        with operation('开启聊天接入' if enabled else '关闭聊天接入'), self.store.lock():
            config = self.store.config()
            affected = [row for row in config['connections'].values() if key is None or row['id'] == identifier(key)]
            if key is not None and not affected:
                raise Error('Connection does not exist')
            if enabled and not affected:
                raise Error('Add a connection first')
            previous = json.loads(json.dumps(config))
            for row in affected:
                row['enabled'] = enabled
            validate_config(config)
            if enabled and not self.controller.check():
                self.controller.install()
            self.store.save(config)
            try:
                self.controller.sync(any(row['enabled'] for row in config['connections'].values()))
                if not enabled:
                    self._quiesce(affected)
            except BaseException:
                self.store.save(previous)
                self.controller.sync(any(row['enabled'] for row in previous['connections'].values()))
                raise

    def update(self, key, **changes):
        self.guard()
        if set(changes) - {'name', 'reply', 'token', 'owner_id'}:
            raise Error('Unsupported connection setting')
        if 'token' in changes and self.row(key)['platform'] == 'telegram':
            probe = connection(dict(self.row(key), **changes))
            with operation('验证 Telegram 接入凭证'):
                changes['platform_id'] = adapter(probe).identity()
        with operation('修改聊天接入配置'), self.store.lock():
            config = self.store.config()
            row = self.row(key)
            row.update(changes)
            config['connections'][key] = connection(row)
            validate_config(config)
            self.store.save(config)

    def delete(self, key):
        self.guard()
        with operation('删除本地聊天接入'):
            self.enable(key, False)
            with self.store.lock():
                self._delete_closed(key)

    def _delete_closed(self, key):
        config = self.store.config()
        row = self.row(key)
        # Reject a concurrent re-enable instead of deleting active worker data.
        if row['enabled']:
            raise Error('Connection changed concurrently; close it again')
        self._quiesce([row])
        del config['connections'][key]
        self.store.save(config)
        self.store.receive_path(key).unlink(missing_ok=True)

    def export(self, path, key=None, overwrite=False):
        self.guard()
        path = Path(path).expanduser()
        if not path.is_absolute() or path.is_symlink():
            raise Error('Use an absolute, non-symlink backup path')
        if path.resolve().is_relative_to(self.store.root.resolve()):
            raise Error('Export outside the connector state directory')
        if path.exists() and not overwrite:
            raise Error('Backup exists; explicit overwrite required')
        with operation('导出聊天接入'), self.store.lock():
            rows = [row for row in self.store.config()['connections'].values() if key is None or row['id'] == identifier(key)]
            if key and not rows:
                raise Error('Connection does not exist')
            payload = {'format': 'my-ai-agent-connectors', 'version': 1, 'connections': rows,
                       'receive': {row['id']: {k: v for k, v in self.store.receive(row).items()
                                              if k not in ('state', 'error', 'updated_at')} for row in rows}}
            atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
        return {'path': str(path), 'connections': len(rows), 'contains_credentials': True}

    def import_file(self, path):
        self.guard()
        path = Path(path).expanduser()
        if not path.is_file() or path.stat().st_size > 2*1024*1024:
            raise Error('Invalid or oversized connector backup')
        with path.open('rb') as source:
            raw = source.read(2*1024*1024 + 1)
        if len(raw) > 2*1024*1024:
            raise Error('Connector backup exceeds size limit')
        payload = json.loads(raw)
        if (not isinstance(payload, dict) or set(payload) != {'format', 'version', 'connections', 'receive'} or
                payload['format'] != 'my-ai-agent-connectors' or type(payload['version']) is not int or payload['version'] != 1 or
                not isinstance(payload['connections'], list) or not isinstance(payload['receive'], dict)):
            raise Error('Invalid connector backup format')
        rows = [connection(row) for row in payload['connections']]
        if len({row['id'] for row in rows}) != len(rows) or set(payload['receive']) != {row['id'] for row in rows}:
            raise Error('Duplicate or mismatched backup connections')
        received = {row['id']: delivery(payload['receive'][row['id']], row['platform']) for row in rows}
        with operation('导入聊天接入'), self.store.lock():
            config = self.store.config()
            if set(config['connections']) & set(received):
                raise Error('Connection already exists; remove it explicitly before importing')
            for row in rows:
                row['enabled'] = False
                config['connections'][row['id']] = row
            validate_config(config)
            previous = {row['id']: (self.store.receive_path(row['id']).read_bytes()
                                    if self.store.receive_path(row['id']).exists() else None) for row in rows}
            try:
                for row in rows:
                    self.store.put_receive(row, dict(received[row['id']], state='stopped', error=''))
                self.store.save(config)
            except BaseException:
                for key, blob in previous.items():
                    if blob is None:
                        self.store.receive_path(key).unlink(missing_ok=True)
                    else:
                        atomic(self.store.receive_path(key), blob)
                raise
        return {'imported': len(rows), 'enabled': False}

    def uninstall(self):
        self.guard()
        with operation('卸载聊天连接器'), self.store.lock():
            self.controller.check()
            # Refuse unknown contents before making any destructive change.
            allowed = {'connections.json', 'service.json', 'runtime', 'control.lock', 'runtime-process.lock',
                       'control-request.json', 'supervisor.json'}
            if any(path.name not in allowed or path.is_symlink() for path in self.store.root.iterdir()):
                raise Error('Unrecognized connector data; refusing broad cleanup')
            rows = self.store.config()['connections']
            runtime = self.store.checked('runtime')
            if runtime.exists() and any(path.is_symlink() or path.name not in {key + '.json' for key in rows} for path in runtime.iterdir()):
                raise Error('Unrecognized receive data; refusing cleanup')
            self.controller.uninstall()
            retired = self.store.root.with_name(self.store.root.name + '.deleted-' + uuid.uuid4().hex)
            self.store.root.rename(retired)
        shutil.rmtree(retired)

    def bind_telegram(self, key, timeout=60):
        self.guard()
        row = self.row(key)
        if row['platform'] != 'telegram' or row['enabled']:
            raise Error('Close this Telegram connection before binding')
        client = adapter(row)
        cursor = self.store.receive(row)['cursor']
        deadline = time.monotonic() + timeout
        started = int(time.time())
        try:
            with operation('等待 Telegram 私聊测试消息'):
                while time.monotonic() < deadline:
                    messages, next_cursor = client.poll(cursor)
                    fresh = [msg for msg in messages if msg.get('time', 0) >= started]
                    if fresh:
                        return fresh[-1]['sender']
                    cursor = next_cursor
                raise Error('No private test message received; send the bot a message and retry')
        finally:
            client.client.cancel()

    def wechat_login(self, display, verification, name, key=None):
        self.guard()
        row = {'platform': 'wechat', 'api_base': BASES['wechat'], 'token': ''}
        client = WeChat(row)
        try:
            with operation('获取微信授权二维码'):
                code = client.qr()
                if not isinstance(code.get('qrcode'), str) or not isinstance(code.get('qrcode_img_content'), str):
                    raise Error('WeChat QR response incomplete')
            display(text(code['qrcode_img_content'], 'QR link', 4096))
            deadline = time.monotonic() + 300
            with operation('等待微信扫码授权'):
                return self._wechat_wait(client, code, deadline, verification, name, key)
        finally:
            client.client.cancel()

    def _wechat_wait(self, client, code, deadline, verification, name, key):
        verify = None
        while time.monotonic() < deadline:
            value = client.qr_status(code['qrcode'], verify)
            state = value.get('status')
            if state == 'confirmed':
                required = ('bot_token', 'ilink_user_id', 'ilink_bot_id')
                if any(not isinstance(value.get(k), str) or not value[k] for k in required):
                    raise Error('WeChat authorization response incomplete')
                if key:
                    with self.store.lock():
                        config = self.store.config()
                        old = self.row(key)
                        if old['platform'] != 'wechat':
                            raise Error('Expected a WeChat connection')
                        old.update(token=value['bot_token'], owner_id=value['ilink_user_id'],
                                   platform_id=value['ilink_bot_id'],
                                   api_base=wechat_base(value.get('baseurl', client.row['api_base'])))
                        config['connections'][key] = connection(old)
                        self.store.save(config)
                        return self.public(old)
                return self.add('wechat', name, value['bot_token'], value['ilink_user_id'],
                                value['ilink_bot_id'], wechat_base(value.get('baseurl', client.row['api_base'])))
            if state == 'need_verifycode':
                with native_output() as writer:
                    writer.write('微信需要配对码。\n')
                    verify = verification()
            elif state in ('expired', 'verify_code_blocked'):
                raise Error('WeChat QR expired or blocked; generate a new QR')
            elif state == 'binded_redirect':
                raise Error('WeChat reports an existing binding; retain existing credentials or generate a fresh authorization')
            time.sleep(.5)
        raise Error('WeChat QR authorization timed out')
