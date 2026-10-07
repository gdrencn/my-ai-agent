"""Minimal output contract reused by the mas-derived inline Screen."""
from contextvars import ContextVar
from contextlib import contextmanager
import codecs
import os
import shutil
import subprocess
import sys
import threading
import time
boundary = ContextVar('maa_output_boundary', default=None)
activity = ContextVar('maa_activity', default=None)


def terminal_size(stream):
    try:
        return os.get_terminal_size(stream.fileno())
    except (AttributeError, OSError, ValueError):
        return shutil.get_terminal_size()


def colored(text, tone, *, enabled=True, foreground_only=False):
    codes = {'green': 32, 'yellow': 33, 'red': 31, 'cyan': 36, 'gray': 90}
    return f'\033[{codes[tone]}m{text}\033[{39 if foreground_only else 0}m' if enabled and tone in codes else text


def say(value):
    callback = boundary.get()
    if callback:
        callback()
    print(value, flush=True)


class Progress:
    """One elapsed-time line on stderr; stdout remains usable for JSON."""
    def __init__(self, label, stream=None):
        self.label, self.phase = label, ''
        self.stream = stream if stream is not None else sys.stderr
        self.tty = self.stream.isatty()
        self.started = time.monotonic()
        self.mutex = threading.RLock()
        self.stopped = threading.Event()
        self.suspended = 0
        self.visible = False

    def render(self, outcome='进行中'):
        from .text import clipped
        with self.mutex:
            if self.suspended:
                return
            elapsed = f' — {"已等待" if outcome == "进行中" else "耗时"} {time.monotonic() - self.started:.1f} 秒'
            detail = self.label + ('：' + self.phase if self.phase else '')
            line = f'[{outcome}] {detail}'
            if self.tty:
                width = max(1, terminal_size(self.stream).columns - 1)
                from .text import cells
                if cells(elapsed) >= width:
                    line = clipped(elapsed.strip(' —'), width)
                else:
                    line = clipped(line, width - cells(elapsed)) + elapsed
                self.stream.write('\r\033[2K' + line)
                self.visible = True
            else:
                self.stream.write(line + elapsed + '\n')
            self.stream.flush()

    def tick(self):
        while not self.stopped.wait(1):
            self.render()

    def stage(self, phase):
        with self.mutex:
            self.phase = phase
            if self.tty:
                self.render()

    def __enter__(self):
        callback = boundary.get()
        if callback:
            callback()
        if self.tty:
            self.stream.write('\033[?25l')
        self.render()
        self.thread = threading.Thread(target=self.tick, daemon=True) if self.tty else None
        if self.thread:
            self.thread.start()
        return self

    def __exit__(self, kind, value, traceback):
        self.stopped.set()
        if self.thread:
            self.thread.join()
        self.render('成功' if kind is None else '中断' if issubclass(kind, (KeyboardInterrupt, SystemExit)) else '失败')
        if self.tty:
            self.stream.write('\n\033[?25h')
            self.stream.flush()

    @contextmanager
    def external(self):
        """Yield a writer which takes the terminal only when output exists."""
        writer = ExternalOutput(self.stream, self)
        try:
            yield writer
        finally:
            writer.close()


class ExternalOutput:
    """Preserve actual diagnostics without committing a temporary progress row."""
    def __init__(self, stream, progress=None):
        self.stream, self.progress = stream, progress
        self.written, self.ends_line = False, True
        self.escape = ''

    def write(self, value):
        if not value:
            return
        progress = self.progress
        from contextlib import nullcontext
        with progress.mutex if progress else nullcontext():
            if not self.written and progress:
                progress.suspended += 1
                if progress.visible:
                    self.stream.write('\r\033[2K')
                    progress.visible = False
            self.written = True
            self.stream.write(value)
            self.stream.flush()
            for char in value:
                if self.escape:
                    self.escape += char
                    if self.escape.startswith('\x1b['):
                        if len(self.escape) > 2 and '@' <= char <= '~':
                            self.escape = ''
                    elif len(self.escape) > 1:
                        self.escape = ''
                elif char == '\x1b':
                    self.escape = char
                else:
                    self.ends_line = char == '\n'

    def close(self):
        progress = self.progress
        from contextlib import nullcontext
        with progress.mutex if progress else nullcontext():
            if not self.written:
                return
            if not self.ends_line:
                self.stream.write('\n')
                self.stream.flush()
            self.written = False
            if progress:
                progress.suspended -= 1
                if progress.tty:
                    progress.render()


@contextmanager
def operation(label):
    current = activity.get()
    if current is not None:
        current.stage(label)
        yield current
        return
    with Progress(label) as progress:
        token = activity.set(progress)
        try:
            yield progress
        finally:
            activity.reset(token)


def stage(phase):
    current = activity.get()
    if current:
        current.stage(phase)


@contextmanager
def native_output():
    current = activity.get()
    if current:
        with current.external() as writer:
            yield writer
    else:
        writer = ExternalOutput(sys.stderr)
        try:
            yield writer
        finally:
            writer.close()


def diagnostic(value):
    with native_output() as writer:
        writer.write(value)


def run(command, *, native=False, **kwargs):
    """Run a command with one output policy, shared by all management entries.

    Normal commands keep the elapsed timer alive and replay actual output after
    completion. Explicitly captured/redirected streams retain subprocess.run's
    contract. Native installers/downloaders forward live output through a PTY
    on terminals so their own progress behavior remains available.
    """
    if kwargs.get('capture_output'):
        return subprocess.run(command, **kwargs)
    inherited = [name for name in ('stdout', 'stderr') if kwargs.get(name) is None]
    if not inherited:
        return subprocess.run(command, **kwargs)
    if native:
        if len(inherited) != 2:
            raise ValueError('Native output requires inherited stdout and stderr')
        for name in inherited:
            kwargs.pop(name, None)
        return _run_native(command, kwargs)
    check = kwargs.pop('check', False)
    for name in inherited:
        kwargs[name] = subprocess.PIPE
    try:
        result = subprocess.run(command, check=False, **kwargs)
    except subprocess.TimeoutExpired as exc:
        _replay(exc, inherited)
        raise
    _replay(result, inherited)
    if check:
        result.check_returncode()
    for name in inherited:
        setattr(result, name, None)
    return result


def _replay(result, streams):
    with native_output() as writer:
        for name in streams:
            value = getattr(result, name, None)
            writer.write(value.decode(errors='replace') if isinstance(value, bytes) else value)


def _run_native(command, kwargs):
    import select
    stream = activity.get().stream if activity.get() else sys.stderr
    if stream.isatty():
        import fcntl
        import pty
        import struct
        import termios
        source, destination = pty.openpty()
        size = terminal_size(stream)
        fcntl.ioctl(destination, termios.TIOCSWINSZ, struct.pack('HHHH', size.lines, size.columns, 0, 0))
    else:
        source, destination = os.pipe()
    errors = []
    finished = threading.Event()
    with native_output() as writer:
        def forward():
            decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
            try:
                while True:
                    if not select.select([source], [], [], .1)[0]:
                        if finished.is_set():
                            break
                        continue
                    try:
                        value = os.read(source, 65536)
                    except OSError as exc:
                        import errno
                        if exc.errno == errno.EIO:  # PTY writer closed.
                            break
                        raise
                    if not value:
                        break
                    writer.write(decoder.decode(value))
                writer.write(decoder.decode(b'', final=True))
            except BaseException as exc:
                errors.append(exc)
            finally:
                os.close(source)
        reader = threading.Thread(target=forward, daemon=True)
        reader.start()
        try:
            result = subprocess.run(command, stdout=destination, stderr=destination, **kwargs)
        finally:
            os.close(destination)
            finished.set()
            reader.join()
        if errors:
            raise errors[0]
        return result
