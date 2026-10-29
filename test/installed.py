"""Read-only installed checks, independent of virtualization and Agent tool execution."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def run(product=None, report=None, write_report=True):
    from maa import __version__, codex, preferences
    from maa.agent_status import configuration
    from maa.environment import require_systemd, missing_dependencies
    from maa.manager import Manager
    root = Path.home() / '.local/share/my-ai-agent'
    archive = root / 'maa.pyz'
    if report is None:
        report = {'version': __version__, 'kind': 'read-only installed configuration checks',
                  'checks': [], 'status': 'failed'}
    result_path = Path.home() / ('maa-native-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.json')
    manager = Manager()
    paths = [manager.store.path(name) for name in ('selected.json', 'target.json', 'runtime.json', 'models.json')]
    paths += [codex.home() / name for name in ('config.toml', 'maa-yolo-recovery.json', 'maa-local.config.toml')]
    paths.append(preferences.path())
    paths += list(manager.store.path('configs').glob('*.json'))
    before = {p: p.read_bytes() if p.exists() else None for p in paths}
    def check(name, function):
        try:
            value = function()
        except Exception as exc:
            report['checks'].append({'name': name, 'status': 'failed', 'error': str(exc)})
            raise
        report['checks'].append({'name': name, 'status': 'passed', 'detail': value})
        print('✓ ' + name, flush=True)
        return value
    try:
        def version():
            if product and hashlib.sha256(archive.read_bytes()).digest() != hashlib.sha256(Path(product).read_bytes()).digest():
                raise AssertionError('Installed product differs from the paired product')
            value = subprocess.check_output([sys.executable, str(archive), '--version'], text=True).strip()
            if value != __version__: raise AssertionError('Installed/product version mismatch')
            entry_value = subprocess.check_output([str(Path.home() / '.local/bin/maa'), '--version'], text=True).strip()
            if entry_value != value: raise AssertionError('Installed command version mismatch')
            return value
        check('installed-version', version)
        def prerequisites():
            require_systemd()
            missing = missing_dependencies()
            if missing: raise AssertionError('Missing dependencies: ' + ', '.join(missing))
            return {'systemd': 'available', 'dependencies': 'available'}
        check('linux-prerequisites', prerequisites)
        state = check('current-model-state', lambda: manager.model_status(include_gpu=False, include_allocations=False))
        def launcher():
            path = codex.launcher_path()
            if path.read_text() != codex.launcher(): raise AssertionError('Unexpected launcher content')
            return {'independent_launcher': True, 'arguments_forwarded': True}
        check('independent-launcher', launcher)
        codex_binary = shutil.which('codex') or (str(Path.home() / '.local/bin/codex') if (Path.home() / '.local/bin/codex').exists() else None)
        if codex_binary:
            check('codex-version', lambda: subprocess.check_output([codex_binary, '--version'], text=True).strip())
            def permissions():
                actual = configuration()
                expected = codex.parse((codex.home() / 'config.toml').read_text()) if (codex.home() / 'config.toml').exists() else {}
                for key in ('approval_policy', 'sandbox_mode'):
                    if key in expected and actual[key] != expected[key]:
                        raise AssertionError('Agent configuration differs: ' + key)
                return {'source': 'Codex config/read', 'configuration': actual, 'model_turn_started': False}
            check('agent-permission-state', permissions)
        else:
            check('codex-availability', lambda: {'installed': False, 'reason': 'Not installed; no Agent query requested'})
        def unchanged():
            changed = [str(p) for p,data in before.items() if (p.read_bytes() if p.exists() else None) != data]
            if changed: raise AssertionError('Configuration changed during read-only checks: ' + ', '.join(changed))
            return {'configurations_unchanged': True, 'model_state': state['state']}
        check('configuration-retained', unchanged)
        report['status'] = 'passed'
        return report
    finally:
        if write_report:
            report['finished'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            fd, temporary = tempfile.mkstemp(prefix='.maa-report-', dir=result_path.parent)
            with os.fdopen(fd, 'w') as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
            os.replace(temporary, result_path)
            print('报告：' + str(result_path), flush=True)



if __name__ == '__main__':
    run()
