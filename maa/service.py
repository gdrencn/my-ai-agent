"""One systemd service owns either native backend and its local API adapter."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import sys
import threading
import time
import uuid
from . import bridge
from .backends import (llama_arguments, llama_observe, ollama_capabilities, check_options,
                       binary, ollama_environment, ollama_endpoint, ollama_load, stop_process, wait_api, llama_endpoint)
from .models import verify_file
from .store import Error, Store, atomic, write
from .output import stage
from .telemetry import launch_reference, native_allocations, UsageRecorder

UNIT = 'maa.service'


def fingerprint(target):
    return hashlib.sha256(json.dumps(target, sort_keys=True).encode()).hexdigest()


def privileged(command, **kwargs):
    return subprocess.run(([] if os.geteuid() == 0 else ['sudo']) + command, check=True, **kwargs)


def escaped(value):
    return '"' + str(value).replace('%', '%%').replace('\\', '\\\\').replace('"', '\\"') + '"'


class Controller:
    def __init__(self, store):
        self.store = store

    def ensure(self):
        from .install import require_container
        require_container()
        if not Path('/run/systemd/system').exists():
            raise Error('maa requires systemd inside the mas container')
        user = pwd.getpwuid(os.getuid()).pw_name
        app = Path.home() / '.local/share/my-ai-agent/maa.pyz'
        if not app.is_file():
            raise Error('Install the packaged maa first; system service cannot use a checkout entry')
        unit = Path('/etc/systemd/system') / UNIT
        marker = f'# my-ai-agent owner uid={os.getuid()}'
        if unit.exists() and marker not in unit.read_text():
            raise Error('maa.service belongs to another installation/user; refusing to overwrite it')
        text = f'''{marker}
[Unit]
Description=my-ai-agent selected local model
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User={user}
Environment=HOME={escaped(Path.home())}
Environment=MAA_HOME={escaped(self.store.root)}
Environment=CODEX_HOME={escaped(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))}
Environment=PATH={escaped(str(Path.home() / '.local/bin') + ':/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin')}
Environment=PYTHONUNBUFFERED=1
ExecStart={escaped(sys.executable)} {escaped(app)} _serve
KillMode=control-group
TimeoutStopSec=30
Restart=on-failure
RestartSec=10
[Install]
WantedBy=multi-user.target
'''
        from .backends import native_environment
        forwarded = {k: v for k, v in native_environment().items()
                     if k.startswith('LLAMA_ARG_') or k in ('OLLAMA_HOST', 'OLLAMA_MODELS')}
        extra = ''.join('Environment=' + escaped(k + '=' + v) + '\n' for k, v in sorted(forwarded.items()))
        text = text.replace('Environment=PYTHONUNBUFFERED=1\n', 'Environment=PYTHONUNBUFFERED=1\n' + extra)
        if not unit.exists() or unit.read_text() != text:
            temp = self.store.path('maa.service')
            atomic(temp, text, 0o644)
            privileged(['install', '-m', '644', str(temp), str(unit)])
            privileged(['systemctl', 'daemon-reload'])
        privileged(['systemctl', 'enable', UNIT], stdout=subprocess.DEVNULL)

    def running(self):
        return self.state() == 'active'

    def state(self):
        result = subprocess.run(['systemctl', 'show', '--property=ActiveState', '--value', UNIT],
                                capture_output=True, text=True, timeout=3)
        if result.returncode:
            raise Error((result.stderr or result.stdout).strip() or 'Cannot read maa service state')
        state = result.stdout.strip()
        if state not in ('active', 'inactive', 'failed', 'activating', 'deactivating', 'reloading'):
            raise Error('Unknown maa service state: ' + state)
        return state

    def stop(self):
        privileged(['systemctl', 'stop', UNIT])
        self.store.path('runtime.json').unlink(missing_ok=True)

    def start(self):
        self.ensure()
        self.store.path('runtime.json').unlink(missing_ok=True)
        stage('启动底座服务')
        privileged(['systemctl', 'restart', UNIT])

    def wait(self, target):
        from .store import read
        deadline = time.monotonic() + int(os.environ.get('MAA_START_TIMEOUT', '600'))
        stamp = fingerprint(target)
        stage('等待底座启动和模型加载；原生日志：maa logs')
        while time.monotonic() < deadline:
            runtime = read(self.store.path('runtime.json'))
            if runtime and runtime.get('fingerprint') == stamp:
                if runtime.get('error'):
                    raise Error(runtime['error'])
                return runtime
            time.sleep(.2)
        raise Error('Model startup timed out; run maa logs to inspect the native diagnostic')


def boot_target(store):
    # A candidate is allowed only while its initiating transaction is alive.
    # After a crash/reboot, boot the last validated selection, never a candidate.
    from .store import read
    pending = read(store.path('pending.json'))
    valid_pending = False
    if pending and pending.get('boot_id') == Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        try:
            current_start = Path(f'/proc/{pending["pid"]}/stat').read_text().rsplit(')', 1)[1].split()[19]
            valid_pending = current_start == pending.get('process_start')
        except (OSError, KeyError, IndexError):
            pass
    return store.target() if valid_pending else store.selected()


def serve(store=None):
    store = store or Store()
    target = boot_target(store)
    store.path('runtime.json').unlink(missing_ok=True)
    if not target:
        return
    process = adapter = None
    stopped = threading.Event()
    def terminate(*_):
        stopped.set()
        if process and process.poll() is None:
            process.terminate()
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    stamp = fingerprint(target)
    try:
        model, values = target['model'], target['settings']
        verify_file(model)
        if model['backend'] == 'ollama':
            help_text = ollama_capabilities()
            check_options(help_text, ['--fit', '--fit-target'])
            if values['mtp']:
                check_options(help_text, ['draft-mtp', '--spec-draft-type-k', '--spec-draft-type-v'])
            command, env = [binary('ollama'), 'serve'], ollama_environment(values)
            health = ollama_endpoint() + '/api/version'
        else:
            from .backends import native_environment
            command, env = llama_arguments(model, values), native_environment()
            health = llama_endpoint() + '/health'
        with store.path('native.log').open('ab', buffering=0) as log:
            launch_offset = log.tell()
            log.write(('\n=== my-ai-agent launch ' + model['name'] + ' ===\n').encode())
            launch = launch_reference(store.path('native.log'), launch_offset, uuid.uuid4().hex)
            try:
                from .http import request
                request(health, timeout=1)
            except Error:
                pass
            else:
                raise Error('An unmanaged native backend is already listening; stop it before maa start')
            process = subprocess.Popen(command, env=env, stdout=log, stderr=log)
            wait_api(health, process, timeout=600)
            if model['backend'] == 'llamacpp':
                # The official launcher can expose metadata before its model is
                # resident. Complete a tiny request before accepting the target.
                request(llama_endpoint() + '/v1/chat/completions',
                        {'model': model['name'], 'messages': [{'role': 'user', 'content': 'Hi'}],
                         'max_tokens': 1, 'stream': False}, timeout=600)
            runtime = ollama_load(target) if model['backend'] == 'ollama' else llama_observe(model['name'])
            runtime.update(backend=model['backend'], key=model['key'], fingerprint=stamp,
                           display_name=model['name'], launch=launch,
                           base_url='http://127.0.0.1:18443/v1', pid=os.getpid(),
                           capabilities={'hosted_web_search': False, 'stateless_responses': True})
            runtime['resources']['gpu_layers'] = native_allocations(store, runtime)['gpu_layers']
            adapter = bridge.server(runtime, record_usage=UsageRecorder(store, runtime))
            thread = threading.Thread(target=adapter.serve_forever, daemon=True)
            thread.start()
            from .codex import profile
            profile(runtime, values)
            write(store.path('runtime.json'), runtime)
            while not stopped.wait(.5):
                if process.poll() is not None:
                    raise Error(f'Native backend exited with code {process.returncode}')
    except Exception as exc:
        tail = ''
        try:
            with store.path('native.log').open('rb') as log:
                log.seek(0, 2)
                log.seek(max(0, log.tell() - 8192))
                tail = log.read().decode(errors='replace')
        except OSError:
            pass
        write(store.path('runtime.json'), {'fingerprint': stamp, 'error': str(exc) + '\n' + tail})
        raise
    finally:
        if adapter:
            adapter.shutdown()
            adapter.server_close()
        if process:
            stop_process(process)
