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
            os.environ['TERM'] = 'xterm-256color'
            os.environ.pop('NO_COLOR', None)
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

    def test_grouped_menu_returns_to_main_and_preserves_focus(self):
        operation = ("from unittest.mock import patch\nfrom maa.ui import main\n"
                     "class Manager:\n def model_status(self, **kwargs):\n"
                     "  return {'model':'fixture.gguf','state':'running'}\n"
                     "with patch('maa.ui.Manager', Manager):\n interactive(main)\nprint('MENU_EXIT')")
        keys = b'\r\x1b[A\r\x1b[A\r'
        value = self.session(operation, keys, '当前模型', (20, 100))
        self.assertIn('本地模型管理', value)
        self.assertIn('当前模型状态', value)
        self.assertIn('Codex 配置', value)
        self.assertIn('codex-local 配置', value)
        self.assertNotIn('当前状态与配置', value)
        self.assertIn('MENU_EXIT', value)
        self.assertIn('\x1b[32m运行中\x1b[39m', value)

    def test_configuration_colors_pending_values_and_cancel(self):
        operation = ("from maa.ui import edit_settings\nfrom maa.settings import settings\n"
                     "try:\n interactive(lambda ui: edit_settings(ui, {'mtp_supported':False}, settings()))\n"
                     "except Cancelled:\n print('DRAFT_CANCELLED')")
        value = self.session(operation, b'\r4096\r\x1b[A\r', '上下文大小', (24, 120))
        self.assertIn('\x1b[36m262144\x1b[39m', value)
        self.assertIn('\x1b[36m4096\x1b[39m', value)
        self.assertIn('\x1b[90m不可用', value)
        self.assertIn('未应用修改', value)
        self.assertIn('DRAFT_CANCELLED', value)

    def test_yolo_nested_switch_restores_original_in_private_home(self):
        operation = ("import tempfile, os\nfrom pathlib import Path\nfrom maa import codex\n"
                     "from maa.ui import global_settings\nwith tempfile.TemporaryDirectory() as folder:\n"
                     " os.environ['CODEX_HOME']=folder\n"
                     " Path(folder,'config.toml').write_text('approval_policy=\"on-request\"\\n')\n"
                     " interactive(global_settings)\n"
                     " assert codex.parse(Path(folder,'config.toml').read_text())['approval_policy']=='on-request'\n"
                     " assert not Path(folder,'maa-yolo-recovery.json').exists()\nprint('YOLO_RESTORED')")
        keys = b'\r\x1b[A\r\r\x1b[B\r\x1b[A\r'
        value = self.session(operation, keys, 'YOLO 模式', (16, 100))
        self.assertIn('关闭（恢复原设置）', value)
        self.assertIn('\x1b[32m开启\x1b[39m', value)
        self.assertIn('\x1b[90m关闭\x1b[39m', value)
        self.assertIn('YOLO_RESTORED', value)

    def test_no_color_retains_configuration_text(self):
        operation = ("import os\nos.environ['NO_COLOR']='1'\nfrom maa.ui import edit_settings\n"
                     "from maa.settings import settings\ntry:\n"
                     " interactive(lambda ui: edit_settings(ui, {'mtp_supported':False}, settings()))\n"
                     "except Cancelled:\n print('NO_COLOR_EXIT')")
        value = self.session(operation, b'\x1b[A\r', '上下文大小', (24, 120))
        self.assertIn('上下文大小：262144', value)
        self.assertNotIn('\x1b[36m', value)
        self.assertNotIn('\x1b[32m', value)
        self.assertIn('NO_COLOR_EXIT', value)

    def test_readonly_activation_keeps_same_prompt_and_does_not_apply(self):
        operation = ("from maa.ui import edit_settings, value_line\nfrom maa.settings import settings\n"
                     "try:\n interactive(lambda ui: edit_settings(ui, {'mtp_supported':False}, settings(),\n"
                     " keys=('reasoning',), title='READONLY_TEST', readonly=[('ctx',value_line('只读上下文','8192'))]))\n"
                     "except Cancelled:\n print('READONLY_CANCELLED')")
        output = self.session(operation, b'\x1b[B\r\x1b[C\x1b[A\x1b', 'READONLY_TEST', (16, 100))
        self.assertEqual(output.count('READONLY_TEST'), 1)
        self.assertIn('READONLY_CANCELLED', output)

    def test_long_model_details_and_current_default_in_narrow_terminal(self):
        operation = ("from maa.ui import choose\n"
                     "print('RESULT', interactive(lambda ui: choose(ui, 'MODEL_PICKER',\n"
                     " [('a','short.gguf'),('b','Qwen3-27B-UD-Q4_K_XL.gguf（当前）')], 'b',\n"
                     " details={'b':'模型：Qwen3-27B-UD-Q4_K_XL.gguf\\n来源：publisher/repository'})))")
        output = self.session(operation, b'\r', 'MODEL_PICKER', (12, 32))
        self.assertIn('UD-Q4_K_XL.gguf', output)
        self.assertIn('publisher/repository', output)
        self.assertIn('RESULT b', output)

    def test_same_basename_model_choices_show_paths_revision_and_current_focus(self):
        operation = ("from maa.ui import choose, model_choices\n"
                     "rows=[{'key':'a','filename':'dir-a/model.gguf','repo':'publisher/repo','revision':'rev-a'},\n"
                     " {'key':'b','filename':'dir-b/model.gguf','repo':'publisher/repo','revision':'rev-b'}]\n"
                     "options,details=model_choices(rows,'b')\n"
                     "assert options[0][1] != options[1][1]\n"
                     "print('RESULT',interactive(lambda ui: choose(ui,'DISTINCT_MODELS',options,'b',details)))")
        output = self.session(operation, b'\r', 'DISTINCT_MODELS', (14, 32))
        self.assertIn('dir-b/model.gguf', output)
        self.assertIn('rev-b', output)
        self.assertIn('RESULT b', output)

    def test_local_same_basename_choices_include_full_paths(self):
        from maa.ui import model_choices
        options, details = model_choices([
            {'key': 'a', 'name': 'model.gguf', 'path': '/models/a/model.gguf'},
            {'key': 'b', 'name': 'model.gguf', 'path': '/models/b/model.gguf'}])
        self.assertNotEqual(options[0][1], options[1][1])
        self.assertIn('/models/a/model.gguf', details['a'])
        self.assertIn('/models/b/model.gguf', details['b'])

    def test_native_command_diagnostic_starts_on_its_own_line(self):
        operation = ("import sys\nfrom unittest.mock import patch\n"
                     "from maa.output import operation\nfrom maa.service import privileged\n"
                     "with operation('NATIVE_BOUNDARY'):\n"
                     " with patch('maa.service.os.geteuid',return_value=0):\n"
                     "  privileged([sys.executable,'-c',\"import sys;print('NATIVE_STDERR',file=sys.stderr,flush=True)\"])\n")
        output = self.session(operation, b'', 'NATIVE_BOUNDARY', (12, 100))
        self.assertIn('\nNATIVE_STDERR', output)
        self.assertNotIn('秒NATIVE_STDERR', output)

    def test_unavailable_mtp_activation_is_inert(self):
        operation = ("from maa.ui import edit_settings\nfrom maa.settings import settings\n"
                     "try:\n interactive(lambda ui: edit_settings(ui,{'mtp_supported':False},settings(),title='UNAVAILABLE_MTP'))\n"
                     "except Cancelled:\n print('MTP_CANCELLED')")
        output = self.session(operation, b'\x1b[B'*6+b'\r\x1b[C\x1b', 'UNAVAILABLE_MTP', (24, 120))
        self.assertEqual(output.count('UNAVAILABLE_MTP'), 1)
        self.assertIn('MTP_CANCELLED', output)


if __name__ == '__main__':
    unittest.main()
