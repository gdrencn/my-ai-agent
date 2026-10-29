#!/usr/bin/env python3
"""Deterministic self-contained zipapp and version-paired release manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from maa import __version__


def entries():
    from maa.environment import PACKAGE_MANAGERS, PACKAGE_ALIASES
    template = (ROOT / 'scripts/entry.template.sh').read_text()
    cases = []
    for tool, operations in PACKAGE_MANAGERS:
        cases.append(f'    if [ "$maa_prepared" = 0 ] && command -v {tool} >/dev/null 2>&1; then')
        cases.append("        maa_native_packages=''\n        for maa_package in $maa_packages; do")
        for generic, native in PACKAGE_ALIASES.get(tool, {}).items():
            cases.append(f'            [ "$maa_package" != {generic} ] || maa_package={native}')
        cases.append('            maa_native_packages="$maa_native_packages $maa_package"\n        done')
        for i, args in enumerate(operations):
            packages = ' $maa_native_packages' if i == len(operations)-1 else ''
            cases.append('        $maa_privilege ' + ' '.join((tool, *args)) + packages)
        cases.append('        maa_prepared=1\n    fi')
    template = template.replace('@PACKAGE_CASES@', '\n'.join(cases))
    for name, arguments in (
        ('install.sh', '--channel stable'),
        ('test/install.sh', '--channel test --version ' + __version__),
        ('test/test.sh', '--channel test --version ' + __version__ + ' --test'),
    ):
        (ROOT / name).write_text(template.replace('@CHANNEL_ARGUMENTS@', arguments))


def build(channel='test'):
    entries()
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
    with zipfile.ZipFile(out / 'maa-test.pyz', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(tester):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, tester[name])
    (out / 'VERSION.json').write_text(json.dumps({'version': __version__, 'channel': channel}, indent=2) + '\n')
    (out / 'bootstrap.py').write_bytes((ROOT / 'bootstrap.py').read_bytes())
    installer = ROOT / ('test/install.sh' if channel == 'test' else 'install.sh')
    (out / 'install.sh').write_bytes(installer.read_bytes())
    checksums = []
    for name in ('maa.pyz', 'maa-test.pyz', 'VERSION.json', 'bootstrap.py', 'install.sh'):
        checksums.append(hashlib.sha256((out / name).read_bytes()).hexdigest() + '  ' + name)
    (out / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n')
    print('Built my-ai-agent ' + __version__ + ' ' + channel)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--channel', choices=('test', 'stable'), default='test')
    build(parser.parse_args().channel)
