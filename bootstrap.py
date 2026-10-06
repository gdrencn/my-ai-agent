#!/usr/bin/env python3
"""Discover immutable test release, validate paired assets, install inside mas."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

REPO = 'gdrencn/my-ai-agent'


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'my-ai-agent-installer'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def run():
    parser = argparse.ArgumentParser(description='Install my-ai-agent test inside a mas container')
    parser.add_argument('--version', help='exact numeric test version; default newest prerelease')
    parser.add_argument('--test', action='store_true', help='run paired portable and native checks after installing')
    parser.add_argument('--components', choices=('all', 'none', 'ollama', 'llamacpp', 'codex'), default='all')
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        raise ValueError('Python 3.11+ is required (mas default Ubuntu 24.04 includes it)')
    if not Path('/dev/lxd/sock').exists():
        raise ValueError('Run this installer inside a mas container, not on the host')
    releases = json.loads(fetch(f'https://api.github.com/repos/{REPO}/releases'))
    candidates = [r for r in releases if r['prerelease'] and not r['draft'] and r['tag_name'].startswith('v')]
    candidates = [r for r in candidates if len(r['tag_name'][1:].split('.')) == 3 and all(x.isdigit() for x in r['tag_name'][1:].split('.'))]
    if args.version:
        candidates = [r for r in candidates if r['tag_name'] == 'v' + args.version]
    if not candidates:
        raise ValueError('No matching test release exists')
    release = max(candidates, key=lambda r: tuple(map(int, r['tag_name'][1:].split('.'))))
    assets = {a['name']: a['browser_download_url'] for a in release['assets']}
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
        if info != {'version': release['tag_name'][1:], 'channel': 'test'}:
            raise ValueError('Release version/channel pairing mismatch')
        print('正在安装 my-ai-agent v' + info['version'] + ' test', flush=True)
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
