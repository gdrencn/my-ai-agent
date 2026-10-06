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

    def test_wait_refreshes_one_line_and_keeps_native_output(self):
        operation = ("import time\nfrom maa.output import operation, stage, native_output\n"
                     "with operation('加载模型'):\n"
                     " stage('准备')\n time.sleep(1.2)\n"
                     " with native_output():\n  print('NATIVE_DOWNLOAD', flush=True)\n"
                     " stage('核验')\n time.sleep(1.1)\n")
        output = self.session(operation, b'', '加载模型', (12, 60))
        self.assertIn('已等待 1.', output)
        self.assertIn('核验', output)
        self.assertIn('[成功]', output)
        self.assertIn('NATIVE_DOWNLOAD', output)
        self.assertGreater(output.count('\r\x1b[2K'), 3)
        self.assertLess(output.count('\n'), 8)

    def test_failed_wait_keeps_elapsed_and_restores_prompt(self):
        operation = ("from maa.output import operation, stage\n"
                     "try:\n with operation('等待故障'):\n"
                     "  stage('恢复原目标')\n  raise ValueError('expected')\n"
                     "except ValueError:\n print('RECOVERED')\n")
        output = self.session(operation, b'', '等待故障', (6, 80))
        self.assertIn('[失败]', output)
        self.assertIn('恢复原目标', output)
        self.assertIn('已等待', output)
        self.assertIn('RECOVERED', output)


if __name__ == '__main__':
    unittest.main()
