"""Compare current discovery with the immutable 0.1.9 and 0.1.10 inventories."""
import argparse
import ast
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('maa_coverage_inventory', ROOT / 'test/coverage.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


def discovered(paths):
    result = set()
    for path in paths:
        for cls in ast.parse(path.read_text()).body:
            if not isinstance(cls, ast.ClassDef):
                continue
            result.update(str(path.relative_to(ROOT)) + ':' + cls.name + '.' + node.name
                          for node in cls.body if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'))
    return result


def compare():
    result = {'baseline': 'stable/0.1.9', 'previous': 'v0.1.10', 'status': 'passed'}
    for name, paths, baseline, previous in (
        ('portable', (ROOT / 'tests').glob('test_*.py'), inventory.PORTABLE_BASELINE, inventory.PORTABLE_0_1_10),
        ('delivery', [ROOT / 'scripts/test_bootstrap.py'], inventory.DELIVERY_BASELINE, inventory.DELIVERY_0_1_10),
    ):
        actual = discovered(paths)
        missing = sorted(set(baseline + previous) - actual)
        assert not missing, (name, missing)
        result[name] = {'baseline_count': len(baseline), 'previous_count': len(previous),
                        'current_count': len(actual), 'missing': missing,
                        'mapping': [{'baseline': item, 'current': item} for item in baseline],
                        'added': sorted(actual - set(baseline))}
    receipt = json.loads((ROOT / 'validation/STABLE_0_1_9_NATIVE.json').read_text())
    original = [row['name'] for row in receipt['checks']]
    assert set(original) == set(inventory.NATIVE_BASELINE), 'Frozen native inventory differs from original executed checks'
    result['native'] = {'baseline_count': len(original), 'current_required_count': len(original) + len(inventory.INSTALLED_ADDITIONS) + 1,
                        'missing': [], 'mapping': [
                            {'baseline': name, 'current': name,
                             'permission_verification': 'native config/read in private CODEX_HOME' if name in (
                                'explicit-yolo-test-baseline', 'yolo-off', 'yolo-on',
                                'product-reinstall-retains-yolo-off-and-native-instance') else None}
                            for name in original],
                        'added': inventory.INSTALLED_ADDITIONS + ['user-permissions-retained'],
                        'execution_evidence': 'V0_1_15_LOCAL.json and V0_1_15_PUBLIC.json; inventory alone is not execution evidence'}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output')
    args = parser.parse_args()
    text = json.dumps(compare(), ensure_ascii=False, indent=2) + '\n'
    if args.output:
        Path(args.output).write_text(text)
    else:
        print(text, end='')
