"""Minimal output contract reused by the mas-derived inline Screen."""
from contextvars import ContextVar
from contextlib import contextmanager
import os
import shutil
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
    codes = {'green': 32, 'yellow': 33, 'red': 31}
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
        """Give native installers/downloaders exclusive terminal output."""
        with self.mutex:
            if not self.suspended and self.tty:
                self.stream.write('\n')
                self.stream.flush()
            self.suspended += 1
        try:
            yield
        finally:
            with self.mutex:
                self.suspended -= 1
                if not self.suspended and self.tty:
                    # Native progress may finish without a newline.
                    self.stream.write('\n')
                    self.render()


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
        with current.external():
            yield
    else:
        yield
