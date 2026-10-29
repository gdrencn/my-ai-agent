"""Read native Codex configuration over stdio; never create a turn or tool call."""
import json
import os
import selectors
import signal
import subprocess
import tempfile
import time
from .backends import binary
from .store import Error


def configuration(timeout=20):
    command = [binary('codex'), '--no-daemon', 'app-server', '--stdio']
    # stderr can contain account or plugin diagnostics; do not copy it to reports.
    with tempfile.TemporaryFile() as diagnostics:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=diagnostics, start_new_session=True)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        pending, initialized = b'', False
        deadline = time.monotonic() + timeout
        def send(value):
            process.stdin.write(json.dumps(value).encode() + b'\n')
            process.stdin.flush()
        try:
            send({'id': 1, 'method': 'initialize', 'params': {
                'clientInfo': {'name': 'my_ai_agent_check', 'version': '1'}}})
            while time.monotonic() < deadline:
                if not selector.select(min(1, max(0, deadline - time.monotonic()))):
                    continue
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    raise Error('Codex configuration reader exited before returning its state')
                pending += chunk
                if len(pending) > 4 * 1024 * 1024:
                    raise Error('Codex configuration response is oversized')
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    message = json.loads(line)
                    if message.get('id') == 1:
                        if 'error' in message:
                            raise Error('Codex rejected configuration initialization')
                        send({'method': 'initialized', 'params': {}})
                        send({'id': 2, 'method': 'config/read', 'params': {'includeLayers': False}})
                        initialized = True
                    elif message.get('id') == 2 and initialized:
                        if 'error' in message:
                            raise Error('Codex could not return its configuration')
                        config = message.get('result', {}).get('config')
                        if not isinstance(config, dict):
                            raise Error('Codex returned an invalid configuration')
                        # Never expose unrelated config, credentials or conversation data.
                        return {key: config.get(key) for key in ('approval_policy', 'sandbox_mode')}
            raise Error('Timed out reading Codex configuration')
        finally:
            selector.close()
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            process.stdin.close()
            process.stdout.close()
