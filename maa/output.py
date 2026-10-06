"""Minimal output contract reused by the mas-derived inline Screen."""
from contextvars import ContextVar
import os
import shutil
import sys
boundary = ContextVar('maa_output_boundary', default=None)


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
