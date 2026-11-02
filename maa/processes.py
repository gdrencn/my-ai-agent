"""Bounded cleanup of a command's own Linux session, including surviving children.

Commands get a new session. PTY callers supply the session created by pty.fork.
Interactive management commands use an owned group in the existing session so
sudo retains its controlling terminal; foreground ownership is scoped to them.
No executable names, user identities, file paths or unrelated sessions are used
to choose signal targets. A changed child process group stays in its session.
"""
from contextlib import contextmanager, ExitStack
import errno
import os
from pathlib import Path
import signal
import subprocess
import sys
import termios
import time


def _record(pid):
    try:
        fields = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
        return (pid, fields[0], int(fields[2]), int(fields[3]), int(fields[19]))
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None


class Session:
    """Ownership token for a child session or group, retained after exit."""
    def __init__(self, pid, *, process_group=False):
        self.pid = pid
        self.process_group = process_group
        deadline = time.monotonic() + 1
        while True:
            row = _record(pid)
            if row and row[2 if process_group else 3] == pid:
                self.started = row[4]
                self.session = row[3]
                return
            if row is None or row[1] == 'Z' or time.monotonic() >= deadline:
                raise RuntimeError('Child did not establish its owned process scope')
            time.sleep(.01)  # forkpty's child may still be establishing the session.

    def members(self):
        leader = _record(self.pid)
        if leader and leader[4] != self.started:
            raise RuntimeError('Owned session leader identity changed')
        rows = []
        for path in Path('/proc').iterdir():
            if path.name.isdecimal():
                row = _record(int(path.name))
                if (row and row[3] == self.session and (not self.process_group or row[2] == self.pid)
                        and row[4] >= self.started and row[1] not in ('Z', 'X')):
                    rows.append(row)
        return rows

    @staticmethod
    def _signal(row, signum):
        descriptor = None
        try:
            if hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'):
                try:
                    descriptor = os.pidfd_open(row[0])
                except OSError as exc:
                    if exc.errno not in (errno.ENOSYS, errno.EINVAL, errno.EPERM, errno.EACCES):
                        raise
            current = _record(row[0])
            if not current or (current[3], current[4]) != (row[3], row[4]):
                return
            if descriptor is not None:
                try:
                    signal.pidfd_send_signal(descriptor, signum)
                    return
                except OSError as exc:
                    if exc.errno not in (errno.ENOSYS, errno.EPERM, errno.EACCES):
                        raise
            current = _record(row[0])
            if current and (current[3], current[4]) == (row[3], row[4]):
                os.kill(row[0], signum)
        except ProcessLookupError:
            pass
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def stop(self, grace=1, kill_wait=1):
        for signum, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, kill_wait)):
            deadline, sent = time.monotonic() + wait, set()
            while True:
                rows = self.members()
                if not rows:
                    return
                for row in rows:
                    token = (row[0], row[4])
                    if token not in sent:
                        self._signal(row, signum)
                        sent.add(token)
                if time.monotonic() >= deadline:
                    break
                time.sleep(.02)
        if self.members():
            raise RuntimeError('Owned child processes did not stop before cleanup')


def _foreground(fd, group):
    # The parent may currently be in the background while taking its terminal
    # back. Block SIGTTOU only around the ioctl, never for the managed command.
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTTOU})
    try:
        os.tcsetpgrp(fd, group)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


@contextmanager
def foreground():
    try:
        terminal = os.open('/dev/tty', os.O_RDWR | os.O_NOCTTY)
    except OSError as exc:
        if exc.errno not in (errno.ENXIO, errno.ENODEV, errno.ENOENT):
            raise
        yield lambda group: None
        return
    previous = None
    attributes = None
    try:
        if os.tcgetpgrp(terminal) == os.getpgrp():
            previous = os.getpgrp()
        attributes = termios.tcgetattr(terminal) if previous is not None else None
        def handoff(group):
            if previous is None:
                return
            try:
                _foreground(terminal, group)
                os.killpg(group, signal.SIGCONT)  # A fast tty reader may have stopped before the handoff.
            except ProcessLookupError:
                pass
        yield handoff
    finally:
        original = sys.exc_info()[1]
        try:
            try:
                if previous is not None:
                    _foreground(terminal, previous)
                    if attributes is not None:
                        termios.tcsetattr(terminal, termios.TCSANOW, attributes)
            finally:
                os.close(terminal)
        except BaseException as cleanup:
            if original is None:
                raise
            original.add_note('Terminal restoration failed: ' + str(cleanup))


@contextmanager
def owned(command, *, preserve_terminal=False, **kwargs):
    """Stop only this invocation's processes before returning to its caller."""
    if not kwargs.pop('start_new_session', True):
        raise ValueError('Owned commands require a new session')
    if 'process_group' in kwargs:
        raise ValueError('Owned commands choose their own process group')
    with ExitStack() as stack:
        # Snapshot terminal modes before spawning: a fast sudo may change echo
        # before the parent next runs. Restore only after owned children stop.
        handoff = stack.enter_context(foreground()) if preserve_terminal else None
        process = subprocess.Popen(command, **({'process_group': 0} if preserve_terminal else {'start_new_session': True}), **kwargs)
        scope = None
        def finish():
            try:
                if scope is not None:
                    scope.stop()
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=2)
                for pipe in (process.stdin, process.stdout, process.stderr):
                    if pipe is not None:
                        pipe.close()
        try:
            scope = Session(process.pid, process_group=preserve_terminal)
            if handoff:
                handoff(process.pid)
            yield process
        except BaseException as original:
            try:
                finish()
            except BaseException as cleanup:
                original.add_note('Owned process cleanup failed: ' + str(cleanup))
            raise
        else:
            finish()


def run(command, *, input=None, capture_output=False, timeout=None, check=False, **kwargs):
    """subprocess.run results with owned-process cleanup on every exit path."""
    if capture_output:
        if 'stdout' in kwargs or 'stderr' in kwargs:
            raise ValueError('capture_output cannot be combined with explicit streams')
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if input is not None:
        if 'stdin' in kwargs:
            raise ValueError('input cannot be combined with stdin')
        kwargs['stdin'] = subprocess.PIPE
    with owned(command, **kwargs) as process:
        stdout, stderr = process.communicate(input, timeout=timeout)
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result
