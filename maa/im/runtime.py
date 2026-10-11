"""Standalone connector supervisor and per-account receive loops."""
import hashlib
import json
import signal
import threading
import time
from .adapters import adapter
from .state import State, text
from .transport import Client, Failure
from ..store import Error, read, write


class Worker(threading.Thread):
    def __init__(self, row, store, factory=adapter):
        super().__init__(name='im-' + row['id'], daemon=False)
        self.row, self.store = row, store
        self.stop_event = threading.Event()
        self.client = Client(self.stop_event)
        self.adapter = factory(row, self.client)
        self.value = store.receive(row)

    def save(self, state=None, error=None):
        if state is not None:
            self.value['state'] = state
        if error is not None:
            self.value['error'] = error
        self.store.put_receive(self.row, self.value)

    def stop(self):
        self.client.cancel()

    def handle(self, msg):
        mid = text(msg['id'], 'message ID', 256)
        if mid in self.value['seen'] or msg.get('time', 0) < int(self.row['created_at']):
            return
        owner = self.row['owner_id'] or self.value.get('owner_id', '')
        if owner and msg['sender'] != owner:
            return
        if self.row['platform'] == 'whatsapp' and not owner:
            self.value['owner_id'] = text(msg['sender'], 'creator ID', 256)
        self.value['seen'] = (self.value['seen'] + [mid])[-2000:]
        self.value['received'] = self.value.get('received', 0) + 1
        self.value['last_received'] = time.time()
        # Commit receipt before sending: a crash must not blindly send it again.
        self.save()
        for attempt in range(3):
            if self.stop_event.is_set():
                return
            try:
                self.adapter.send(msg)
                self.value['sent'] = self.value.get('sent', 0) + 1
                self.value['last_sent'] = time.time()
                self.save('connected', '')
                return
            except Failure as exc:
                if exc.uncertain:
                    self.value['uncertain'] = self.value.get('uncertain', 0) + 1
                    self.save('error', 'Send result unknown; not automatically resent')
                    return
                if exc.status in (429, 503) and attempt < 2:
                    if self.stop_event.wait(max(exc.retry_after, 2**attempt)):
                        return
                    continue
                self.save('error', str(exc))
                return

    def run(self):
        self.save('connecting', '')
        delay = 1
        try:
            try:
                self.adapter.start()
            except Failure:
                pass  # Start notification is advisory, not login/readiness evidence.
            while not self.stop_event.is_set():
                try:
                    messages, cursor = self.adapter.poll(self.value['cursor'])
                    self.save('connected', '')
                    for msg in messages:
                        if self.stop_event.is_set():
                            break
                        self.handle(msg)
                    if not self.stop_event.is_set():
                        self.value['cursor'] = cursor
                        self.save()
                    delay = 1
                except Failure as exc:
                    if self.stop_event.is_set():
                        break
                    self.save('error', str(exc))
                    if exc.status in (400, 401, 403):
                        self.stop_event.wait()  # New credentials/config create a new worker.
                    else:
                        self.stop_event.wait(max(delay, exc.retry_after))
                        delay = min(60, delay*2)
                except (KeyError, TypeError, ValueError, Error):
                    self.save('error', 'Malformed platform response')
                    self.stop_event.wait(delay)
                    delay = min(60, delay*2)
        finally:
            self.client.cancel()
            self.adapter.finish()
            self.save('stopped', '')


def fingerprint(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()


def serve(store=None, stop=None, factory=adapter):
    store, stop = store or State(), stop or threading.Event()
    workers, acknowledged = {}, None
    with store.lock('runtime-process'):
        try:
            while not stop.is_set():
                # Read the barrier before configuration. An acknowledgement can
                # only cover changes committed before the management request.
                request = read(store.checked('control-request.json'), {})
                rows = store.config()['connections']
                wanted = {key: row for key, row in rows.items() if row['enabled']}
                for key, (signature, worker) in list(workers.items()):
                    if not worker.is_alive():
                        raise Failure('Connector worker exited unexpectedly')
                    if key not in wanted or fingerprint(wanted[key]) != signature:
                        worker.stop()
                        worker.join(12)
                        if worker.is_alive():
                            raise Failure('Connector shutdown timed out')
                        del workers[key]
                for key, row in wanted.items():
                    if key not in workers:
                        worker = Worker(row, store, factory)
                        workers[key] = (fingerprint(row), worker)
                        worker.start()
                acknowledgement = {'request': request.get('id'), 'active': list(workers)}
                if acknowledgement != acknowledged:
                    write(store.checked('supervisor.json'), acknowledgement)
                    acknowledged = acknowledgement
                stop.wait(.25)
        finally:
            for _, worker in workers.values():
                worker.stop()
            for _, worker in workers.values():
                worker.join(12)


def main():
    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    try:
        serve(stop=stop)
        return 0
    except Exception as exc:
        # No exception bodies: unknown transport errors may contain credentials.
        print('Connector stopped: ' + type(exc).__name__, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
