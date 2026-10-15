import os
from pathlib import Path
import pty
import re
import select
import struct
import subprocess
import sys
import termios
import time
import unittest
import fcntl
import tempfile
from unittest.mock import patch


class Terminal(unittest.TestCase):
    def setUp(self):
        self.preferences = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'XDG_CONFIG_HOME': self.preferences.name})
        self.env.start()
        from maa.preferences import set_language
        set_language('zh_cn')

    def tearDown(self):
        self.env.stop()
        self.preferences.cleanup()

    def receive(self, fd, marker, seconds=4):
        output, deadline = b'', time.monotonic() + seconds
        while time.monotonic() < deadline:
            if select.select([fd], [], [], .1)[0]:
                try:
                    output += os.read(fd, 65536)
                except OSError:
                    break
                plain = re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', output.decode(errors='replace'))
                if marker in plain:
                    return output
        self.fail(f'Did not receive {marker!r}: {output.decode(errors="replace")}')

    def menu_rows(self, output):
        """Replay inline cursor moves and erasure, including committed history."""
        rows, row, column = [[]], 0, 0
        for token in re.findall(r'\x1b\[[0-9;?]*[A-Za-z]|[^\x1b]', output):
            if token.startswith('\x1b'):
                number = token[2:-1]
                if token[-1] in ('A', 'B') and number.isdigit():
                    row = max(0, row + (1 if token[-1] == 'B' else -1) * int(number))
                    while len(rows) <= row:
                        rows.append([])
                elif token == '\x1b[2K':
                    rows[row] = []
                elif token == '\x1b[0J':
                    rows[row] = rows[row][:column]
                    del rows[row+1:]
                continue
            if token == '\r':
                column = 0
            elif token == '\n':
                row += 1
                if len(rows) <= row:
                    rows.append([])
            else:
                while len(rows[row]) <= column:
                    rows[row].append(' ')
                rows[row][column] = token
                column += 1
        return [''.join(line) for line in rows]

    def visible_lines(self, output):
        """Replay the controls used by Progress; retain committed terminal rows."""
        rows, line, cursor = [], [], 0
        for token in re.findall(r'\x1b\[[0-9;?]*[A-Za-z]|[^\x1b]', output):
            if token == '\x1b[2K':
                line = []
            elif token.startswith('\x1b'):
                continue
            elif token == '\r':
                cursor = 0
            elif token == '\n':
                rows.append(''.join(line))
                line, cursor = [], 0
            else:
                if cursor < len(line):
                    line[cursor] = token
                else:
                    line.append(token)
                cursor += 1
        return rows + ([''.join(line)] if line else [])

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
            if callable(keys):
                output += keys(fd)
            else:
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

    def test_language_first_selection_works_with_piped_stdin(self):
        code = ("from maa import preferences\npreferences.path().unlink()\n"
                "read,write=os.pipe();os.close(write);os.dup2(read,0);os.close(read)\n"
                "print('CHOSEN',preferences.installation_language())\n"
                "assert not preferences.path().exists()")
        value = self.session('import os\n' + code, b'\x1b[B\r', 'Select interface language', size=(12, 80))
        self.assertIn('CHOSEN en_us', value)

    def test_language_main_menu_switches_immediately_without_backend_calls(self):
        code = ("from maa import preferences,ui\npreferences.set_language('en_us')\n"
                "class Manager:\n"
                " def model_status(self,**kw):return {'model':None,'state':'unselected'}\n"
                " def __getattr__(self,name):raise AssertionError('Unexpected backend call '+name)\n"
                "ui.Manager=Manager\ninteractive(ui.main)\n"
                "print('LANGUAGE_FINAL',preferences.load()['language'])")
        def keys(fd):
            os.write(fd, b'\x1b[B'*5 + b'\r')
            output = self.receive(fd, 'Select interface language')
            os.write(fd, b'\x1b[A\r')
            output += self.receive(fd, '语言：简体中文 (zh_cn)')
            os.write(fd, b'\x1b')
            return output
        value = self.session(code, keys, 'Local model management', size=(18, 100))
        self.assertIn('语言已保存。', value)
        self.assertIn('LANGUAGE_FINAL zh_cn', value)

    def test_language_selection_cancel_keeps_preferences(self):
        code = ("from maa import preferences\npreferences.set_language('en_us')\n"
                "before=preferences.path().read_bytes()\n"
                "try:interactive(lambda screen:preferences.choose(screen,'en_us'))\n"
                "except Cancelled:pass\n"
                "assert preferences.path().read_bytes()==before\nprint('CANCELLED_LANGUAGE en_us')")
        value = self.session(code, b'\x1b', 'Select interface language', size=(12, 80))
        self.assertIn('CANCELLED_LANGUAGE en_us', value)

    def test_english_configuration_values_and_progress_in_real_terminal(self):
        code = ("from maa import preferences,ui\nfrom maa.settings import settings\n"
                "from maa.output import operation,stage\npreferences.set_language('en_us')\n"
                "model={'mtp_supported':False}\n"
                "try:interactive(lambda screen:ui.edit_settings(screen,model,settings()))\n"
                "except Cancelled:pass\n"
                "with operation('应用配置'):\n stage('等待原生底座和模型加载；原生日志：maa logs')\n"
                "print('ENGLISH_DONE')")
        value = self.session(code, b'\x1b', 'Model configuration', size=(18, 100))
        self.assertIn('Model configuration', value)
        self.assertIn('[Success]', value)
        self.assertIn('Apply configuration', value)
        self.assertNotIn('主模型 KV 格式', value)

    def test_utf8_input_cursor_editing_in_real_pty(self):
        value = self.session("print('RESULT', interactive(lambda ui: ui.input('Input model')))", '模型ab'.encode() + b'\x1b[D\x7fX\r', 'Input model')
        self.assertIn('RESULT 模型Xb', value)

    def test_secret_input_masks_editing_and_restores_terminal(self):
        code = ("value=interactive(lambda ui: ui.input('Private Token', secret=True))\n"
                "assert value=='SENSITIVE_TOKEN'\nprint('SECRET_ACCEPTED')")
        value = self.session(code, b'SENSITIVE_TOKEN\r', 'Private Token', (12, 70))
        self.assertIn('SECRET_ACCEPTED', value)
        self.assertNotIn('SENSITIVE_TOKEN', value)
        self.assertIn('********', value)

    def test_im_navigation_values_and_cancel_return_to_parent(self):
        code = ("import tempfile\nfrom pathlib import Path\nfrom maa.im.state import State\n"
                "from maa.im.manager import Connections\nfrom maa.im.ui import main\n"
                "from tests.test_im import FixtureController, record\n"
                "with tempfile.TemporaryDirectory() as folder:\n"
                " store=State(Path(folder)/'im')\n row=record('whatsapp')\n"
                " store.save({'version':1,'connections':{row['id']:row}})\n"
                " manager=Connections(store,FixtureController(store),lambda:None)\n"
                " interactive(lambda ui:main(ui,manager))\nprint('IM_RETURNED')")
        # Platform category -> WhatsApp -> account -> switch -> cancel, then
        # return through account, platform, category and chat entry.
        value = self.session(code, b'\r\x1b[B\r\r\r' + b'\x1b[D'*5, '聊天接入', (30, 100))
        self.assertIn('IM_RETURNED', value)
        self.assertIn('发送成功数', value)
        self.assertIn('固定测试回复', value)
        self.assertIn('已设置', value)
        self.assertNotIn('FAKE_TEST_TOKEN', value)
        self.assertIn('平台接入', value)
        self.assertIn('连接器程序', value)
        self.assertIn('备份与恢复', value)
        self.assertNotIn('刷新', value)

    def test_live_menu_updates_only_changed_rows_and_keeps_focus(self):
        code = ("from maa.menu import MenuView\nfrom maa.ui import value_line\n"
                "calls=0\n"
                "def snapshot():\n global calls\n calls+=1\n"
                " return MenuView('LIVE_MENU',[('a','First'),('b','Second')],(value_line('COUNT',calls),))\n"
                "def work(ui):\n"
                " return ui.choose('LIVE_MENU',[('a','First'),('b','Second')],description=[value_line('COUNT',0)],refresh=snapshot)\n"
                "print('LIVE_RESULT',interactive(work))")
        def drive(fd):
            os.write(fd, b'\x1b[B')
            output = self.receive(fd, 'COUNT：2')
            os.write(fd, b'\r')
            return output
        value = self.session(code, drive, 'LIVE_MENU', (14, 80))
        self.assertIn('LIVE_RESULT b', value)
        self.assertEqual(value.count('LIVE_MENU'), 1)
        rows = self.menu_rows(value)
        self.assertEqual(sum('LIVE_MENU' in row for row in rows), 1, rows)
        self.assertEqual(sum('COUNT：2' in row for row in rows), 1, rows)
        self.assertFalse(any('COUNT：0' in row or 'COUNT：1' in row for row in rows), rows)

    def test_live_selection_tracks_ids_and_refuses_retargeted_confirmation(self):
        for removed in (False, True):
            with self.subTest(removed=removed):
                options = [('a', 'Alpha'), ('b', 'Bravo'), ('c', 'Charlie')]
                replacement = [('c', 'Charlie'), ('a', 'Alpha')] if removed else list(reversed(options))
                code = ("from maa.menu import MenuView\n"
                        f"options={options!r}\nreplacement={replacement!r}\ncalls=0\n"
                        "def snapshot():\n global calls\n calls+=1\n"
                        " return MenuView('IDENTITY_MENU',replacement,(f'TICK {calls}',))\n"
                        "print('IDENTITY_RESULT',interactive(lambda ui:ui.choose('IDENTITY_MENU',options,default='b',refresh=snapshot)))")
                def drive(fd):
                    output = self.receive(fd, 'TICK 1')
                    os.write(fd, b'\r')
                    if removed:
                        output += self.receive(fd, 'TICK 2')
                        os.write(fd, b'\r')
                    return output
                value = self.session(code, drive, 'IDENTITY_MENU', (12, 80))
                self.assertIn('IDENTITY_RESULT ' + ('a' if removed else 'b'), value)
                self.assertEqual(value.count('IDENTITY_MENU'), 1)

    def test_im_live_error_blocks_actions_and_recovers_without_reprinting(self):
        code = ("from maa.im.ui import live\nfrom maa.menu import MenuView\nfrom maa.store import Error\n"
                "class Manager:\n"
                " def __init__(self):self.calls=0\n"
                " def status(self):\n  self.calls+=1\n"
                "  if self.calls==2:raise Error('READ_FAILED')\n"
                "  return {'count':self.calls}\n"
                "manager=Manager()\n"
                "def view(status):return MenuView('ERROR_MENU',[('action','Do action'),(None,'返回')],(f'READY {status[\"count\"]}',))\n"
                "print('ERROR_RESULT',interactive(lambda ui:live(ui,manager,'ERROR_MENU',view))[0])")
        def drive(fd):
            output = self.receive(fd, 'READ_FAILED')
            os.write(fd, b'\r')
            output += self.receive(fd, 'READY 3')
            os.write(fd, b'\r')
            return output
        value = self.session(code, drive, 'ERROR_MENU', (14, 100))
        self.assertIn('ERROR_RESULT action', value)
        self.assertEqual(value.count('ERROR_MENU'), 1)
        self.assertIn('当前状态未知', value)
        rows = self.menu_rows(value)
        self.assertTrue(any('READY 3' in row for row in rows), rows)
        self.assertFalse(any('READ_FAILED' in row for row in rows), rows)

    def test_im_account_live_updates_pause_during_input_and_confirmation(self):
        code = ("import tempfile,threading,time\nfrom pathlib import Path\n"
                "from maa.im.ui import account\nfrom maa.im.state import State\nfrom maa.im.manager import Connections\n"
                "from tests.test_im import FixtureController,record\n"
                "with tempfile.TemporaryDirectory() as folder:\n"
                " store=State(Path(folder)/'im')\n row=record('whatsapp',name='Account')\n"
                " store.save({'version':1,'connections':{row['id']:row}})\n"
                " manager=Connections(store,FixtureController(store),lambda:None)\n"
                " queries=[]\n status=manager.status\n"
                " def observe():\n  queries.append(time.monotonic())\n  return status()\n"
                " manager.status=observe\n"
                " def update():\n  time.sleep(.5)\n  store.put_receive(row,{'received':9,'sent':7})\n"
                " thread=threading.Thread(target=update)\n thread.start()\n"
                " def work(ui):\n"
                "  for method in ('input','confirm'):\n"
                "   original=getattr(ui,method)\n"
                "   def paused(*args,_original=original,**kwargs):\n"
                "    before=len(queries)\n    result=_original(*args,**kwargs)\n"
                "    assert len(queries)==before,'Queries continued inside edit/confirmation'\n    return result\n"
                "   setattr(ui,method,paused)\n"
                "  account(ui,manager,row['id'])\n"
                " interactive(work)\n thread.join()\n"
                " assert manager.row(row['id'])['name']=='Edited'\nprint('EDIT_RETURNED')")
        def drive(fd):
            output = self.receive(fd, '发送成功数：7')
            os.write(fd, b'\x1b[B\r')
            output += self.receive(fd, '请输入新值')
            time.sleep(1.2)
            os.write(fd, b'Edited\r')
            output += self.receive(fd, '本地名称：Edited')
            os.write(fd, b'\x1b[B'*4 + b'\r')
            output += self.receive(fd, '删除 Edited')
            time.sleep(1.2)
            os.write(fd, b'\x1b[D')
            output += self.receive(fd, '固定测试回复')
            os.write(fd, b'\x1b[D')
            return output
        value = self.session(code, drive, '固定测试回复', (30, 100))
        self.assertIn('EDIT_RETURNED', value)
        self.assertNotIn('刷新', value)
        self.assertNotIn('FAKE_TEST_TOKEN', value)

    def test_live_resize_and_no_color_preserve_current_option(self):
        code = ("os.environ['NO_COLOR']='1'\nfrom maa.menu import MenuView\n"
                "from maa.ui import value_line\ncalls=0\n"
                "def snapshot():\n global calls\n calls+=1\n"
                " return MenuView('LIVE_RESIZE',[('a',value_line('状态','已关闭','gray')),('b',value_line('接收计数',calls))])\n"
                "print('RESIZE_RESULT',interactive(lambda ui:ui.choose('LIVE_RESIZE',snapshot().options,default='b',refresh=snapshot)))")
        code = 'import os\n' + code
        def drive(fd):
            fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', 8, 24, 0, 0))
            output = self.receive(fd, '接收计数：2')
            os.write(fd, b'\r')
            return output
        value = self.session(code, drive, 'LIVE_RESIZE', (14, 80))
        self.assertIn('RESIZE_RESULT b', value)
        self.assertNotRegex(value, r'\x1b\[(3\d|9\d)m')
        rows = self.menu_rows(value)
        self.assertEqual(sum('LIVE_RESIZE' in row for row in rows), 1, rows)

    def test_im_program_readonly_status_is_inert_and_updates(self):
        code = ("import tempfile,threading,time\nfrom pathlib import Path\n"
                "from maa.im.ui import program\nfrom maa.im.manager import Connections\nfrom maa.im.state import State\n"
                "from tests.test_im import FixtureController\n"
                "with tempfile.TemporaryDirectory() as folder:\n"
                " store=State(Path(folder)/'im')\n controller=FixtureController(store)\n controller.installed=True\n"
                " controller.active=lambda:controller.autostart\n"
                " def refuse():raise AssertionError('Readonly page invoked a mutation')\n"
                " manager=Connections(store,controller,refuse)\n"
                " def update():\n  time.sleep(.5)\n  controller.autostart=True\n"
                " thread=threading.Thread(target=update)\n thread.start()\n"
                " interactive(lambda ui:program(ui,manager))\n thread.join()\nprint('PROGRAM_RETURNED')")
        def drive(fd):
            os.write(fd, b'\x1b[B\r')
            output = self.receive(fd, '运行状态（只读）：运行中')
            os.write(fd, b'\x1b[D')
            return output
        value = self.session(code, drive, '安装 / 更新连接器程序', (18, 100))
        self.assertIn('PROGRAM_RETURNED', value)
        self.assertNotIn('刷新', value)
        self.assertEqual(value.count('连接器程序\x1b[0m'), 1)
        rows = self.menu_rows(value)
        self.assertEqual(sum('运行状态（只读）：运行中' in row for row in rows), 1, rows)
        self.assertFalse(any('运行状态（只读）：已关闭' in row for row in rows), rows)

    def test_im_account_removed_externally_leaves_only_return(self):
        code = ("import tempfile,threading,time\nfrom pathlib import Path\n"
                "from maa.im.ui import account\nfrom maa.im.manager import Connections\nfrom maa.im.state import State\n"
                "from tests.test_im import FixtureController,record\n"
                "with tempfile.TemporaryDirectory() as folder:\n"
                " store=State(Path(folder)/'im')\n row=record('whatsapp',name='RemovedAccount')\n"
                " store.save({'version':1,'connections':{row['id']:row}})\n"
                " manager=Connections(store,FixtureController(store),lambda:None)\n"
                " def remove():\n  time.sleep(.5)\n  store.save({'version':1,'connections':{}})\n"
                " thread=threading.Thread(target=remove)\n thread.start()\n"
                " interactive(lambda ui:account(ui,manager,row['id']))\n thread.join()\nprint('REMOVED_RETURNED')")
        def drive(fd):
            output = self.receive(fd, '此接入已被其他操作删除')
            os.write(fd, b'\x1b[D')
            return output
        value = self.session(code, drive, '固定测试回复', (30, 100))
        self.assertIn('REMOVED_RETURNED', value)
        rows = self.menu_rows(value)
        self.assertEqual(sum('此接入已被其他操作删除' in row for row in rows), 1, rows)
        self.assertFalse(any('固定测试回复' in row or 'RemovedAccount' in row for row in rows), rows)

    def test_cancel_restores_terminal(self):
        operation = "try:\n print(interactive(lambda ui: ui.input('Cancel model')))\nexcept Cancelled:\n print('CANCELLED')"
        value = self.session(operation, b'\x1b', 'Cancel model', (6, 20))
        self.assertIn('CANCELLED', value)

    def test_wait_refreshes_one_line_and_keeps_native_output(self):
        operation = ("import time\nfrom maa.output import operation, stage, native_output\n"
                     "with operation('加载模型'):\n"
                     " stage('准备')\n time.sleep(1.2)\n"
                     " with native_output() as output:\n  output.write('NATIVE_DOWNLOAD\\n')\n"
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
        self.assertEqual(self.visible_lines(output)[0], 'NATIVE_STDERR')
        self.assertEqual(len(self.visible_lines(output)), 2)
        self.assertNotIn('秒NATIVE_STDERR', output)

    def test_silent_commands_keep_timer_and_leave_only_final_row(self):
        operation = ("import sys\nfrom unittest.mock import patch\n"
                     "from maa.output import operation,stage\nfrom maa.service import privileged\n"
                     "with operation('SILENT_COMMANDS'),patch('maa.service.os.geteuid',return_value=0):\n"
                     " stage('停止原底座')\n"
                     " privileged([sys.executable,'-c','import time;time.sleep(1.2)'])\n"
                     " stage('准备模型配置')\n"
                     " for _ in range(3):\n  privileged([sys.executable,'-c','pass'])\n")
        output = self.session(operation, b'', 'SILENT_COMMANDS', (12, 120))
        self.assertIn('已等待 1.', output.split('准备模型配置', 1)[0])
        rows = self.visible_lines(output)
        self.assertEqual(len(rows), 1, rows)
        self.assertTrue(rows[0].startswith('[成功] SILENT_COMMANDS：准备模型配置'), rows)

    def test_command_failure_preserves_diagnostic_and_final_row(self):
        operation = ("import sys,subprocess\nfrom maa.output import operation,run\n"
                     "try:\n with operation('FAILED_COMMAND'):\n"
                     "  run([sys.executable,'-c',\"import sys;print('NATIVE_FAILURE',file=sys.stderr);sys.exit(7)\"],check=True)\n"
                     "except subprocess.CalledProcessError as exc:\n assert exc.returncode==7\n")
        output = self.session(operation, b'', 'FAILED_COMMAND', (12, 120))
        rows = self.visible_lines(output)
        self.assertEqual(len(rows), 2, rows)
        self.assertEqual(rows[0], 'NATIVE_FAILURE')
        self.assertTrue(rows[1].startswith('[失败] FAILED_COMMAND'), rows)

    def test_native_output_preserves_terminal_and_line_endings(self):
        for ending in ('', '\\n'):
            with self.subTest(ending=ending):
                script = "import sys;assert sys.stdout.isatty() and sys.stderr.isatty();sys.stderr.write('NATIVE_TEXT" + ending + "');sys.stderr.flush()"
                operation = ("import sys\nfrom maa.output import operation,run\n"
                             "with operation('NATIVE_LINES'):\n"
                             f" run([sys.executable,'-c',{script!r}],native=True,check=True)\n")
                output = self.session(operation, b'', 'NATIVE_LINES', (12, 120))
                rows = self.visible_lines(output)
                self.assertEqual(len(rows), 2, rows)
                self.assertEqual(rows[0], 'NATIVE_TEXT')
                self.assertTrue(rows[1].startswith('[成功] NATIVE_LINES'), rows)

    def test_silent_native_command_continues_timer(self):
        operation = ("import sys\nfrom maa.output import operation,run\n"
                     "with operation('SILENT_NATIVE'):\n"
                     " run([sys.executable,'-c','import time;time.sleep(1.2)'],native=True,check=True)\n")
        output = self.session(operation, b'', 'SILENT_NATIVE', (12, 120))
        self.assertIn('已等待 1.', output)
        self.assertEqual(len(self.visible_lines(output)), 1)

    def test_native_live_utf8_and_progress_are_forwarded(self):
        script = ("import os,sys,time;data='原生下载'.encode();os.write(2,data[:2]);time.sleep(.1);"
                  "os.write(2,data[2:]);sys.stderr.write(' 1%\\r原生下载 100%\\n\\x1b[?2');sys.stderr.flush();"
                  "time.sleep(.1);sys.stderr.write('5h');sys.stderr.flush()")
        operation = ("import sys\nfrom maa.output import operation,run\n"
                     "with operation('NATIVE_UTF8'):\n"
                     f" run([sys.executable,'-c',{script!r}],native=True,check=True)\n")
        output = self.session(operation, b'', 'NATIVE_UTF8', (12, 120))
        self.assertNotIn('\ufffd', output)
        self.assertIn('原生下载 1%', output)
        rows = self.visible_lines(output)
        self.assertEqual(len(rows), 2, rows)
        self.assertEqual(rows[0], '原生下载 100%')

    def test_native_interrupt_restores_output_and_cursor(self):
        operation = ("import sys\nfrom maa.output import operation,run\n"
                     "try:\n with operation('NATIVE_INTERRUPT'):\n"
                     "  run([sys.executable,'-c',\"import time;print('NATIVE_READY',flush=True);time.sleep(60)\"],native=True,check=True)\n"
                     "except KeyboardInterrupt:\n print('INTERRUPTED')\n")
        output = self.session(operation, b'\x03', 'NATIVE_READY', (12, 120))
        self.assertIn('[中断] NATIVE_INTERRUPT', output)
        self.assertIn('INTERRUPTED', output)

    def test_command_progress_returns_to_menu_without_old_rows(self):
        operation = ("import sys\nfrom maa.output import operation,run\n"
                     "def work(ui):\n ui.choose('BEFORE_COMMAND', [('go','执行')])\n"
                     " with operation('MENU_COMMAND'):\n"
                     "  for _ in range(3):\n   run([sys.executable,'-c','pass'],check=True)\n"
                     " ui.choose('AFTER_COMMAND',[('back','返回')])\n"
                     "interactive(work)\n")
        output = self.session(operation, b'\r\r', 'BEFORE_COMMAND', (16, 120))
        self.assertIn('AFTER_COMMAND', output)
        command_area = output.split('[进行中] MENU_COMMAND', 1)[1].split('AFTER_COMMAND', 1)[0]
        rows = self.visible_lines(command_area)
        self.assertFalse(any('[进行中]' in row for row in rows), rows)

    def test_unavailable_mtp_activation_is_inert(self):
        operation = ("from maa.ui import edit_settings\nfrom maa.settings import settings\n"
                     "try:\n interactive(lambda ui: edit_settings(ui,{'mtp_supported':False},settings(),title='UNAVAILABLE_MTP'))\n"
                     "except Cancelled:\n print('MTP_CANCELLED')")
        output = self.session(operation, b'\x1b[B'*6+b'\r\x1b[C\x1b', 'UNAVAILABLE_MTP', (24, 120))
        self.assertEqual(output.count('UNAVAILABLE_MTP'), 1)
        self.assertIn('MTP_CANCELLED', output)


if __name__ == '__main__':
    unittest.main()
