"""Bounded native HTTP calls; preserve status and upstream diagnostics."""
import json
import urllib.error
import urllib.request
from .store import Error


def endpoint(host, port):
    """Format a native client URL without changing the server's bind address."""
    host = {'0.0.0.0': '127.0.0.1', '::': '::1'}.get(host, host)
    authority = '[' + host + ']' if ':' in host else host
    return f'http://{authority}:{port}'


def request(url, value=None, timeout=30, method=None):
    data = None if value is None else json.dumps(value).encode()
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read(32 * 1024 * 1024 + 1)
            if len(body) > 32 * 1024 * 1024:
                raise Error('Native API response exceeded 32 MiB')
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        raise Error('HTTP {v0} from {v1}: {v2}', v0=exc.code, v1=url, v2=exc.read(8192).decode(errors="replace")) from exc
    except (OSError, ValueError) as exc:
        raise Error('{v0}: {v1}', v0=url, v1=exc) from exc
