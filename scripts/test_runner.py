"""Packaged tests run outside the source checkout, paired with a product."""
import argparse
import importlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from maa import __version__


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--unit', action='store_true')
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--product')
    args = parser.parse_args()
    if args.product:
        result = subprocess.check_output([sys.executable, args.product, '--version'], text=True).strip()
        if result != __version__:
            raise ValueError('Tester/product version mismatch')
    modules = [importlib.import_module('tests.' + name) for name in ('test_core', 'test_service', 'test_status', 'test_terminal')]
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(module) for module in modules)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful() or result.skipped:
        return 1
    if args.native:
        from maa_testing.native import run as native
        native()
    return 0


if __name__ == '__main__':
    raise SystemExit(run())
