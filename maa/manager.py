"""One-shot configuration transactions shared by CLI and menu."""
from contextlib import contextmanager
import subprocess
from . import codex
from .backends import ollama_status, llama_status
from .models import (ollama_session, ollama_inventory, ollama_install, local_model,
                     hf_download, verify_file, ollama_input)
from .service import Controller, fingerprint
from .settings import settings, BACKEND_KEYS
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
            old = self.store.selected()
            if self._same_backend(old, target):
                if old != target:
                    self._codex_only(target)
                self._start_saved(target)
            else:
                self._apply(target)
            return self.status()

    @staticmethod
    def _same_backend(first, second):
        return bool(first and first['model'] == second['model'] and
                    all(first['settings'][key] == second['settings'][key] for key in BACKEND_KEYS))

    def _codex_only(self, target):
        """Use the accepted context even when paused; never contact the backend."""
        old = self.store.selected()
        runtime = read(self.store.path('runtime.json'))
        if not runtime or runtime.get('fingerprint') != fingerprint(old):
            raise Error('No verified context for the current model; run maa start before changing codex-local configuration')
        config = self.store.path('configs') / (target['model']['key'] + '.json')
        paths = (codex.profile_path(), config, self.store.path('runtime.json'),
                 self.store.path('target.json'), self.store.path('selected.json'))
        backup = {path: path.read_bytes() if path.exists() else None for path in paths}
        try:
            stage('保存 codex-local 配置；保留底座运行状态')
            codex.profile(runtime, target['settings'])
            self.save_config(target['model'], target['settings'])
            write(self.store.path('runtime.json'), {**runtime, 'fingerprint': fingerprint(target)})
            write(self.store.path('target.json'), target)
            write(self.store.path('selected.json'), target)
        except BaseException:
            for path, data in backup.items():
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic(path, data)
            raise

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
            write(self.store.path('pending.json'), target)
            self.controller.begin()
            stage('停止原底座')
            self.controller.stop()
            write(self.store.path('target.json'), target)
            self.controller.prepare(target)
            self.controller.start(target)
            runtime = self.controller.wait(target)
            runtime['display_name'] = target['model']['name']
            write(self.store.path('runtime.json'), runtime)
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
                    self.controller.start(old_target)
                    self.controller.wait(old_target)
                    recovery = 'Previous service restored.'
                else:
                    recovery = 'Previous stopped state restored.'
            except BaseException as secondary:
                recovery = f'Recovery failed: {secondary}; saved selection retained. Run maa start.'
            if isinstance(primary, KeyboardInterrupt):
                raise KeyboardInterrupt(recovery) from primary
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
            verify_file(target['model'])
            self._start_saved(target)
            return self.status()

    def _interrupted_target(self, target):
        return self.store.target() != target or self.store.path('pending.json').exists()

    def _start_saved(self, target):
        if self._interrupted_target(target):
            stage('恢复已提交目标并重新核验原生配置')
            write(self.store.path('target.json'), target)
            self._apply(target)
            return
        runtime = read(self.store.path('runtime.json'))
        valid = (runtime and runtime.get('fingerprint') == fingerprint(target) and
                 self.controller.configuration_matches(target))
        if not valid:
            self._apply(target)
            return
        if self.controller.running():
            observed = (ollama_status if target['model']['backend'] == 'ollama' else llama_status)(runtime)
            if observed['state'] == 'running':
                stage('当前模型已运行；复用现有底座')
                return
            self.controller.wake(target)
            runtime = self.controller.wait(target)
        else:
            stage('启动已保存的原生底座配置')
            self.controller.ensure()
            snapshot = self.controller.snapshot()
            path = codex.profile_path()
            old_profile = path.read_bytes() if path.exists() else None
            try:
                self.controller.start(target)
                runtime = self.controller.wait(target)
                runtime['display_name'] = target['model']['name']
                write(self.store.path('runtime.json'), runtime)
                codex.profile(runtime, target['settings'])
                self.controller.commit(target)
            except BaseException as primary:
                try:
                    stage('启动失败，恢复原暂停状态')
                    self.controller.stop()
                    self.controller.restore(snapshot)
                    if old_profile is None:
                        path.unlink(missing_ok=True)
                    else:
                        atomic(path, old_profile)
                    recovery = 'Previous stopped state restored.'
                except BaseException as secondary:
                    recovery = f'Recovery failed: {secondary}; saved selection retained. Run maa start.'
                if isinstance(primary, KeyboardInterrupt):
                    raise KeyboardInterrupt(recovery) from primary
                raise Error(f'Start failed: {primary}\n{recovery}') from primary
            return
        runtime['display_name'] = target['model']['name']
        write(self.store.path('runtime.json'), runtime)
        codex.profile(runtime, target['settings'])
        self.controller.commit(target)

    def status(self):
        selected = self.store.selected()
        running = self.controller.running()
        runtime = read(self.store.path('runtime.json')) if running else None
        return {'selected': selected, 'running': running, 'runtime': runtime,
                'yolo': codex.yolo_state(), 'model_status': self.model_status()}

    def model_status(self, include_gpu=True, include_allocations=True):
        from .telemetry import native_allocations, nvidia_memory, launch_reference
        selected = self.store.selected()
        result = {'backend': selected['model']['backend'] if selected else None,
                  'model': selected['model']['name'] if selected else None,
                  'state': 'unselected' if not selected else 'paused', 'context': None,
                  'allocations': None, 'usage': None, 'error': None,
                  'usage_note': 'Native direct connection: no maa conversation interceptor or token receipt.',
                  'mtp': 'unavailable' if not selected or not selected['model']['mtp_supported'] else
                  'on' if selected['settings']['mtp'] else 'off'}
        saved = read(self.store.path('runtime.json')) if selected else None
        result['saved_context'] = saved.get('context') if saved and saved.get('fingerprint') == fingerprint(selected) else None
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
            if include_allocations and hasattr(self.controller, 'unit_info'):
                info = self.controller.unit_info()
                log = self.store.path('native') / (result['backend'] + '.log')
                runtime['launch'] = launch_reference(log, 0, info.get('InvocationID')) if log.exists() else None
                runtime['log_path'] = str(log)
            observed = ollama_status(runtime) if result['backend'] == 'ollama' else llama_status(runtime)
            result.update(observed)
            if include_allocations and observed['state'] == 'running':
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
        target = self.store.selected()
        stage('准备模型管理服务')
        self.controller.ensure()
        primary = None
        try:
            self.controller.stop()
            yield
        except BaseException as exc:
            primary = exc
            raise
        finally:
            if active and target:
                try:
                    stage('恢复原底座和模型')
                    if self._interrupted_target(target):
                        self._start_saved(target)
                    else:
                        self.controller.start(target)
                        runtime = self.controller.wait(target)
                        codex.profile(runtime, target['settings'])
                        self.controller.commit(target)
                except BaseException as exc:
                    detail = f'Restoring previous service failed: {exc}; saved selection retained. Run maa start.'
                    if isinstance(primary, KeyboardInterrupt) or isinstance(exc, KeyboardInterrupt):
                        raise KeyboardInterrupt(detail) from (primary or exc)
                    if primary:
                        raise Error(f'{primary}\n{detail}') from primary
                    raise
                else:
                    if isinstance(primary, KeyboardInterrupt):
                        raise KeyboardInterrupt('Previous service restored.') from primary

    def inventory(self, backend):
        with operation('读取本地模型清单'), self.store.lock():
            if backend == 'ollama':
                if self._ollama_running():
                    return ollama_inventory(self.store)
                with self.maintenance(), ollama_session(self.store.path('native.log')):
                    return ollama_inventory(self.store)
            return [row for row in self.store.models().values() if row['backend'] == backend]

    def add_model(self, backend, name=None, path=None, repo=None, filename=None):
        with operation('安装 / 登记模型'):
            if backend == 'ollama':
                ollama_input(name, path)
                with self.store.lock('ollama-download'):
                    with self.store.lock():
                        direct = self._ollama_running()
                        if not direct:
                            with self.maintenance(), ollama_session(self.store.path('native.log')):
                                installed = ollama_install(self.store, name, path)
                                return self._installed_ollama(installed)
                    # The user may pause/switch during native pull. Its failure
                    # must not restore a stale target over their newer choice.
                    installed = ollama_install(self.store, name, path)
                    with self.store.lock():
                        if self._ollama_running():
                            return self._installed_ollama(installed)
                        with self.maintenance(), ollama_session(self.store.path('native.log')):
                            return self._installed_ollama(installed)
            model = hf_download(self.store, repo, filename) if repo else local_model(path)
            with self.store.lock():
                verify_file(model)
                self.store.register(model)
            return model

    def _ollama_running(self):
        selected = self.store.selected()
        return bool(selected and selected['model']['backend'] == 'ollama'
                    and self.controller.owned('ollama') and self.controller.running())

    def _installed_ollama(self, name):
        try:
            model = next(iter(ollama_inventory(self.store, name=name)))
        except StopIteration:
            raise Error('Native installation completed but model is absent from the native inventory') from None
        selected = self.store.selected()
        if selected and selected['model']['backend'] == 'ollama' and selected['model']['name'] == name:
            # pull/create can replace a public tag's saved parameters, even with
            # identical weights. Next explicit start/select must revalidate it.
            runtime = read(self.store.path('runtime.json'))
            if runtime:
                write(self.store.path('runtime.json'), {**runtime, 'native_config': None})
        return model

    def install(self, component):
        from .install import component as installer
        with operation('安装底座 / Codex CLI'), self.store.lock():
            selected = self.store.selected()
            if component != 'codex':
                self.controller.ensure()
            affected = selected and component in ('all', selected['model']['backend'])
            if affected:
                with self.maintenance():
                    installer(component)
            else:
                installer(component)

    def configure(self, changes, expected=None):
        with operation('应用配置'), self.store.lock():
            selected = self.store.selected()
            if not selected:
                raise Error('Select a local model first')
            if expected is not None and selected != expected:
                raise Error('Current model or configuration changed during editing; reopen the configuration menu')
            target = {'model': selected['model'], 'settings': self.config(selected['model'], changes)}
            if selected == target:
                stage('配置未变化；保留当前运行状态')
            elif self._same_backend(selected, target):
                self._codex_only(target)
            else:
                verify_file(target['model'])
                self._apply(target)
            return self.status()
