"""Bounded HTTP JSON with cooperative shutdown and credential-free diagnostics."""
import http.client
import json
import socket
import threading
from urllib.parse import urlsplit
from ..store import Error


class Failure(Error):
    def __init__(self, message, *, status=0, uncertain=False, retry_after=0, **values):
        super().__init__(message, **values)
        self.status, self.uncertain, self.retry_after = status, uncertain, retry_after


class Client:
    def __init__(self, stop=None):
        self.stop = stop or threading.Event()
        self.lock, self.active = threading.Lock(), None

    def cancel(self):
        self.stop.set()
        with self.lock:
            current = self.active
            if current is not None:
                try:
                    if current.sock:
                        current.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                current.close()

    def request(self, base, path, *, data=None, headers=None, timeout=45, method=None, sending=False):
        if self.stop.is_set():
            raise Failure('Connection stopped')
        url = urlsplit(base)
        factory = http.client.HTTPSConnection if url.scheme == 'https' else http.client.HTTPConnection
        current = factory(url.hostname, url.port, timeout=timeout)
        with self.lock:
            self.active = current
        try:
            if self.stop.is_set():
                raise Failure('Connection stopped')
            body = json.dumps(data, ensure_ascii=False).encode() if data is not None else None
            request_headers = {'User-Agent': 'my-ai-agent-connector', **(headers or {})}
            if body is not None:
                request_headers['Content-Type'] = 'application/json'
            current.request(method or ('POST' if body is not None else 'GET'), path, body, request_headers)
            response = current.getresponse()
            raw = response.read(2*1024*1024 + 1)
            if len(raw) > 2*1024*1024:
                raise Failure('Platform response exceeds size limit', uncertain=sending)
            try:
                value = json.loads(raw) if raw else {}
            except (ValueError, UnicodeError):
                raise Failure('Platform returned invalid JSON', uncertain=sending) from None
            if not 200 <= response.status < 300:
                delay = value.get('parameters', {}).get('retry_after', 0) if isinstance(value, dict) else 0
                if response.getheader('Retry-After', '').isdigit():
                    delay = int(response.getheader('Retry-After'))
                delay = min(3600, max(0, delay)) if type(delay) is int else 0
                # WhatsApp 503/131016 is documented as definitely not accepted.
                raise Failure('Platform HTTP {v0}', v0=response.status, status=response.status,
                              uncertain=sending and response.status >= 500 and response.status != 503,
                              retry_after=delay)
            if not isinstance(value, dict):
                raise Failure('Unexpected platform response', uncertain=sending)
            return value
        except Failure:
            raise
        except (OSError, http.client.HTTPException, ValueError):
            raise Failure('Platform network request failed', uncertain=sending) from None
        finally:
            current.close()
            with self.lock:
                if self.active is current:
                    self.active = None
