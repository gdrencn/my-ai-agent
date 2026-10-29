"""Authentication and live diagnostic contracts, without changing host sudo."""
import contextlib
import io
import json
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from unittest.mock import patch

from maa.output import run
from maa.service import privileged


SUDO = r"""#!/usr/bin/env python3
import json, os, sys, termios
from pathlib import Path
args = sys.argv[1:]
base = Path(__file__).parent
with (base / 'calls').open('a') as log:
    log.write(json.dumps(args) + '\n')
cached = (base / 'cached').exists()
if args == ['-n', '-v']:
    raise SystemExit(0 if cached else 1)
if args and args[0] == '-n':
    args.pop(0)
    if not cached and not (base / 'nopasswd').exists():
        print('SUDO_PASSWORD_REQUIRED', file=sys.stderr, flush=True)
        raise SystemExit(1)
if not cached and not (base / 'nopasswd').exists():
    terminal = os.open('/dev/tty', os.O_RDWR)
    before = termios.tcgetattr(terminal)
    hidden = termios.tcgetattr(terminal)
    hidden[3] &= ~termios.ECHO
    try:
        termios.tcsetattr(terminal, termios.TCSANOW, hidden)
        os.write(2, b'AUTH_PASSWORD:')
        answer = bytearray()
        while True:
            value = os.read(terminal, 1)
            if value in (b'\r', b'\n', b''):
                break
            answer += value
        if answer != b'fixture-secret':
            print('AUTH_REJECTED', file=sys.stderr, flush=True)
            raise SystemExit(1)
        (base / 'cached').touch()
        print('AUTH_OK', file=sys.stderr, flush=True)
    finally:
        termios.tcsetattr(terminal, termios.TCSANOW, before)
        os.close(terminal)
os.execvp(args[0], args)
"""


class Privilege(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.base = Path(self.folder.name)
        sudo = self.base / 'sudo'
        sudo.write_text(SUDO)
        sudo.chmod(0o755)
        self.env = patch.dict(os.environ, {'PATH': str(self.base) + os.pathsep + os.environ['PATH'],
                                           'XDG_CONFIG_HOME': str(self.base / 'preferences')})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.folder.cleanup()

    def calls(self):
        return [json.loads(line) for line in (self.base / 'calls').read_text().splitlines()]

    def terminal(self, code, *, password=b'fixture-secret\n', cancel=False):
        root = str(Path(__file__).resolve().parent.parent)
        code = ('import os, sys, subprocess, json\n'
                f'sys.path.insert(0, {root!r})\n'
                'from unittest.mock import patch\n'
                'from maa.output import operation, run\n'
                'from maa.service import privileged\n' + code)
        pid, fd = pty.fork()
        if pid == 0:
            os.execv(sys.executable, [sys.executable, '-c', code])
        before = termios.tcgetattr(fd)
        output = b''
        answered = False
        status = None
        try:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if select.select([fd], [], [], .05)[0]:
                    try:
                        value = os.read(fd, 65536)
                    except OSError:
                        break
                    if not value:
                        break
                    output += value
                if b'AUTH_PASSWORD:' in output and not answered:
                    self.assertNotIn(b'COMMAND_FINISHED', output)
                    os.write(fd, b'\x03' if cancel else password)
                    answered = True
                if pid:
                    done, status_value = os.waitpid(pid, os.WNOHANG)
                    if done:
                        status = os.waitstatus_to_exitcode(status_value)
                        pid = 0
                        # Drain any output written just before exit.
                        continue
                if status is not None:
                    break
            if pid:
                done, status_value = os.waitpid(pid, os.WNOHANG)
                if done:
                    status = os.waitstatus_to_exitcode(status_value)
                    pid = 0
            self.assertIsNotNone(status, output.decode(errors='replace'))
            self.assertEqual(before[3], termios.tcgetattr(fd)[3])
            self.assertNotIn(b'fixture-secret', output)
            return status, output.decode(errors='replace'), answered
        finally:
            if pid:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            os.close(fd)

    def test_password_prompt_is_live_with_piped_stdin_and_json_stdout(self):
        command = [sys.executable, '-c', 'import sys;print("{\\"ok\\": true}");print("NATIVE_DIAGNOSTIC", file=sys.stderr)']
        # Match curl | bash: stdin is a pipe, the controlling TTY still exists.
        code = ("r,w=os.pipe();os.close(w);os.dup2(r,0);os.close(r)\n"
                "with patch('maa.service.os.geteuid', return_value=1000):\n"
                " with operation('AUTHENTICATING'):\n"
                f"  result=privileged({command!r}, stdout=subprocess.PIPE, text=True)\n"
                " assert json.loads(result.stdout)=={'ok':True}\n"
                " print('COMMAND_FINISHED')\n")
        status, output, answered = self.terminal(code)
        self.assertEqual(status, 0, output)
        self.assertTrue(answered)
        self.assertIn('NATIVE_DIAGNOSTIC', output)
        self.assertIn('COMMAND_FINISHED', output)
        self.assertIn('\x1b[?25h', output)
        self.assertEqual(len([row for row in self.calls() if row != ['-n', '-v']]), 1)

    def test_live_parent_capture_keeps_nested_authentication_visible(self):
        root = str(Path(__file__).resolve().parent.parent)
        child = (f"import sys;sys.path.insert(0,{root!r})\n"
                 "import subprocess;from unittest.mock import patch;from maa.service import privileged\n"
                 "with patch('maa.service.os.geteuid', return_value=1000):\n"
                 " privileged(['true'], stdout=subprocess.DEVNULL)\n"
                 "print('{\"ok\":true}')\n")
        command = [sys.executable, '-c', child]
        code = ("with operation('PARENT'):\n"
                f" result=run({command!r}, native=True, stdout=subprocess.PIPE, tee_stderr=True, text=True)\n"
                " assert result.returncode==0, result.stderr\n"
                " assert json.loads(result.stdout)=={'ok':True}\n"
                " assert 'AUTH_PASSWORD:' in result.stderr\n"
                " print('COMMAND_FINISHED')\n")
        status, output, answered = self.terminal(code)
        self.assertEqual(status, 0, output)
        self.assertTrue(answered)
        self.assertEqual(output.count('AUTH_PASSWORD:'), 1)

    def test_authentication_failure_preserves_exit_and_restores_terminal(self):
        code = ("with patch('maa.service.os.geteuid', return_value=1000):\n"
                " try:\n"
                "  with operation('REJECT'):\n"
                "   privileged(['true'], stdout=subprocess.DEVNULL)\n"
                " except subprocess.CalledProcessError as error:\n"
                "  assert error.returncode==1\n"
                " else:\n  raise AssertionError('authentication unexpectedly accepted')\n"
                "print('COMMAND_FINISHED')\n")
        status, output, answered = self.terminal(code, password=b'wrong\n')
        self.assertEqual(status, 0, output)
        self.assertTrue(answered)
        self.assertIn('AUTH_REJECTED', output)
        self.assertIn('\x1b[?25h', output)

    def test_interrupt_during_authentication_restores_terminal(self):
        code = ("try:\n"
                " with patch('maa.service.os.geteuid', return_value=1000):\n"
                "  with operation('INTERRUPT'):\n"
                "   privileged(['true'])\n"
                "except KeyboardInterrupt:\n print('AUTH_CANCELLED')\n")
        status, output, answered = self.terminal(code, cancel=True)
        self.assertEqual(status, 0, output)
        self.assertTrue(answered)
        self.assertIn('AUTH_CANCELLED', output)
        self.assertIn('\x1b[?25h', output)
        self.assertFalse((self.base / 'cached').exists())

    def test_cached_and_command_specific_nopasswd_do_not_prompt(self):
        for marker in ('cached', 'nopasswd'):
            with self.subTest(marker=marker):
                (self.base / marker).touch()
                code = ("with patch('maa.service.os.geteuid', return_value=1000):\n"
                        " with operation('CACHED'):\n"
                        "  privileged(['true'], stdout=subprocess.DEVNULL)\n"
                        "print('COMMAND_FINISHED')\n")
                status, output, answered = self.terminal(code)
                self.assertEqual(status, 0, output)
                self.assertFalse(answered)
                (self.base / marker).unlink()

    def test_noninteractive_missing_authentication_fails_without_waiting(self):
        with patch('maa.service.os.geteuid', return_value=1000):
            started = time.monotonic()
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                privileged(['true'], capture_output=True, text=True, timeout=2)
        self.assertLess(time.monotonic() - started, 2)
        self.assertIn('SUDO_PASSWORD_REQUIRED', caught.exception.stderr)
        self.assertEqual(self.calls(), [['-n', 'true']])

    def test_root_bypasses_sudo(self):
        with patch('maa.service.os.geteuid', return_value=0):
            result = privileged([sys.executable, '-c', 'print("ROOT_RESULT")'], capture_output=True, text=True)
        self.assertEqual(result.stdout, 'ROOT_RESULT\n')
        self.assertFalse((self.base / 'calls').exists())

    def test_live_stderr_retains_text_bytes_and_failure_diagnostics(self):
        command = [sys.executable, '-c', 'import sys;print("JSON_STDOUT");print("LIVE_STDERR",file=sys.stderr);sys.exit(7)']
        for text in (False, True):
            with self.subTest(text=text), contextlib.redirect_stderr(io.StringIO()) as output:
                with self.assertRaises(subprocess.CalledProcessError) as caught:
                    run(command, native=True, stdout=subprocess.PIPE, tee_stderr=True, text=text, check=True)
                self.assertEqual(caught.exception.returncode, 7)
                self.assertEqual(caught.exception.stdout, 'JSON_STDOUT\n' if text else b'JSON_STDOUT\n')
                self.assertEqual(caught.exception.stderr, 'LIVE_STDERR\n' if text else b'LIVE_STDERR\n')
                self.assertEqual(output.getvalue(), 'LIVE_STDERR\n')

    def test_live_stderr_timeout_retains_partial_diagnostics(self):
        command = [sys.executable, '-c', 'import sys,time;print("PARTIAL_OUT",flush=True);print("PARTIAL_ERR",file=sys.stderr,flush=True);time.sleep(5)']
        with contextlib.redirect_stderr(io.StringIO()) as output:
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                run(command, native=True, stdout=subprocess.PIPE, tee_stderr=True, text=True, timeout=.2)
        self.assertIn(b'PARTIAL_OUT', caught.exception.stdout)
        self.assertIn('PARTIAL_ERR', caught.exception.stderr)
        self.assertIn('PARTIAL_ERR', output.getvalue())
