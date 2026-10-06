import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import sys
import termios
import time
import unittest
import fcntl


class Terminal(unittest.TestCase):
    def session(self, operation, keys, marker, size=(12, 32)):
        pid, fd = pty.fork()
        if pid == 0:
            root = str(Path(__file__).resolve().parent.parent)
            code = f'import sys;sys.path.insert(0,{root!r})\nfrom maa.menu import interactive, Cancelled\n' + operation
            os.execv(sys.executable, [sys.executable, '-c', code])
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', *size, 0, 0))
        before = termios.tcgetattr(fd)
        output = b''
        try:
            deadline = time.monotonic() + 8
            while marker.encode() not in output and time.monotonic() < deadline:
                if select.select([fd], [], [], .2)[0]:
                    output += os.read(fd, 65536)
            self.assertIn(marker.encode(), output)
            os.write(fd, keys)
            while time.monotonic() < deadline:
                if select.select([fd], [], [], .2)[0]:
                    try:
                        output += os.read(fd, 65536)
                    except OSError:
                        break
                done, status = os.waitpid(pid, os.WNOHANG)
                if done:
                    pid = 0
                    self.assertEqual(os.waitstatus_to_exitcode(status), 0)
                    break
            after = termios.tcgetattr(fd)
            self.assertEqual(before[3], after[3])
            self.assertIn(b'\x1b[?25h', output)
            self.assertNotIn(b'\x1b[2J', output)
            return output.decode(errors='replace')
        finally:
            if pid:
                try:
                    os.kill(pid, 9)
                    os.waitpid(pid, 0)
                except ProcessLookupError:
                    pass
            os.close(fd)

    def test_arrow_wrap_and_enter_in_real_pty(self):
        value = self.session("print('RESULT', interactive(lambda ui: ui.choose('Select model', [('a','模型甲'),('b','模型乙')])))", b'\x1b[A\r', 'Select model')
        self.assertIn('RESULT b', value)

    def test_utf8_input_cursor_editing_in_real_pty(self):
        value = self.session("print('RESULT', interactive(lambda ui: ui.input('Input model')))", '模型ab'.encode() + b'\x1b[D\x7fX\r', 'Input model')
        self.assertIn('RESULT 模型Xb', value)

    def test_cancel_restores_terminal(self):
        operation = "try:\n print(interactive(lambda ui: ui.input('Cancel model')))\nexcept Cancelled:\n print('CANCELLED')"
        value = self.session(operation, b'\x1b', 'Cancel model', (6, 20))
        self.assertIn('CANCELLED', value)


if __name__ == '__main__':
    unittest.main()
