"""Historical failure-cleanup regressions, used only with private mocked state."""
from contextlib import contextmanager
from pathlib import Path
import tempfile
from maa.store import Store, read, write
REPORT = {'cleanup': []}
def command(*args, **kwargs):
    raise RuntimeError('This helper requires a private command fixture')

@contextmanager
def invalid_fixture():
    import struct
    store, key = Store(), None
    previous = store.selected()
    with tempfile.TemporaryDirectory(prefix='maa-native-invalid-') as folder:
        path = Path(folder) / 'bad-native.gguf'
        path.write_bytes(b'GGUF' + struct.pack('<IQQ', 3, 0, 0))
        try:
            bad = command('add', 'llamacpp', '--path', str(path))
            key = bad['key']
            yield bad
        finally:
            selected = store.selected()
            if key and selected and selected['model']['key'] == key:
                if previous:
                    command('select', previous['model']['key'])
                else:
                    command('pause', structured=False)
                    with store.lock():
                        store.path('selected.json').unlink(missing_ok=True)
                        store.path('target.json').unlink(missing_ok=True)
            with store.lock():
                rows = store.models()
                if key:
                    selected = store.selected()
                    if selected and selected['model']['key'] == key:
                        raise RuntimeError('Invalid fixture unexpectedly selected; refusing to remove an active model')
                    rows.pop(key, None)
                    write(store.path('models.json'), rows)
                    (store.path('configs') / (key + '.json')).unlink(missing_ok=True)
            REPORT['cleanup'].append({'fixture': 'bad-native.gguf', 'key': key, 'registry_removed': key not in store.models(),
                                      'temporary_directory': True})


def cleanup_legacy_fixture():
    """Recognize only the exact weight-less fixture created by the 0.1.1 tester."""
    import hashlib
    import struct
    store = Store()
    path = store.path('bad-native.gguf')
    signature = b'GGUF' + struct.pack('<IQQ', 3, 0, 0)
    if not path.is_file() or path.stat().st_size != len(signature) or path.read_bytes() != signature:
        return
    digest = hashlib.sha256(signature).hexdigest()
    with store.lock():
        rows = store.models()
        owned = [key for key, row in rows.items() if row.get('path') == str(path)
                 and row.get('source') == 'local' and row.get('sha256') == digest]
        selected = store.selected()
        if selected and selected['model']['key'] in owned:
            REPORT['cleanup'].append({'legacy_fixture_removed': False, 'reason': 'Fixture is selected; retained'})
            return
        for key in owned:
            rows.pop(key)
            (store.path('configs') / (key + '.json')).unlink(missing_ok=True)
        write(store.path('models.json'), rows)
        path.unlink()
        REPORT['cleanup'].append({'legacy_fixture_removed': True, 'keys': owned})

