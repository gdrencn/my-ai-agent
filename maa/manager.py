"""Transactional composition shared by CLI, menu and codex-local."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
from . import codex
from .backends import ollama_load, llama_observe
from .http import request
from .models import ollama_session, ollama_inventory, ollama_install, local_model, hf_download, verify_file
from .service import Controller, fingerprint
from .settings import settings
from .store import Error, Store, atomic, read, write


class Manager:
    def __init__(self, store=None, controller=None):
        self.store = store or Store()
        self.controller = controller or Controller(self.store)

    def config(self, model, changes=None):
        saved = read(self.store.path('configs') / (model['key'] + '.json'), {})
        return settings(saved, changes, mtp_supported=model['mtp_supported'])

    def save_config(self, model, values):
        write(self.store.path('configs') / (model['key'] + '.json'), values)

    def select(self, key, changes=None):
        with self.store.lock():
            model = self.store.model(key)
            verify_file(model)
            target = {'model': model, 'settings': self.config(model, changes)}
            self._apply(target)
            return self.status()

    def _apply(self, target):
        old = self.store.selected()
        old_target = old
        active = self.controller.running()
        path = codex.profile_path()
        old_profile = path.read_bytes() if path.exists() else None
        config_path = self.store.path('configs') / (target['model']['key'] + '.json')
        old_config = config_path.read_bytes() if config_path.exists() else None
        try:
            self.controller.ensure()
            self.controller.stop()
            write(self.store.path('pending.json'), {'pid': os.getpid(),
                  'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                  'process_start': Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]})
            write(self.store.path('target.json'), target)
            self.controller.start()
            runtime = self.controller.wait(target)
            codex.profile(runtime, target['settings'])
            self.save_config(target['model'], target['settings'])
            write(self.store.path('selected.json'), target)
        except BaseException as primary:
            recovery = ''
            try:
                self.controller.stop()
                if old_target:
                    write(self.store.path('target.json'), old_target)
                else:
                    self.store.path('target.json').unlink(missing_ok=True)
                if old_profile is not None:
                    atomic(path, old_profile)
                else:
                    path.unlink(missing_ok=True)
                if old_config is not None:
                    atomic(config_path, old_config)
                else:
                    config_path.unlink(missing_ok=True)
                if active and old:
                    self.controller.start()
                    self.controller.wait(old_target)
                    recovery = 'Previous service restored.'
                else:
                    recovery = 'Previous stopped state restored.'
            except BaseException as secondary:
                recovery = f'Recovery failed: {secondary}; saved selection retained. Run maa start.'
            raise Error(f'Switch failed: {primary}\n{recovery}') from primary
        finally:
            self.store.path('pending.json').unlink(missing_ok=True)

    def pause(self):
        with self.store.lock():
            self.controller.stop()

    def start(self):
        with self.store.lock():
            target = self.store.selected()
            if not target:
                raise Error('Select a local model first')
            self._apply(target)
            return self.status()

    def status(self):
        selected = self.store.selected()
        running = self.controller.running()
        runtime = read(self.store.path('runtime.json')) if running else None
        return {'selected': selected, 'running': running, 'runtime': runtime,
                'yolo': codex.yolo_state()}

    @contextmanager
    def maintenance(self):
        active = self.controller.running()
        self.controller.ensure()
        self.controller.stop()
        primary = None
        try:
            yield
        except BaseException as exc:
            primary = exc
            raise
        finally:
            if active:
                try:
                    self.controller.start()
                    self.controller.wait(self.store.selected())
                except BaseException as exc:
                    if primary:
                        raise Error(f'{primary}\nRestoring previous service failed: {exc}') from primary
                    raise

    def inventory(self, backend):
        with self.store.lock():
            if backend == 'ollama':
                with self.maintenance(), ollama_session(self.store.path('native.log')):
                    return ollama_inventory(self.store)
            return [row for row in self.store.models().values() if row['backend'] == backend]

    def add_model(self, backend, name=None, path=None, repo=None, filename=None):
        with self.store.lock():
            if backend == 'ollama':
                with self.maintenance(), ollama_session(self.store.path('native.log')):
                    return ollama_install(self.store, name, path)
            model = hf_download(self.store, repo, filename) if repo else local_model(path)
            self.store.register(model)
            return model

    def configure(self, changes):
        selected = self.store.selected()
        if not selected:
            raise Error('Select a local model first')
        return self.select(selected['model']['key'], changes)

    def local_command(self, arguments):
        # This entry is dedicated to the selected local model. Native Codex task
        # arguments are forwarded, but provider/model overrides cannot reroute it.
        forbidden = ('--profile', '-p', '--model', '-m', '--oss', '--local-provider')
        for index, arg in enumerate(arguments):
            if any(arg == flag or arg.startswith(flag + '=') for flag in forbidden) or (
                    arg.startswith(('-m', '-p')) and not arg.startswith('--')):
                raise Error('codex-local model/provider are managed by maa; change them in maa select')
            override = (arguments[index + 1] if arg in ('-c', '--config') and index + 1 < len(arguments)
                        else arg[2:] if arg.startswith('-c') and not arg.startswith('--')
                        else arg.partition('=')[2] if arg.startswith('--config=') else '')
            if override:
                key = override.partition('=')[0].strip()
                if key.startswith(('model', 'profiles')):
                    raise Error('codex-local model configuration must be changed through maa')
        with self.store.lock():
            target = self.store.selected()
            if not target or not self.controller.running():
                raise Error('Current model is stopped or unselected; use maa start / maa select')
            runtime = self.controller.wait(target)
            if runtime['backend'] == 'ollama':
                observed = ollama_load(target)
            else:
                observed = llama_observe(target['model']['key'], runtime['upstream'])
            runtime.update(observed)
            request(runtime['base_url'].removesuffix('/v1') + '/health', timeout=2)
            codex.profile(runtime, target['settings'])
            command = [codex.executable(), '--profile', 'maa-local'] + list(arguments)
        # Do not hold the mutation lock throughout an interactive coding session.
        return subprocess.call(command)
