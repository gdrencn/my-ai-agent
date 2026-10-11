"""Official platform transports; no AI interpretation or Codex calls."""
import base64
import secrets
import time
import uuid
from urllib.parse import urlencode
from .state import BASES, wechat_base
from .transport import Client, Failure

WX_VERSION = '2.4.8'  # Compatibility metadata from Tencent's published client protocol.


class Adapter:
    def __init__(self, row, client=None):
        self.row, self.client = row, client or Client()
        self.last = {}

    def request(self, path, *, data=None, poll=False, sending=False, auth=True):
        platform = self.row['platform']
        if platform == 'whatsapp':
            interval = 4.1 if poll else 5.1
            label = 'poll' if poll else 'send'
            wait = self.last.get(label, 0) + interval - time.monotonic()
            if wait > 0 and self.client.stop.wait(wait):
                raise Failure('Connection stopped')
            self.last[label] = time.monotonic()
        return self.client.request(self.row['api_base'], path, data=data,
                                   headers=self.headers(auth), timeout=45 if poll else 30, sending=sending)

    def headers(self, auth=True):
        return {'Authorization': 'Bearer ' + self.row['token']} if auth else {}

    def start(self):
        pass

    def finish(self):
        pass


class Telegram(Adapter):
    def headers(self, auth=True):
        return {}

    def call(self, name, data, **options):
        value = self.request('/bot' + self.row['token'] + '/' + name, data=data, **options)
        if value.get('ok') is not True:
            raise Failure('Telegram rejected API request')
        return value.get('result')

    def identity(self):
        value = self.call('getMe', {})
        if not isinstance(value, dict) or not value.get('is_bot') or not value.get('id'):
            raise Failure('Telegram bot identity unavailable')
        info = self.call('getWebhookInfo', {})
        if not isinstance(info, dict):
            raise Failure('Telegram webhook information unavailable')
        if info.get('url'):
            raise Failure('This Telegram bot already uses a webhook; use a separate bot or remove its webhook explicitly')
        return str(value['id'])

    def poll(self, cursor):
        rows = self.call('getUpdates', {'offset': cursor, 'timeout': 25,
                                      'allowed_updates': ['message']}, poll=True)
        if not isinstance(rows, list):
            raise Failure('Invalid Telegram update list')
        messages = []
        for update in rows:
            uid = update['update_id']
            cursor = max(cursor, uid + 1)
            msg = update.get('message', {})
            if msg.get('chat', {}).get('type') == 'private' and isinstance(msg.get('text'), str):
                messages.append({'id': str(uid), 'sender': str(msg.get('from', {}).get('id', '')),
                                 'to': str(msg['chat']['id']), 'time': msg.get('date', 0)})
        return messages, cursor

    def send(self, msg):
        self.call('sendMessage', {'chat_id': msg['to'], 'text': self.row['reply']}, sending=True)


class WhatsApp(Adapter):
    def poll(self, cursor):
        value = self.request('/agent/v1/updates?' + urlencode({'offset': cursor, 'limit': 50, 'timeout': 15}), poll=True)
        messages = []
        for entry in value.get('entry', []):
            for change in entry.get('changes', []):
                for msg in change.get('value', {}).get('messages', []):
                    sender = msg.get('from', '')
                    if msg.get('type') == 'text' and isinstance(sender, str) and sender.startswith('user:'):
                        messages.append({'id': msg['id'], 'sender': sender, 'to': sender,
                                         'time': int(msg.get('timestamp', 0))})
        return messages, value.get('next_offset', cursor)

    def send(self, msg):
        self.request('/agent/v1/messages', data={'messaging_product': 'whatsapp',
                     'to': msg['to'], 'type': 'text', 'text': {'body': self.row['reply']}}, sending=True)


class WeChat(Adapter):
    def headers(self, auth=True):
        headers = {'iLink-App-Id': 'bot', 'iLink-App-ClientVersion': str((2 << 16) + (4 << 8) + 8)}
        if auth:
            headers.update({'AuthorizationType': 'ilink_bot_token',
                            'X-WECHAT-UIN': base64.b64encode(str(secrets.randbits(32)).encode()).decode()})
            if self.row.get('token'):
                headers['Authorization'] = 'Bearer ' + self.row['token']
        return headers

    @staticmethod
    def info():
        from .. import __version__
        return {'channel_version': WX_VERSION, 'bot_agent': 'my-ai-agent/' + __version__}

    def call(self, path, data=None, **options):
        if data is not None and path != 'get_bot_qrcode?bot_type=3':
            data = dict(data, base_info=self.info())
        value = self.request('/ilink/bot/' + path, data=data, **options)
        if value.get('ret', 0) != 0 or value.get('errcode', 0) != 0:
            expired = value.get('errcode') == -14 or value.get('ret') == -14
            raise Failure('WeChat authorization expired; authorize again' if expired else 'WeChat rejected API request',
                          retry_after=3600 if expired else 0)
        return value

    def start(self):
        self.call('msg/notifystart', {})

    def finish(self):
        # Separate bounded client: the receive client's cancellation is already set.
        client = Client()
        try:
            client.request(self.row['api_base'], '/ilink/bot/msg/notifystop',
                           data={'base_info': self.info()}, headers=self.headers(), timeout=3)
        except Failure:
            pass  # A remote notification must never prevent local shutdown.
        finally:
            client.cancel()

    def poll(self, cursor):
        value = self.call('getupdates', {'get_updates_buf': cursor}, poll=True)
        messages = []
        for msg in value.get('msgs', []):
            if msg.get('message_type') != 1 or msg.get('group_id'):
                continue
            if any(item.get('type') == 1 for item in msg.get('item_list', [])):
                messages.append({'id': str(msg['message_id']), 'sender': msg.get('from_user_id', ''),
                                 'to': msg.get('from_user_id', ''), 'context': msg.get('context_token', ''),
                                 'time': msg.get('create_time_ms', 0) / 1000})
        return messages, value.get('get_updates_buf') or cursor

    def send(self, msg):
        if not msg['context']:
            raise Failure('WeChat reply context token unavailable')
        self.call('sendmessage', {'msg': {'from_user_id': '', 'to_user_id': msg['to'],
                  'client_id': str(uuid.uuid4()), 'message_type': 2, 'message_state': 2,
                  'context_token': msg['context'], 'item_list': [{'type': 1, 'text_item': {'text': self.row['reply']}}]}}, sending=True)

    def qr(self):
        return self.call('get_bot_qrcode?bot_type=3', {'local_token_list': []})

    def qr_status(self, code, verify=None):
        params = {'qrcode': code}
        if verify:
            params['verify_code'] = verify
        value = self.request('/ilink/bot/get_qrcode_status?' + urlencode(params), auth=False, poll=True)
        if value.get('status') == 'scaned_but_redirect':
            host = value['redirect_host']
            self.row['api_base'] = wechat_base(host if host.startswith('https://') else 'https://' + host)
        return value


def adapter(row, client=None):
    return {'telegram': Telegram, 'whatsapp': WhatsApp, 'wechat': WeChat}[row['platform']](row, client)
