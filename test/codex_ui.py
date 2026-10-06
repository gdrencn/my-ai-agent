"""Drive the actual Codex TUI and verify its local-only model picker."""
import fcntl
import os
import pty
import re
import select
import signal
import struct
import termios
import time
from pathlib import Path


def picker(command, display_name):
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.chdir(Path.home())
        os.execv(command, [command, '--no-alt-screen'])
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', 40, 160, 0, 0))
    output = b''
    started, sent, selected = time.monotonic(), False, False
    sent_at, confirmed = None, False
    original = termios.tcgetattr(fd)
    def plain(data):
        return re.sub(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))', '', data.decode(errors='replace'))
    try:
        deadline = started + 45
        while time.monotonic() < deadline:
            if sent_at is not None and not confirmed and time.monotonic() - sent_at > 1:
                os.write(fd, b'\r')
                confirmed = True
            if select.select([fd], [], [], .2)[0]:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    break
                output += chunk
                if b'\x1b[6n' in chunk:
                    os.write(fd, b'\x1b[1;1R')
                text = plain(output)
                if 'trust this' in text.lower() or 'Do you trust' in text:
                    os.write(fd, b'\r')
                if not sent and ('context left' in text or 'for shortcuts' in text or 'To get started' in text):
                    os.write(fd, b'/model\r')
                    sent = True
                    sent_at = time.monotonic()
                if sent and ('select model' in text.lower() or 'choose a model' in text.lower()):
                    selected = True
                    break
            done, status = os.waitpid(pid, os.WNOHANG)
            if done:
                pid = 0
                raise AssertionError('Codex exited before model picker: ' + plain(output)[-12000:])
        text = plain(output)
        assert selected, 'Model picker did not open: ' + text[-12000:]
        screen = text[max(text.lower().rfind('select model'), text.lower().rfind('choose a model')):]
        assert display_name in screen, screen
        assert not re.search(r'GPT-[0-9]|gpt-[0-9]', screen), screen
        assert 'fallback metadata' not in text and 'requires embedded mode' not in text, text
        os.write(fd, b'\x1b')
        time.sleep(.3)
        os.write(fd, b'\x03')
        end = time.monotonic() + 5
        while time.monotonic() < end:
            if select.select([fd], [], [], .1)[0]:
                try:
                    output += os.read(fd, 65536)
                except OSError:
                    pass
            done, status = os.waitpid(pid, os.WNOHANG)
            if done:
                pid = 0
                break
            os.write(fd, b'\x03')
        assert not pid, 'Codex did not exit after cancellation'
        assert termios.tcgetattr(fd)[3] == original[3], 'Terminal mode not restored'
        return {'local_only': True, 'warnings_absent': True,
                'elapsed_seconds': round(time.monotonic() - started, 3), 'picker': screen[-6000:]}
    finally:
        if pid:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        os.close(fd)
