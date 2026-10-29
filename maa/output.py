"""Minimal output contract reused by the inline Screen."""
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
    def __init__(self, label, stream=None, **values):
        from .i18n import text
        from .preferences import language
        self.locale = language()
        label = text(label, locale=self.locale, **values)
        self.label, self.phase = label, ''
        self.stream = stream if stream is not None else sys.stderr
        self.tty = self.stream.isatty()
        self.started = time.monotonic()
        self.mutex = threading.RLock()
        self.stopped = threading.Event()
        self.suspended = 0
        self.visible = False

    def render(self, outcome='in_progress'):
        from .text import clipped
        from .i18n import t
        with self.mutex:
            if self.suspended:
                return
            elapsed = t('progress_wait' if outcome == 'in_progress' else 'progress_elapsed', locale=self.locale, elapsed=time.monotonic() - self.started)
            detail = self.label + (t('separator', locale=self.locale) + self.phase if self.phase else '')
            line = f'[{t("progress_" + outcome, locale=self.locale)}] {detail}'
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

    def stage(self, phase, **values):
        from .i18n import text
        with self.mutex:
            self.phase = text(phase, locale=self.locale, **values)
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
        self.render('success' if kind is None else 'interrupted' if issubclass(kind, (KeyboardInterrupt, SystemExit)) else 'failed')
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
def operation(label, **values):
    current = activity.get()
    if current is not None:
        current.stage(label, **values)
        yield current
        return
    with Progress(label, **values) as progress:
        token = activity.set(progress)
        try:
            yield progress
        finally:
            activity.reset(token)


def stage(phase, **values):
    current = activity.get()
    if current:
        current.stage(phase, **values)


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


def run(command, *, native=False, tee_stderr=False, **kwargs):
    """Run a command with one output policy, shared by all management entries.

    Normal commands keep the elapsed timer alive and replay actual output after
    completion. Explicitly captured/redirected streams retain subprocess.run's
    contract. Native installers/downloaders forward live output through a PTY
    on terminals so their own progress behavior remains available.
    """
    if tee_stderr and (not native or kwargs.get('capture_output') or kwargs.get('stderr') is not None):
        raise ValueError('Live stderr capture requires native mode and inherited stderr')
    if kwargs.get('capture_output'):
        return subprocess.run(command, **kwargs)
    inherited = [name for name in ('stdout', 'stderr') if kwargs.get(name) is None]
    if not inherited:
        return subprocess.run(command, **kwargs)
    if native:
        if tee_stderr and inherited != ['stderr']:
            raise ValueError('Live stderr capture requires independently redirected stdout')
        for name in inherited:
            kwargs.pop(name, None)
        return _run_native(command, kwargs, inherited, tee_stderr)
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


def _run_native(command, kwargs, inherited=('stdout', 'stderr'), tee_stderr=False):
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
    captured = []
    check = kwargs.pop('check', False)
    def stderr_value():
        data = b''.join(captured)
        if kwargs.get('text') or kwargs.get('universal_newlines') or kwargs.get('encoding') or kwargs.get('errors'):
            import locale
            encoding = kwargs.get('encoding') or ('utf-8' if sys.flags.utf8_mode else locale.getencoding())
            return data.decode(encoding, kwargs.get('errors') or 'strict').replace('\r\n', '\n').replace('\r', '\n')
        return data
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
                    if tee_stderr:
                        captured.append(value)
                    writer.write(decoder.decode(value))
                writer.write(decoder.decode(b'', final=True))
            except BaseException as exc:
                errors.append(exc)
            finally:
                os.close(source)
        reader = threading.Thread(target=forward, daemon=True)
        reader.start()
        try:
            try:
                result = subprocess.run(command, check=False, **{**kwargs, **{name: destination for name in inherited}})
            finally:
                os.close(destination)
                finished.set()
                reader.join()
        except subprocess.TimeoutExpired as exc:
            if tee_stderr:
                exc.stderr = stderr_value()
            raise
        if errors:
            raise errors[0]
        if tee_stderr:
            result.stderr = stderr_value()
        if check:
            result.check_returncode()
        return result
