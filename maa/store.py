"""Atomic state, serialization and cross-process mutation locking."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile


class Error(RuntimeError):
    pass


def atomic(path, data, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            os.fchmod(out.fileno(), mode)
            out.write(data.encode() if isinstance(data, str) else data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default
    except (ValueError, OSError) as exc:
        raise Error(f'Cannot read {path}: {exc}') from exc


def write(path, value):
    atomic(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def identity(backend, name):
    return hashlib.sha256((backend + '\0' + name).encode()).hexdigest()[:24]


class Store:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get('MAA_HOME') or
                         Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'my-ai-agent')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path(self, name):
        return self.root / name

    @contextmanager
    def lock(self):
        with self.path('control.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def models(self):
        return read(self.path('models.json'), {})

    def model(self, key):
        try:
            return self.models()[key]
        except KeyError:
            raise Error(f'Model is not registered: {key}') from None

    def register(self, model):
        models = self.models()
        models[model['key']] = model
        write(self.path('models.json'), models)

    def selected(self):
        return read(self.path('selected.json'))

    def target(self):
        return read(self.path('target.json'))
