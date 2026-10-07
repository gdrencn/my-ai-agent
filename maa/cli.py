"""CLI argument parsing; business operations are shared with the menu."""
import argparse
import json
import os
import subprocess
import sys
from . import __version__, codex
from .manager import Manager
from .settings import DEFAULTS
from .store import Error
from .output import operation


def change_pairs(pairs):
    changes = {}
    for pair in pairs:
        key, sep, value = pair.partition('=')
        if not sep or key not in DEFAULTS:
            raise Error(f'Expected managed key=value: {pair}')
        if key in ('context', 'reserve_mib'):
            try:
                value = int(value)
            except ValueError:
                raise Error(f'{key} must be an integer') from None
        elif isinstance(DEFAULTS[key], bool):
            if value not in ('on', 'off'):
                raise Error(f'{key}: use on/off')
            value = value == 'on'
        changes[key] = value
    return changes


def parser():
    root = argparse.ArgumentParser(prog='maa', description='my-ai-agent: manage local models and codex-local inside mas')
    root.add_argument('--version', action='version', version=__version__)
    actions = root.add_subparsers(dest='action')
    for name in ('status', 'pause', 'start', 'logs'):
        actions.add_parser(name)
    inventory = actions.add_parser('models', help='refresh native Ollama / list registered llama.cpp models')
    inventory.add_argument('backend', choices=('ollama', 'llamacpp'))
    add = actions.add_parser('add', help='download/import/register an exact model')
    add.add_argument('backend', choices=('ollama', 'llamacpp'))
    add.add_argument('--name', help='Ollama name:tag')
    add.add_argument('--path', help='local GGUF path')
    add.add_argument('--repo', help='HF publisher/repository')
    add.add_argument('--file', dest='filename', help='exact GGUF relative filename')
    select = actions.add_parser('select', help='immediately switch; save boot target')
    select.add_argument('key', help='model key returned by maa models/add')
    select.add_argument('--set', action='append', default=[], metavar='KEY=VALUE')
    config = actions.add_parser('config', help='apply current model settings immediately')
    config.add_argument('values', nargs='+', metavar='KEY=VALUE')
    yolo = actions.add_parser('yolo', help='write two keys / restore their original values')
    yolo.add_argument('state', choices=('on', 'off'))
    installation = actions.add_parser('install', help='run official native installers')
    installation.add_argument('component', choices=('ollama', 'llamacpp', 'codex', 'all'))
    product = actions.add_parser('_install')
    product.add_argument('--components', choices=('none', 'ollama', 'llamacpp', 'codex', 'all'), default='all')
    return root


def run(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        args = parser().parse_args(argv)
        if args.action == '_install':
            from .install import product
            product(sys.argv[0], args.components)
            return 0
        if args.action is None:
            if not sys.stdout.isatty():
                raise Error('Interactive menu requires a terminal; use maa --help for CLI commands')
            from .ui import run as menu
            menu()
            return 0
        manager = Manager()
        result = None
        if args.action == 'status':
            result = manager.status()
        elif args.action == 'logs':
            selected = manager.store.selected()
            path = manager.store.path('native') / ((selected['model']['backend'] if selected else 'ollama') + '.log')
            if path.exists():
                with path.open('rb') as source:
                    source.seek(0, 2)
                    source.seek(max(0, source.tell() - 16384))
                    print(source.read().decode(errors='replace'))
        elif args.action == 'models':
            result = manager.inventory(args.backend)
        elif args.action == 'add':
            if args.backend == 'ollama' and (not args.name or args.repo or args.filename):
                raise Error('Ollama requires --name; --path optionally imports GGUF')
            if args.backend == 'llamacpp' and (bool(args.path) == bool(args.repo) or bool(args.repo) != bool(args.filename)):
                raise Error('llama.cpp requires either --path, or both --repo and --file')
            result = manager.add_model(args.backend, name=args.name, path=args.path, repo=args.repo, filename=args.filename)
        elif args.action == 'select':
            result = manager.select(args.key, change_pairs(args.set))
        elif args.action == 'config':
            result = manager.configure(change_pairs(args.values))
        elif args.action == 'pause':
            manager.pause()
        elif args.action == 'start':
            result = manager.start()
        elif args.action == 'yolo':
            with operation('更新 Codex 全局 YOLO 设置'):
                codex.yolo(args.state == 'on')
            result = codex.yolo_state()
        elif args.action == 'install':
            manager.install(args.component)
        if result is not None:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except KeyboardInterrupt as exc:
        print('maa: 已中断。' + ('\n' + str(exc) if str(exc) else ''), file=sys.stderr)
        return 130
    except (Error, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f'maa: {exc}', file=sys.stderr)
        return 1
