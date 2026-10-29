"""Shared human catalogs; raw native diagnostics and machine data stay intact."""
import argparse
from functools import lru_cache
from importlib import import_module
import sys
import threading
from . import preferences
from .store import Error

@lru_cache(maxsize=2)
def catalog(locale):
    return import_module('.locales.' + locale, __package__)

def error_text(value, *, locale=None):
    if isinstance(value, Error):
        return text(value.template, locale=locale,
                    **{key: error_text(item, locale=locale) if isinstance(item, Error) else item for key, item in value.values.items()})
    return str(value)

def t(key, *, locale=None, **values):
    locale = locale or preferences.language()
    return catalog(locale).MESSAGES[key].format(**{key: error_text(value, locale=locale) if isinstance(value, Error) else value for key, value in values.items()})

def text(source, *, locale=None, **values):
    locale = locale or preferences.language()
    template = catalog(locale).TEXT.get(source, source)
    return template.format(**values) if values else template

class Subparsers(argparse._SubParsersAction):
    def add_parser(self, name, **kwargs):
        if kwargs.get('help'):
            kwargs['help'] = text(kwargs['help'])
        return super().add_parser(name, **kwargs)


parser_lock = threading.RLock()


class Parser(argparse.ArgumentParser):
    """Translate parser presentation without changing commands or parsed values."""
    def __init__(self, *args, **kwargs):
        if kwargs.get('description'):
            kwargs['description'] = text(kwargs['description'])
        super().__init__(*args, **kwargs)
        self._positionals.title = text('positional arguments')
        self._optionals.title = text('options')
        self.register('action', 'parsers', Subparsers)
        for action in self._actions:
            if action.help:
                action.help = text(action.help)

    def add_argument(self, *args, **kwargs):
        if kwargs.get('help'):
            kwargs['help'] = text(kwargs['help'])
        return super().add_argument(*args, **kwargs)

    def add_subparsers(self, **kwargs):
        kwargs.setdefault('parser_class', Parser)
        return super().add_subparsers(**kwargs)

    def parse_known_args(self, *args, **kwargs):
        # argparse calls gettext while parsing dynamic validation messages. Scope
        # that hook to parsing, including recursive subparsers, then restore it.
        with parser_lock:
            original = argparse._
            argparse._ = text
            try:
                return super().parse_known_args(*args, **kwargs)
            finally:
                argparse._ = original

    def format_usage(self):
        return super().format_usage().replace('usage: ', text('usage: '), 1)

    def format_help(self):
        return super().format_help().replace('usage: ', text('usage: '), 1)

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, text('{v0}: error: {v1}\n', v0=self.prog, v1=message))
