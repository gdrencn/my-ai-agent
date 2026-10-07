"""One-shot native systemd configuration; no maa runtime service."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import time
import uuid
from .backends import (binary, llama_arguments, llama_endpoint, llama_observe,
                       ollama_capabilities, check_options, ollama_environment,
                       ollama_endpoint, ollama_prepare, ollama_observe)
from .http import request
from .output import stage, native_output
from .store import Error, atomic, read, write

UNITS = {'ollama': 'ollama.service', 'llamacpp': 'llama-server.service'}


def fingerprint(target):
    return hashlib.sha256(json.dumps(target, sort_keys=True).encode()).hexdigest()


def privileged(command, **kwargs):
    if kwargs.get('capture_output') or (kwargs.get('stdout') is not None and kwargs.get('stderr') is not None):
        return subprocess.run(([] if os.geteuid() == 0 else ['sudo']) + command, check=True, **kwargs)
    with native_output():
        return subprocess.run(([] if os.geteuid() == 0 else ['sudo']) + command, check=True, **kwargs)


def escaped(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def exec_arg(value):
    return escaped(str(value).replace('$', '$$'))


class Controller:
    def __init__(self, store):
        self.store = store
        self.marker = f'# my-ai-agent native configuration owner uid={os.getuid()}'
        self.model_backup = None

    def unit_path(self, backend):
        base = Path('/etc/systemd/system')
        return base / 'ollama.service.d/50-local-model.conf' if backend == 'ollama' else base / UNITS[backend]

    def config_paths(self):
        return ([self.unit_path(b) for b in UNITS] + [self.store.path('native') / 'ollama-preload.json',
                self.store.path('runtime.json'), self.store.path('ollama-originals.json')])

    def owned(self, backend):
        path = self.unit_path(backend)
        return path.exists() and path.read_text().startswith(self.marker + '\n')

    def ensure(self):
        from .install import require_container
        require_container()
        if not Path('/run/systemd/system').exists():
            raise Error('Native backend autostart requires systemd inside mas')
        for backend in UNITS:
            path = self.unit_path(backend)
            if path.exists() and not self.owned(backend):
                raise Error(f'Native configuration is not owned by this installation: {path}')

    def legacy_path(self):
        path = Path('/etc/systemd/system/maa.service')
        if not path.exists():
            return None
        text = path.read_text()
        expected = str(Path.home() / '.local/share/my-ai-agent/maa.pyz')
        import shlex
        commands = [line.split('=', 1)[1] for line in text.splitlines() if line.startswith('ExecStart=')]
        arguments = shlex.split(commands[0]) if len(commands) == 1 else []
        if (not text.startswith(f'# my-ai-agent owner uid={os.getuid()}\n') or len(arguments) != 3
                or arguments[1:] != [expected, '_serve']
                or not Path(arguments[0]).name.startswith('python')
                or any(line.startswith(('ExecStartPre=', 'ExecStartPost=', 'ExecStop=')) for line in text.splitlines())):
            raise Error('Legacy maa.service was modified or belongs to another user; refusing to remove it')
        return path

    def migrate(self):
        path = self.legacy_path()
        if path is None:
            return
        stage('移除旧 maa 常驻服务')
        privileged(['systemctl', 'disable', '--now', 'maa.service'])
        privileged(['rm', '--', str(path)])
        privileged(['systemctl', 'daemon-reload'])
        self.store.path('runtime.json').unlink(missing_ok=True)

    def snapshot(self):
        self.ensure()
        return {'files': {str(p): p.read_bytes() if p.exists() else None for p in self.config_paths()},
                'enabled': {b: self.enabled(b) for b in UNITS}}

    def enabled(self, backend):
        result = subprocess.run(['systemctl', 'is-enabled', UNITS[backend]], capture_output=True, text=True, timeout=5)
        return result.stdout.strip() == 'enabled'

    def write_unit(self, path, text):
        temp = self.store.path('native-unit.tmp')
        atomic(temp, text)
        privileged(['install', '-D', '-m', '644', str(temp), str(path)])
        temp.unlink(missing_ok=True)

    def restore(self, snapshot):
        if self.model_backup:
            from .models import ollama_session
            name, backup = self.model_backup
            with ollama_session(self.store.path('native') / 'maintenance.log'):
                request(ollama_endpoint() + '/api/copy', {'source': backup, 'destination': name})
                request(ollama_endpoint() + '/api/delete', {'model': backup}, method='DELETE')
            self.model_backup = None
        for name, data in snapshot['files'].items():
            path = Path(name)
            if name.startswith('/etc/systemd/system/'):
                if data is None:
                    if path.exists():
                        privileged(['rm', '--', name])
                else:
                    self.write_unit(path, data.decode())
            elif data is None:
                path.unlink(missing_ok=True)
            else:
                atomic(path, data)
        privileged(['systemctl', 'daemon-reload'])
        for backend, enabled in snapshot['enabled'].items():
            if self.unit_path(backend).exists() or backend == 'ollama':
                privileged(['systemctl', 'enable' if enabled else 'disable', UNITS[backend]],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def begin(self):
        # An interrupted validation must never boot an unaccepted candidate.
        # Pause uses stop() only and therefore keeps the accepted boot target.
        for backend in UNITS:
            if self.owned(backend):
                privileged(['systemctl', 'disable', UNITS[backend]], stdout=subprocess.DEVNULL)

    def commit(self, target):
        privileged(['systemctl', 'enable', UNITS[target['model']['backend']]], stdout=subprocess.DEVNULL)

    def finish(self):
        if self.model_backup:
            try:
                request(ollama_endpoint() + '/api/delete', {'model': self.model_backup[1]}, method='DELETE')
                self.model_backup = None
            except Error:
                # An unused manifest is harmless; the accepted runtime is valid.
                import sys
                with native_output():
                    print('Unused rollback manifest retained; native model configuration is committed.', file=sys.stderr)

    def prepare(self, target):
        """Only official backend executables and curl run at boot."""
        self.ensure()
        model, values = target['model'], target['settings']
        user = pwd.getpwuid(os.getuid()).pw_name
        self.store.path('native').mkdir(exist_ok=True)
        log = self.store.path('native') / (model['backend'] + '.log')
        log.touch(mode=0o600, exist_ok=True)
        import grp
        group = grp.getgrgid(os.getgid()).gr_name
        common = (f'User={user}\nGroup={group}\n'
                  f'Environment=HOME={escaped(Path.home())}\n'
                  f'Environment=PATH={escaped(str(Path.home() / ".local/bin") + ":/usr/local/bin:/usr/bin:/bin")}\n'
                  f'StandardOutput=append:{log}\nStandardError=append:{log}\n'
                  f'ExecStartPre=/usr/bin/truncate --size 0 {exec_arg(log)}\n'
                  'TimeoutStartSec=660\nTimeoutStopSec=30\nKillMode=control-group\nRestart=on-failure\nRestartSec=10\n')
        if model['backend'] == 'ollama':
            from .models import ollama_session
            help_text = ollama_capabilities()
            check_options(help_text, ['--fit', '--fit-target'])
            if values['mtp']:
                check_options(help_text, ['draft-mtp', '--spec-draft-type-k', '--spec-draft-type-v'])
            with ollama_session(log, values):
                backup = 'maa-rollback-' + uuid.uuid4().hex + ':latest'
                request(ollama_endpoint() + '/api/copy', {'source': model['name'], 'destination': backup})
                self.model_backup = (model['name'], backup)
                ollama_prepare(target, self.store)
            names = {key: value for key, value in ollama_environment(values).items()
                     if key.startswith(('OLLAMA_', 'LLAMA_ARG_'))}
            environments = ''.join('Environment=' + escaped(key + '=' + value) + '\n' for key, value in sorted(names.items()))
            preload = self.store.path('native') / 'ollama-preload.json'
            write(preload, {'model': model['name'], 'prompt': '', 'stream': False, 'keep_alive': values['keep_alive']})
            text = (self.marker + '\n[Service]\nExecStart=\nExecStartPre=\nExecStartPost=\n' + common + environments +
                    'ExecStart=' + exec_arg(binary('ollama')) + ' serve\n' +
                    'ExecStartPost=/usr/bin/curl --fail --silent --show-error --retry 120 --retry-delay 1 '
                    '--retry-connrefused --max-time 600 --output /dev/null --header "Content-Type: application/json" '
                    '--data-binary ' + exec_arg('@' + str(preload)) + ' ' + exec_arg(ollama_endpoint() + '/api/generate') + '\n')
        else:
            import socket
            from urllib.parse import urlparse
            endpoint = urlparse(llama_endpoint())
            try:
                with socket.create_connection((endpoint.hostname, endpoint.port), timeout=1):
                    pass
            except OSError:
                pass
            else:
                raise Error('An unmanaged llama.cpp endpoint is already listening; stop it before maa model operations')
            command = llama_arguments(model, values)
            env = {key: value for key, value in os.environ.items() if key in ('LLAMA_ARG_HOST', 'LLAMA_ARG_PORT')}
            text = (self.marker + '\n[Unit]\nDescription=llama.cpp local model\nAfter=network-online.target\n'
                    'Wants=network-online.target\n[Service]\nType=simple\n' + common +
                    ''.join('Environment=' + escaped(key + '=' + value) + '\n' for key, value in env.items()) +
                    'ExecStart=' + ' '.join(exec_arg(arg) for arg in command) + '\n[Install]\nWantedBy=multi-user.target\n')
        self.write_unit(self.unit_path(model['backend']), text)
        privileged(['systemctl', 'daemon-reload'])

    def stop(self):
        for backend in UNITS:
            if self.owned(backend):
                privileged(['systemctl', 'stop', UNITS[backend]])

    def start(self, target):
        # The caller owns the transaction: never infer a candidate from disk.
        if not target:
            raise Error('Select a local model first')
        backend = target['model']['backend']
        for other in UNITS:
            if other != backend and self.owned(other):
                privileged(['systemctl', 'disable', '--now', UNITS[other]], stdout=subprocess.DEVNULL)
        stage('启动原生底座')
        privileged(['systemctl', 'start', UNITS[backend]])

    def wake(self, target):
        if target['model']['backend'] == 'ollama':
            from .backends import ollama_wake
            ollama_wake(target['model']['name'], target['settings'])
        else:
            stage('唤醒 llama.cpp 模型')
            request(llama_endpoint() + '/v1/responses', {'model': target['model']['name'],
                    'input': 'Hi', 'max_output_tokens': 1, 'stream': False}, timeout=600)

    def unit_info(self, target=None):
        target = target or self.store.selected()
        if not target:
            return {'ActiveState': 'inactive'}
        if not self.owned(target['model']['backend']):
            return {'ActiveState': 'inactive'}
        result = subprocess.run(['systemctl', 'show', UNITS[target['model']['backend']],
                                 '--property=ActiveState,SubState,Result,MainPID,InvocationID'], capture_output=True, text=True, timeout=5)
        if result.returncode:
            raise Error(result.stderr.strip() or 'Cannot read native unit state')
        return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)

    def state(self):
        return self.unit_info().get('ActiveState', 'inactive')

    def running(self):
        return self.state() == 'active'

    def configuration_signature(self, target):
        paths = [self.unit_path(target['model']['backend'])]
        if target['model']['backend'] == 'ollama':
            paths.append(self.store.path('native') / 'ollama-preload.json')
        return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths if path.exists()}

    def configuration_matches(self, target):
        runtime = read(self.store.path('runtime.json'), {})
        return (self.owned(target['model']['backend']) and runtime.get('native_config') is not None
                and runtime['native_config'] == self.configuration_signature(target))

    def observe(self, target=None):
        target = target or self.store.selected()
        model = target['model']
        runtime = ollama_observe(model['name'], missing_ok=True) if model['backend'] == 'ollama' else llama_observe(model['name'])
        if runtime is None:
            runtime = {'model': model['name'], 'upstream': ollama_endpoint(), 'context': None, 'resources': {}}
        info = self.unit_info(target)
        log = self.store.path('native') / (model['backend'] + '.log')
        launch = None
        if log.exists():
            from .telemetry import launch_reference
            launch = launch_reference(log, 0, info.get('InvocationID'))
        return {**runtime, 'model': model['name'], 'display_name': model['name'], 'backend': model['backend'],
                'key': model['key'], 'fingerprint': fingerprint(target), 'launch': launch,
                'native_config': self.configuration_signature(target),
                'log_path': str(log), 'pid': int(info.get('MainPID', 0)),
                'base_url': (ollama_endpoint() if model['backend'] == 'ollama' else llama_endpoint()) + '/v1',
                'capabilities': {'native_direct_connection': True}}

    def wait(self, target):
        stage('等待原生底座和模型加载；原生日志：maa logs')
        end = time.monotonic() + int(os.environ.get('MAA_START_TIMEOUT', '600'))
        last = ''
        while time.monotonic() < end:
            state = self.unit_info(target)
            if state.get('ActiveState') == 'failed' or (state.get('SubState') == 'auto-restart' and state.get('Result') not in ('success', None)):
                raise Error('Native service failed; inspect maa logs')
            try:
                if self.unit_info(target).get('ActiveState') == 'failed':
                    raise Error('Native service failed; inspect maa logs')
                observed = self.observe(target)
                context = observed.get('context')
                if (type(context) is int and context > 0 and not observed.get('resources', {}).get('sleeping')
                        and self.unit_info(target).get('ActiveState') == 'active'):
                    if observed['backend'] == 'llamacpp':
                        request(observed['base_url'] + '/responses', {'model': observed['model'], 'input': 'Hi',
                                'max_output_tokens': 1, 'stream': False}, timeout=600)
                    write(self.store.path('runtime.json'), observed)
                    return observed
            except Error as exc:
                last = str(exc)
                if self.unit_info(target).get('ActiveState') == 'failed':
                    raise Error(last)
            time.sleep(.2)
        raise Error('Native backend readiness timed out: ' + last)
