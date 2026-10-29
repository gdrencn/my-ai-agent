"""Real child writers verify ownership, result preservation and bounded teardown."""
import json
import errno
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from maa import agent_status, processes


ACTOR = r'''
import json,os,signal,sys,time
from pathlib import Path
folder,trace,mode=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
child=os.fork()
if child==0:
    os.setpgid(0,0)
    signal.signal(signal.SIGTERM,signal.SIG_IGN)
    fd=os.open(os.devnull,os.O_RDWR)
    for stream in (0,1,2):os.dup2(fd,stream)
    target=folder/'codex/.tmp/plugins-clone-fixture/plugins/example/skills/skill'
    target.mkdir(parents=True,exist_ok=True)
    (target/'writer').write_text(str(time.monotonic()))
    pending=trace.with_suffix('.pending')
    pending.write_text(json.dumps({'pid':os.getpid(),'sid':os.getsid(0),'group':os.getpgrp()}))
    pending.replace(trace)
    while True:
        target=folder/'codex/.tmp/plugins-clone-fixture/plugins/example/skills/skill'
        target.mkdir(parents=True,exist_ok=True)
        (target/'writer').write_text(str(time.monotonic()))
        time.sleep(.002)
while not trace.exists():time.sleep(.005)
print('main output',flush=True)
print('main diagnostic',file=sys.stderr,flush=True)
if mode=='query':
    for line in sys.stdin:
        row=json.loads(line)
        if row['method']=='initialize':print(json.dumps({'id':1,'result':{}}),flush=True)
        if row['method']=='config/read':print(json.dumps({'id':2,'result':{'config':{'approval_policy':'never','sandbox_mode':'danger-full-access'}}}),flush=True)
elif mode=='pty':
    import termios,tty
    original=termios.tcgetattr(0)
    tty.setraw(0)
    print('To get started',flush=True)
    typed=b''
    while True:
        char=os.read(0,1)
        if char==b'\x03':
            termios.tcsetattr(0,termios.TCSANOW,original)
            break
        typed+=char
        if b'/model\r' in typed:
            print('Select model\nfixture-model',flush=True)
            typed=b''
elif mode=='wait':time.sleep(60)
else:sys.exit(int(mode))
'''


def alive(pid):
    try:
        return (Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()[0] != 'Z'
    except FileNotFoundError:
        return False


def ready(path):
    deadline=time.monotonic()+5
    while not path.exists():
        if time.monotonic()>deadline:raise AssertionError('Child writer did not start')
        time.sleep(.01)
    return json.loads(path.read_text())


class Processes(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.trace=self.root/'writer.json'
        self.folder=self.root/'private'
        self.actor=self.root/'actor.py';self.actor.write_text(ACTOR)
    def tearDown(self):
        if self.trace.exists():
            row=json.loads(self.trace.read_text())
            for pid in (row['pid'],row['sid']):
                if alive(pid):os.kill(pid,signal.SIGKILL)
        self.temp.cleanup()
    def command(self,mode):
        return [sys.executable,str(self.actor),str(self.folder),str(self.trace),mode]
    def assert_stopped(self):
        row=ready(self.trace)
        self.assertFalse(alive(row['pid']))
        self.assertNotEqual(row['sid'],row['group'])
        import shutil
        shutil.rmtree(self.folder,ignore_errors=False)
        time.sleep(.03)
        self.assertFalse(self.folder.exists(),'A child recreated the deleted Codex home')

    def test_success_and_nonzero_exit_stop_surviving_writer_and_keep_outputs(self):
        for status in (0,7):
            with self.subTest(status=status):
                self.trace.unlink(missing_ok=True)
                result=processes.run(self.command(str(status)),capture_output=True,text=True,timeout=5)
                self.assertEqual(result.returncode,status)
                self.assertEqual(result.stdout,'main output\n')
                self.assertEqual(result.stderr,'main diagnostic\n')
                self.assert_stopped()

    def test_timeout_preserves_partial_output_and_stops_children(self):
        with self.assertRaises(subprocess.TimeoutExpired) as raised:
            processes.run(self.command('wait'),capture_output=True,timeout=.3)
        self.assertIn(b'main output',raised.exception.output)
        self.assert_stopped()

    def test_checked_failure_preserves_exception_output_and_stops_children(self):
        with self.assertRaises(subprocess.CalledProcessError) as raised:
            processes.run(self.command('17'),capture_output=True,text=True,check=True,timeout=5)
        self.assertEqual(raised.exception.returncode,17)
        self.assertEqual(raised.exception.stdout,'main output\n')
        self.assertEqual(raised.exception.stderr,'main diagnostic\n')
        self.assert_stopped()

    def test_interruption_stops_its_writer_and_preserves_unrelated_session(self):
        unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)
        try:
            with self.assertRaises(KeyboardInterrupt):
                with processes.owned(self.command('wait'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL):
                    ready(self.trace)
                    raise KeyboardInterrupt
            self.assert_stopped()
            self.assertIsNone(unrelated.poll())
        finally:
            unrelated.terminate();unrelated.wait(timeout=5)

    def test_unavailable_pidfd_uses_verified_owned_processes(self):
        with patch.object(processes.os,'pidfd_open',side_effect=OSError(errno.ENOSYS,'Not available'),create=True):
            result=processes.run(self.command('0'),capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0)
        self.assert_stopped()

    def test_configuration_query_cleans_plugin_like_child_before_returning(self):
        # Protocol stdout is JSON only; the actor's diagnostics stay private.
        source=ACTOR.replace("print('main output',flush=True)","pass")
        self.actor.write_text('#!'+sys.executable+'\n'+source.replace(
            "folder,trace,mode=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]",
            'folder=Path('+repr(str(self.folder))+');trace=Path('+repr(str(self.trace))+');mode="query"'))
        self.actor.chmod(0o755)
        with patch.object(agent_status,'binary',return_value=str(self.actor)):
            result=agent_status.configuration(timeout=5)
        self.assertEqual(result,{'approval_policy':'never','sandbox_mode':'danger-full-access'})
        self.assert_stopped()

    def test_sigint_during_communicate_preserves_130_and_cleans_writer(self):
        source_root=str(Path(processes.__file__).parent.parent)
        code='import sys\nsys.path.insert(0,'+repr(source_root)+')\nfrom maa.processes import run\n'
        code+='try:run('+repr(self.command('wait'))+',capture_output=True,timeout=60)\n'
        code+='except KeyboardInterrupt:raise SystemExit(130)\n'
        driver=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        try:
            ready(self.trace)
            driver.send_signal(signal.SIGINT)
            stdout,stderr=driver.communicate(timeout=10)
            self.assertEqual(driver.returncode,130,(stdout,stderr))
            self.assert_stopped()
        finally:
            if driver.poll() is None:driver.kill()
            driver.communicate(timeout=5)

    def picker_actor(self,mode):
        self.folder.mkdir()
        source=ACTOR.replace('folder,trace,mode=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]',
                            'folder=Path('+repr(str(self.folder))+');trace=Path('+repr(str(self.trace))+');mode='+repr(mode))
        self.actor.write_text('#!'+sys.executable+'\n'+source)
        self.actor.chmod(0o755)
        try:
            from maa_testing.codex_ui import picker
        except ImportError:
            from test.codex_ui import picker
        return picker

    def test_real_pty_picker_stops_writer_after_normal_terminal_restoration(self):
        picker=self.picker_actor('pty')
        result=picker(str(self.actor),'fixture-model',cwd=self.folder)
        self.assertTrue(result['local_only'])
        self.assert_stopped()

    def test_real_pty_picker_stops_writer_when_main_exits_before_picker(self):
        picker=self.picker_actor('0')
        with self.assertRaises(AssertionError):picker(str(self.actor),'fixture-model',cwd=self.folder)
        self.assert_stopped()
