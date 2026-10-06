"""Bounded native HTTP calls; preserve status and upstream diagnostics."""
import json
import urllib.error
import urllib.request
from .store import Error


def request(url, value=None, timeout=30, method=None):
    data = None if value is None else json.dumps(value).encode()
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read(32 * 1024 * 1024 + 1)
            if len(body) > 32 * 1024 * 1024:
                raise Error('Native API response exceeded 32 MiB')
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        raise Error(f'HTTP {exc.code} from {url}: {exc.read(8192).decode(errors="replace")}') from exc
    except (OSError, ValueError) as exc:
        raise Error(f'{url}: {exc}') from exc
