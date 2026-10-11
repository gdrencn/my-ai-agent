"""Private protocol fixtures and connector lifecycle acceptance; no remote sends."""
from contextlib import contextmanager
import http.server
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import uuid
import zipfile
from maa.im.adapters import Telegram, WhatsApp, WeChat, Adapter
from maa.im.manager import Connections
from maa.im.packaging import runtime_bytes
from maa.im.runtime import Worker, serve
from maa.im.service import Controller
from maa.im.state import State, BASES, REPLY, connection, validate_config, delivery, wechat_base
from maa.im.transport import Client, Failure
from maa.store import Error, atomic, read, write


def record(platform='telegram', **changes):
    return connection(dict(id=uuid.uuid4().hex, platform=platform, name='Private fixture', token='123:FAKE_TEST_TOKEN',
        owner_id='42' if platform == 'telegram' else 'user:42' if platform == 'whatsapp' else 'wx-owner',
        platform_id=uuid.uuid4().hex, api_base=BASES[platform], enabled=False,
        created_at=time.time()-1, reply=REPLY) | changes)


def eventually(check, seconds=3):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(.02)
    raise AssertionError('Condition not reached')


class Quiet(Adapter):
    def send(self, msg):
        pass

    def poll(self, cursor):
        self.client.stop.wait(.03)
        return [], cursor


class FixtureController:
    """Real supervisor with fixture-only adapters and no system mutations."""
    def __init__(self, store):
        self.store, self.installed, self.autostart = store, False, False
        self.thread, self.stop_event = None, None

    def check(self):
        return {'fixture': True} if self.installed else None

    def install(self):
        self.installed = True

    def active(self):
        return bool(self.thread and self.thread.is_alive())

    def enabled(self):
        return self.autostart

    def sync(self, enabled):
        self.autostart = enabled
        if enabled and not self.active():
            self.stop_event = threading.Event()
            self.thread = threading.Thread(target=serve, args=(self.store, self.stop_event, Quiet))
            self.thread.start()
        elif not enabled and self.active():
            self.stop_event.set()
            self.thread.join(4)
            assert not self.thread.is_alive()

    def uninstall(self):
        self.sync(False)
        self.installed = False


@contextmanager
def http_fixture(callback):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def handle_request(self):
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length)) if length else None
            status, body, headers = callback(self.path, payload, dict(self.headers))
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(json.dumps(body).encode() if body is not None else b'')
            except (BrokenPipeError, ConnectionResetError):
                pass

        do_GET = do_POST = handle_request
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield 'http://127.0.0.1:' + str(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class Connectors(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = State(self.root / 'im')
        self.control = FixtureController(self.store)
        self.manager = Connections(self.store, self.control, lambda: None)

    def tearDown(self):
        self.control.sync(False)
        self.temp.cleanup()

    def save_rows(self, *rows):
        self.store.save({'version': 1, 'connections': {row['id']: row for row in rows}})

    def test_platform_limits_binding_identity_and_address_validation(self):
        tg = record()
        self.save_rows(tg, record(token='456:SECOND_TEST_TOKEN'))
        for platform in ('whatsapp', 'wechat'):
            with self.assertRaises(Error):
                self.save_rows(record(platform), record(platform))
        with self.assertRaises(Error):
            self.save_rows(tg, record(token=tg['token']))
        with self.assertRaises(Error):
            record(enabled=True, owner_id='')
        for url in ('http://ilinkai.weixin.qq.com', 'https://weixin.qq.com.evil.test',
                    'https://user:pass@ilinkai.weixin.qq.com', 'https://ilinkai.weixin.qq.com/x'):
            with self.assertRaises(Error):
                wechat_base(url)
        for value in ({'cursor': -1}, {'cursor': True}, {'seen': ['\x1b[2J']}, {'error': '\x1b[2J'}, {'state': {}}):
            with self.assertRaises(Error):
                delivery(value, 'telegram')

    def test_two_bot_disable_and_delete_wait_for_supervisor_without_stopping_other(self):
        one, two = record(), record(token='456:FAKE_SECOND_TOKEN')
        self.save_rows(one, two)
        self.manager.enable()
        eventually(lambda: all(row['state'] == 'connected' for row in self.manager.status()['connections']))
        thread = self.control.thread
        self.manager.delete(one['id'])
        self.assertIs(thread, self.control.thread)
        self.assertTrue(thread.is_alive())
        self.assertNotIn(one['id'], self.store.config()['connections'])
        self.assertFalse(self.store.receive_path(one['id']).exists())
        self.assertNotIn(one['id'], read(self.store.path('supervisor.json'))['active'])
        self.manager.enable(enabled=False)
        self.assertFalse(self.control.active())
        self.assertFalse(self.control.enabled())

    def test_fast_on_off_never_leaves_worker_or_recreates_deleted_state(self):
        row = record()
        self.save_rows(row)
        for _ in range(5):
            self.manager.enable(row['id'])
            self.manager.enable(row['id'], False)
        self.manager.delete(row['id'])
        time.sleep(.1)
        self.assertFalse(self.store.receive_path(row['id']).exists())
        self.assertFalse(self.control.active())

    def test_export_delete_import_preserves_cursor_credentials_and_closes_connections(self):
        row = record(enabled=True)
        self.save_rows(row)
        self.store.put_receive(row, {'cursor': 2**53+17, 'seen': ['m1'], 'sent': 3, 'received': 4})
        backup = self.root / 'private.json'
        self.manager.export(backup)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(Error):
            self.manager.export(backup)
        with self.assertRaises(Error):
            self.manager.import_file(backup)
        self.manager.delete(row['id'])
        self.manager.import_file(backup)
        restored = self.manager.row(row['id'])
        self.assertFalse(restored['enabled'])
        self.assertEqual(restored['token'], row['token'])
        self.assertEqual(self.store.receive(restored)['cursor'], 2**53+17)
        self.assertEqual(self.store.receive(restored)['seen'], ['m1'])
        self.assertNotIn(row['token'], json.dumps(self.manager.status()))

    def test_invalid_import_is_transactional_and_does_not_overwrite_account(self):
        row = record('whatsapp')
        self.save_rows(row)
        backup = self.root / 'backup'
        other = record('whatsapp')
        write(backup, {'format': 'my-ai-agent-connectors', 'version': 1, 'connections': [other], 'receive': {other['id']: {}}})
        before = self.store.path('connections.json').read_bytes()
        with self.assertRaises(Error):
            self.manager.import_file(backup)
        self.assertEqual(before, self.store.path('connections.json').read_bytes())
        self.assertFalse(self.store.receive_path(other['id']).exists())

    def test_cleanup_refuses_unknown_data_and_retires_old_manager(self):
        row = record('whatsapp')
        self.save_rows(row)
        unknown = self.store.path('user-file')
        unknown.write_text('retain')
        with self.assertRaises(Error):
            self.manager.uninstall()
        self.assertEqual(unknown.read_text(), 'retain')
        unknown.unlink()
        self.manager.uninstall()
        self.assertFalse(self.store.root.exists())
        self.assertFalse(list(self.root.glob('*.deleted-*')))
        State(self.store.root)
        with self.assertRaises(Error):
            with self.store.lock():
                self.fail('Retired manager accepted a replacement installation')

    def test_worker_filters_users_old_updates_and_deduplicates_before_send(self):
        row = record()
        worker = Worker(row, self.store, Quiet)
        sent = []
        worker.adapter.send = lambda msg: sent.append(msg['id'])
        msg = {'id': '1', 'sender': '42', 'to': '42', 'time': time.time(), 'body': 'PRIVATE_CHAT_BODY'}
        worker.handle(msg)
        worker.handle(msg)
        worker.handle(dict(msg, id='2', sender='99'))
        worker.handle(dict(msg, id='3', time=0))
        self.assertEqual(sent, ['1'])
        state = self.store.receive(row)
        self.assertEqual((state['received'], state['sent']), (1, 1))
        self.assertNotIn('PRIVATE_CHAT_BODY', self.store.receive_path(row['id']).read_text())
        restarted = Worker(row, self.store, Quiet)
        restarted.adapter.send = lambda _: self.fail('Repeated send after restart')
        restarted.handle(msg)

    def test_ambiguous_send_is_recorded_and_never_retried(self):
        row = record('whatsapp', owner_id='')
        worker = Worker(row, self.store, Quiet)
        calls = []
        def send(msg):
            calls.append(msg)
            raise Failure('Network reset', uncertain=True)
        worker.adapter.send = send
        msg = {'id': 'm1', 'sender': 'user:42', 'to': 'user:42', 'time': time.time()}
        worker.handle(msg)
        worker.handle(msg)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.store.receive(row)['uncertain'], 1)
        self.assertEqual(self.store.receive(row)['owner_id'], 'user:42')

    def test_rate_limits_and_definitive_send_retry_are_bounded(self):
        client = WhatsApp(record('whatsapp'))
        waits = []
        with patch.object(client.client, 'request', return_value={}), \
                patch.object(client.client.stop, 'wait', side_effect=lambda delay: waits.append(delay) or False), \
                patch('maa.im.adapters.time.monotonic', return_value=100):
            client.poll(0)
            client.poll(0)
            client.send({'to': 'user:42'})
            client.send({'to': 'user:42'})
        self.assertEqual(len(waits), 2)
        self.assertAlmostEqual(waits[0], 4.1)
        self.assertAlmostEqual(waits[1], 5.1)
        row = record()
        worker = Worker(row, self.store, Quiet)
        with patch.object(worker.adapter, 'send', side_effect=[Failure('Rate limited', status=429, retry_after=7), None]) as send, \
                patch.object(worker.stop_event, 'wait', return_value=False) as wait:
            worker.handle({'id': 'm1', 'sender': '42', 'to': '42', 'time': time.time()})
        self.assertEqual(send.call_count, 2)
        wait.assert_called_once_with(7)
        self.assertEqual(self.store.receive(row)['sent'], 1)

    def test_authentication_failure_waits_for_configuration_or_cancel(self):
        class Unauthorized(Quiet):
            def poll(self, cursor):
                raise Failure('Platform HTTP 401', status=401)
        row = record()
        worker = Worker(row, self.store, Unauthorized)
        worker.start()
        try:
            eventually(lambda: self.store.receive(row).get('state') == 'error')
            self.assertTrue(worker.is_alive())
            worker.stop()
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(self.store.receive(row)['state'], 'stopped')
        finally:
            worker.stop(); worker.join(1)

    def test_native_controller_ownership_rollback_and_independent_unit(self):
        controller = Controller(self.store, self.root / 'units', self.root / 'connectors.pyz')
        events = []
        def privileged(args, **kwargs):
            events.append(args)
            if args[0] == 'install':
                atomic(Path(args[-1]), Path(args[-2]).read_bytes(), 0o644)
            elif args[0] == 'rm':
                Path(args[-1]).unlink()
        with patch('maa.im.service.require_systemd'), patch('maa.im.service.privileged', privileged), \
                patch.object(controller, 'active', return_value=False), patch.object(controller, 'enabled', return_value=False):
            controller.install()
            unit = controller.path.read_text()
            self.assertIn('connectors.pyz', unit)
            self.assertNotIn('maa.pyz', unit)
            self.assertNotIn('codex', unit)
            controller.check()
            before = controller.executable.read_bytes()
            with patch('maa.im.service.runtime_bytes', return_value=b'upgraded'), \
                    patch.object(controller, 'sync', side_effect=Error('fixture failure')):
                with self.assertRaises(Error):
                    controller.install()
            self.assertEqual(before, controller.executable.read_bytes())
            controller.check()
            controller.path.write_text('foreign unit')
            with self.assertRaises(Error):
                controller.uninstall()
            self.assertTrue(controller.executable.exists())

    def test_runtime_archive_starts_without_product_or_codex(self):
        blob = runtime_bytes()
        self.assertEqual(blob, runtime_bytes())
        archive = self.root / 'connectors.pyz'
        archive.write_bytes(blob)
        with zipfile.ZipFile(io.BytesIO(blob)) as package:
            self.assertNotIn('maa/manager.py', package.namelist())
            self.assertNotIn('maa/codex.py', package.namelist())
            self.assertNotIn('maa/im/manager.py', package.namelist())
        env = dict(os.environ, MAA_IM_HOME=str(self.store.root))
        process = subprocess.Popen([sys.executable, '-I', str(archive)], env=env, cwd=self.root,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            eventually(lambda: self.store.path('supervisor.json').exists())
            process.terminate()
            out, err = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 0, (out, err))
        finally:
            if process.poll() is None:
                process.kill(); process.wait()

    def test_wechat_qr_confirmation_and_credential_renewal_keep_existing_identity(self):
        class Login:
            def __init__(self, row):
                self.row, self.client = row, Client()
            def qr(self):
                return {'qrcode': 'fixture-qr', 'qrcode_img_content': 'https://ilinkai.weixin.qq.com/fixture'}
            def qr_status(self, code, verify):
                return {'status': 'confirmed', 'bot_token': 'FAKE_WX_TOKEN', 'ilink_user_id': 'wx-owner',
                        'ilink_bot_id': 'wx-bot', 'baseurl': BASES['wechat']}
        displays = []
        with patch('maa.im.manager.WeChat', Login):
            row = self.manager.wechat_login(displays.append, lambda: self.fail('Unexpected code request'), '微信')
            self.assertFalse(row['enabled'])
            self.assertNotIn('token', row)
            renewed = self.manager.wechat_login(displays.append, lambda: '', 'ignored', row['id'])
        self.assertEqual(row['id'], renewed['id'])
        self.assertEqual(len(self.store.config()['connections']), 1)
        self.assertEqual(self.manager.row(row['id'])['token'], 'FAKE_WX_TOKEN')
        self.assertEqual(len(displays), 2)

    def test_menu_and_cli_share_operations_without_model_manager(self):
        from maa.cli import parser
        from maa.im.cli import execute
        row = record('whatsapp')
        self.save_rows(row)
        with patch('maa.im.cli.Connections', return_value=self.manager), \
                patch('maa.cli.Manager', side_effect=AssertionError('Model manager must not be involved')):
            result = execute(parser().parse_args(['im', 'status']))
            self.assertEqual(result['connections'][0]['id'], row['id'])
            with self.assertRaises(Error):
                execute(parser().parse_args(['im', 'delete', row['id']]))
        self.assertIn(row['id'], self.store.config()['connections'])

    def test_telegram_official_request_shapes_and_webhook_refusal(self):
        requests = []
        def response(path, payload, headers):
            requests.append((path, payload, headers))
            name = path.rsplit('/', 1)[-1]
            result = {'getMe': {'id': 123, 'is_bot': True}, 'getWebhookInfo': {'url': ''},
                      'getUpdates': [{'update_id': 8, 'message': {'date': 123, 'from': {'id': 42},
                                     'chat': {'id': 42, 'type': 'private'}, 'text': 'not persisted'}},
                                    {'update_id': 9, 'message': {'chat': {'type': 'group'}, 'text': 'ignore'}}],
                      'sendMessage': {'message_id': 10}}[name]
            return 200, {'ok': True, 'result': result}, {}
        with http_fixture(response) as base:
            row = record()
            client = Telegram(dict(row, api_base=base))  # Fixture injection; public config rejects HTTP.
            self.assertEqual(client.identity(), '123')
            messages, cursor = client.poll(5)
            self.assertEqual(cursor, 10)
            self.assertEqual(len(messages), 1)
            client.send(messages[0])
        self.assertEqual(requests[-1][1], {'chat_id': '42', 'text': REPLY})
        self.assertEqual(requests[2][1]['offset'], 5)
        self.assertNotIn('body', messages[0])
        client = Telegram(record())
        with patch.object(client, 'call', side_effect=[{'id': 1, 'is_bot': True}, {'url': 'https://existing.test'}]):
            with self.assertRaises(Failure):
                client.identity()

    def test_whatsapp_int64_cursor_204_and_fixed_reply(self):
        requests = []
        def response(path, payload, headers):
            requests.append((path, payload, headers))
            if len(requests) == 1:
                return 200, {'next_offset': 2**53+13, 'entry': [{'changes': [{'value': {'messages': [
                    {'from': 'user:42', 'id': 'wamid.fixture', 'timestamp': '123', 'type': 'text',
                     'text': {'body': 'not persisted'}}]}}]}]}, {}
            return 204, None, {}
        with http_fixture(response) as base:
            client = WhatsApp(dict(record('whatsapp'), api_base=base))
            messages, cursor = client.poll(0)
            self.assertEqual(cursor, 2**53+13)
            client.last.clear()  # Avoid sleeping for fixture rate limiting.
            self.assertEqual(client.poll(cursor), ([], cursor))
            client.send(messages[0])
        self.assertIn('offset=9007199254741005', requests[1][0])
        self.assertEqual(requests[2][1]['text']['body'], REPLY)
        self.assertTrue(requests[0][2]['Authorization'].startswith('Bearer '))

    def test_wechat_context_auth_qr_redirect_and_expired_cooldown(self):
        requests = []
        def response(path, payload, headers):
            requests.append((path, payload, headers))
            if path.endswith('/getupdates'):
                return 200, {'ret': 0, 'get_updates_buf': 'next', 'msgs': [{'message_id': 4, 'message_type': 1,
                    'from_user_id': 'wx-owner', 'create_time_ms': 123000, 'context_token': 'opaque-context',
                    'item_list': [{'type': 1, 'text_item': {'text': 'not persisted'}}]}]}, {}
            return 200, {'ret': 0}, {}
        with http_fixture(response) as base:
            client = WeChat(dict(record('wechat'), api_base=base))
            messages, cursor = client.poll('before')
            client.send(messages[0])
        self.assertEqual(cursor, 'next')
        self.assertEqual(requests[1][1]['msg']['context_token'], 'opaque-context')
        self.assertEqual(requests[0][2]['AuthorizationType'], 'ilink_bot_token')
        self.assertIn('base_info', requests[0][1])
        client = WeChat(record('wechat'))
        with patch.object(client, 'request', return_value={'status': 'scaned_but_redirect', 'redirect_host': 'evil.test'}):
            with self.assertRaises(Error):
                client.qr_status('qr')
        with patch.object(client, 'request', return_value={'errcode': -14}):
            with self.assertRaises(Failure) as failure:
                client.poll('')
            self.assertEqual(failure.exception.retry_after, 3600)

    def test_http_errors_are_sanitized_and_slow_poll_is_cancelled(self):
        with http_fixture(lambda *_: (500, {'error': 'SECRET_MUST_NOT_LEAK'}, {})) as base:
            with self.assertRaises(Failure) as failure:
                Client().request(base, '/secret', data={}, sending=True)
            self.assertTrue(failure.exception.uncertain)
            self.assertNotIn('SECRET', str(failure.exception))
        arrived, release = threading.Event(), threading.Event()
        def slow(*_):
            arrived.set(); release.wait(3)
            return 200, {}, {}
        errors = []
        with http_fixture(slow) as base:
            client = Client()
            def receive():
                try:
                    client.request(base, '/poll')
                except Failure as exc:
                    errors.append(exc)
            thread = threading.Thread(target=receive)
            thread.start()
            self.assertTrue(arrived.wait(2))
            client.cancel()
            thread.join(1)
            release.set()
            self.assertFalse(thread.is_alive())
        self.assertTrue(errors)


if __name__ == '__main__':
    unittest.main()
