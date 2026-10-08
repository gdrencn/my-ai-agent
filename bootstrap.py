#!/usr/bin/env python3
"""Resolve an immutable channel release, verify paired assets, install in mas."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import quote

REPO = 'gdrencn/my-ai-agent'


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'my-ai-agent-installer'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def release(version=None, channel='test'):
    base = f'https://api.github.com/repos/{REPO}/releases'
    pattern = r'v(\d+\.\d+\.\d+)' if channel == 'test' else r'stable/(\d+\.\d+\.\d+)'

    def accepted(item):
        return (not item.get('draft') and item.get('prerelease') is (channel == 'test')
                and re.fullmatch(pattern, item.get('tag_name', '')))

    if version:
        if not re.fullmatch(r'v?\d+\.\d+\.\d+', version):
            raise ValueError('Version must be numeric major.minor.patch')
        tag = ('v' if channel == 'test' else 'stable/') + version.removeprefix('v')
        selected = json.loads(fetch(base + '/tags/' + quote(tag, safe='')))
        if not accepted(selected) or selected['tag_name'] != tag:
            raise ValueError('Release version/channel pairing mismatch')
        return selected
    if channel == 'stable':
        selected = json.loads(fetch(base + '/latest'))
        if not accepted(selected):
            raise ValueError('No matching stable release exists')
        return selected
    candidates = []
    for page in range(1, 101):
        rows = json.loads(fetch(base + f'?per_page=100&page={page}'))
        candidates.extend(item for item in rows if accepted(item))
        if len(rows) < 100:
            break
    if not candidates:
        raise ValueError('No matching test release exists')
    return max(candidates, key=lambda item: tuple(map(int, item['tag_name'][1:].split('.'))))


def run(argv=None):
    parser = argparse.ArgumentParser(description='Install my-ai-agent inside a mas container')
    parser.add_argument('--channel', choices=('test', 'stable'), default='test')
    parser.add_argument('--version', help='exact numeric version in the selected channel')
    parser.add_argument('--test', action='store_true', help='run paired portable and native checks after installing')
    parser.add_argument('--components', choices=('all', 'none', 'ollama', 'llamacpp', 'codex'), default='all')
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        raise ValueError('Python 3.11+ is required (mas default Ubuntu 24.04 includes it)')
    if not Path('/dev/lxd/sock').exists():
        raise ValueError('Run this installer inside a mas container, not on the host')
    selected = release(args.version, args.channel)
    version = selected['tag_name'][1:] if args.channel == 'test' else selected['tag_name'].split('/')[-1]
    assets = {a['name']: a['browser_download_url'] for a in selected['assets']}
    manifest = fetch(assets['SHA256SUMS']).decode()
    checks = dict((name, digest) for digest, name in (line.split() for line in manifest.splitlines()))
    with tempfile.TemporaryDirectory(prefix='maa-install-') as folder:
        folder = Path(folder)
        for name in ('maa.pyz', 'VERSION.json') + (('maa-test.pyz',) if args.test else ()):
            blob = fetch(assets[name])
            if hashlib.sha256(blob).hexdigest() != checks[name]:
                raise ValueError('Checksum mismatch: ' + name)
            (folder / name).write_bytes(blob)
        info = json.loads((folder / 'VERSION.json').read_text())
        if info != {'version': version, 'channel': args.channel}:
            raise ValueError('Release version/channel pairing mismatch')
        print('正在安装 my-ai-agent v' + info['version'] + ' ' + args.channel, flush=True)
        subprocess.run([sys.executable, str(folder / 'maa.pyz'), '_install', '--components', args.components], check=True)
        if args.test:
            subprocess.run([sys.executable, str(folder / 'maa-test.pyz'), '--native',
                            '--product', str(folder / 'maa.pyz')], check=True)


if __name__ == '__main__':
    try:
        run()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print('my-ai-agent install: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
