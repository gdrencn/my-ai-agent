"""Build the same independent connector runtime from source or a zipapp."""
import importlib.resources
import io
import zipfile


def runtime_bytes():
    from .. import __version__
    files = {'__main__.py': b'from maa.im.runtime import main\nraise SystemExit(main())\n',
             'maa/__init__.py': ('__version__ = ' + repr(__version__) + '\n').encode(),
             'maa/store.py': importlib.resources.files('maa').joinpath('store.py').read_bytes()}
    for name in ('__init__', 'state', 'transport', 'adapters', 'runtime'):
        files['maa/im/' + name + '.py'] = importlib.resources.files('maa.im').joinpath(name + '.py').read_bytes()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o644 << 16
            archive.writestr(info, data)
    return output.getvalue()
