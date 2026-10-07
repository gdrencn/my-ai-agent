"""One-shot configuration transactions shared by CLI and menu."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
from . import codex
from .backends import ollama_status, llama_status
from .http import request
from .models import ollama_session, ollama_inventory, ollama_install, local_model, hf_download, verify_file
from .service import Controller, fingerprint
from .settings import settings
from .store import Error, Store, atomic, read, write
from .output import operation, stage


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
        with operation('应用模型配置'), self.store.lock():
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
        launcher = codex.launcher_path()
        if launcher.exists() and '# managed by my-ai-agent\n' not in launcher.read_text():
            raise Error('codex-local is not owned by maa; refusing to overwrite it')
        old_launcher = launcher.read_bytes() if launcher.exists() else None
        native_snapshot = self.controller.snapshot()
        config_path = self.store.path('configs') / (target['model']['key'] + '.json')
        old_config = config_path.read_bytes() if config_path.exists() else None
        try:
            stage('准备底座服务')
            self.controller.ensure()
            self.controller.begin()
            stage('停止原底座')
            self.controller.stop()
            write(self.store.path('target.json'), target)
            self.controller.prepare(target)
            self.controller.start()
            runtime = self.controller.wait(target)
            runtime['display_name'] = target['model']['name']
            stage('同步 Codex 本地配置和模型目录')
            codex.profile(runtime, target['settings'])
            codex.install_launcher()
            self.save_config(target['model'], target['settings'])
            self.controller.commit(target)
            write(self.store.path('selected.json'), target)
        except BaseException as primary:
            recovery = ''
            try:
                stage('切换失败，恢复原目标')
                self.controller.stop()
                self.controller.restore(native_snapshot)
                if old_target:
                    write(self.store.path('target.json'), old_target)
                else:
                    self.store.path('target.json').unlink(missing_ok=True)
                if old_profile is not None:
                    atomic(path, old_profile)
                else:
                    path.unlink(missing_ok=True)
                if old_launcher is None:
                    launcher.unlink(missing_ok=True)
                else:
                    atomic(launcher, old_launcher, 0o755)
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
        else:
            self.controller.finish()
        finally:
            self.store.path('pending.json').unlink(missing_ok=True)
            if self.store.selected():
                write(self.store.path('target.json'), self.store.selected())
            else:
                self.store.path('target.json').unlink(missing_ok=True)

    def pause(self):
        with operation('暂停当前模型'), self.store.lock():
            self.controller.stop()

    def start(self):
        with operation('启动当前模型'), self.store.lock():
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
                'yolo': codex.yolo_state(), 'model_status': self.model_status()}

    def model_status(self, include_gpu=True):
        from .telemetry import native_allocations, nvidia_memory, launch_reference
        selected = self.store.selected()
        result = {'backend': selected['model']['backend'] if selected else None,
                  'model': selected['model']['name'] if selected else None,
                  'state': 'unselected' if not selected else 'paused', 'context': None,
                  'allocations': None, 'usage': None, 'error': None,
                  'mtp': 'unavailable' if not selected or not selected['model']['mtp_supported'] else
                  'on' if selected['settings']['mtp'] else 'off'}
        if include_gpu:
            result['gpu_memory'] = nvidia_memory()
        if not selected:
            return result
        try:
            state = self.controller.state() if hasattr(self.controller, 'state') else 'active' if self.controller.running() else 'inactive'
        except (Error, OSError, subprocess.SubprocessError) as exc:
            return {**result, 'state': 'error', 'error': str(exc)}
        if state == 'failed':
            return {**result, 'state': 'error', 'error': 'Native backend service failed; inspect maa logs'}
        if state in ('activating', 'reloading', 'deactivating'):
            return {**result, 'state': 'stopping' if state == 'deactivating' else 'loading'}
        if state != 'active':
            return result
        runtime = read(self.store.path('runtime.json'))
        if not runtime or runtime.get('fingerprint') != fingerprint(selected):
            return {**result, 'state': 'loading'}
        if runtime.get('error'):
            return {**result, 'state': 'error', 'error': runtime['error']}
        try:
            if hasattr(self.controller, 'unit_info'):
                info = self.controller.unit_info()
                log = self.store.path('native') / (result['backend'] + '.log')
                runtime['launch'] = launch_reference(log, 0, info.get('InvocationID')) if log.exists() else None
                runtime['log_path'] = str(log)
            observed = ollama_status(runtime) if result['backend'] == 'ollama' else llama_status(runtime)
            result.update(observed)
            if observed['state'] == 'running':
                result['allocations'] = native_allocations(self.store, runtime)
            result['usage_note'] = 'Native direct connection: no maa conversation interceptor or token receipt.'
            current = read(self.store.path('runtime.json'))
            if not current or current.get('fingerprint') != runtime.get('fingerprint'):
                return {**result, 'state': 'loading', 'allocations': None, 'usage': None, 'context': None}
        except (Error, OSError, ValueError, TypeError, KeyError) as exc:
            result.update(state='error', error=str(exc))
        return result

    @contextmanager
    def maintenance(self):
        active = self.controller.running()
        stage('准备模型管理服务')
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
                    stage('恢复原底座和模型')
                    self.controller.start()
                    self.controller.wait(self.store.selected())
                except BaseException as exc:
                    if primary:
                        raise Error(f'{primary}\nRestoring previous service failed: {exc}') from primary
                    raise

    def inventory(self, backend):
        with operation('读取本地模型清单'), self.store.lock():
            if backend == 'ollama':
                with self.maintenance(), ollama_session(self.store.path('native.log')):
                    return ollama_inventory(self.store)
            return [row for row in self.store.models().values() if row['backend'] == backend]

    def add_model(self, backend, name=None, path=None, repo=None, filename=None):
        with operation('安装 / 登记模型'), self.store.lock():
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
