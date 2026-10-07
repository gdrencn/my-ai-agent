#!/usr/bin/env python3
"""Deterministic self-contained zipapp and version-paired release manifest."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from maa import __version__


def build():
    out = ROOT / 'dist'
    out.mkdir(exist_ok=True)
    files = {str(p.relative_to(ROOT)): p.read_bytes() for p in (ROOT / 'maa').rglob('*.py')}
    files['__main__.py'] = b'from maa.cli import run\nraise SystemExit(run())\n'
    files['THIRD_PARTY_LICENSES/tomlkit.txt'] = (ROOT / 'docs/TOMLKIT_LICENSE').read_bytes()
    with zipfile.ZipFile(out / 'maa.pyz', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name])
    tester = dict(files)
    tester['__main__.py'] = (ROOT / 'scripts/test_runner.py').read_bytes()
    tester.update({str(p.relative_to(ROOT)): p.read_bytes() for p in (ROOT / 'tests').rglob('*.py')})
    tester['maa_testing/__init__.py'] = b''
    tester['maa_testing/native.py'] = (ROOT / 'test/native.py').read_bytes()
    tester['maa_testing/codex_ui.py'] = (ROOT / 'test/codex_ui.py').read_bytes()
    tester['maa_testing/codex_tool.py'] = (ROOT / 'test/codex_tool.py').read_bytes()
    with zipfile.ZipFile(out / 'maa-test.pyz', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(tester):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, tester[name])
    (out / 'VERSION.json').write_text(json.dumps({'version': __version__, 'channel': 'test'}, indent=2) + '\n')
    for name in ('bootstrap.py', 'install.sh'):
        (out / name).write_bytes((ROOT / name).read_bytes())
    checksums = []
    for name in ('maa.pyz', 'maa-test.pyz', 'VERSION.json', 'bootstrap.py', 'install.sh'):
        checksums.append(hashlib.sha256((out / name).read_bytes()).hexdigest() + '  ' + name)
    (out / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n')
    print('Built my-ai-agent ' + __version__)


if __name__ == '__main__':
    build()
