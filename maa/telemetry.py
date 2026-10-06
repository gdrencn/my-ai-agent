"""Bounded native allocation records, driver observations and token counters.

Backend APIs are queried by their own observers. Shared parsing here applies
only to the llama buffer log format actually emitted by those native runners.
"""
import csv
import io
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from .store import Error, read, write

LOG_LIMIT = 4 * 1024 * 1024
BUFFER = re.compile(r'([A-Za-z_][A-Za-z0-9_]*):\s+(\S+)\s+(model|KV|RS|compute|output)\s+buffer size\s*=\s*([\d.]+)\s*MiB')
LAYERS = re.compile(r'offloaded\s+(\d+)/(\d+)\s+layers to GPU')
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')


def launch_reference(path, offset, service_id):
    stat = Path(path).stat()
    return {'device': stat.st_dev, 'inode': stat.st_ino, 'offset': offset, 'service_id': service_id}


def allocations(blob, offset=0, truncated=False):
    """Latest actual tensor load, then target/MTP contexts; no fit estimates."""
    buffers, layers, phase, generation, shared, probing = {}, None, 'main', None, False, False
    initialized, rs_sequences = False, None
    position = offset
    for raw in blob.splitlines(keepends=True):
        line_position = position
        position += len(raw)
        line = ANSI.sub('', raw.decode(errors='replace'))
        if line.lstrip().startswith('{'):
            try:
                event = json.loads(line)
                line = event.get('message', event.get('msg', ''))
                if not isinstance(line, str):
                    continue
            except ValueError:
                continue
        # A new real load supersedes previous probes/retries and expired runners.
        # no_alloc fit probes do not allocate or emit actual buffer-size lines.
        probe = re.search(r'\bno_alloc\s*=\s*([01])\b', line)
        if probe:
            probing = probe[1] == '1'
        if probing:
            continue
        if 'load_tensors:' in line and 'loading model tensors' in line:
            buffers, layers, phase, shared = {}, None, 'main', False
            initialized, rs_sequences = False, None
            generation = line_position
        if 'llama_server:' in line and 'model loaded' in line:
            initialized = True
        if initialized:
            # These are allocation records for initialization. Later scheduler
            # reallocations cannot be attributed to target/draft by log order.
            continue
        match = LAYERS.search(line)
        if match:
            loaded, total = map(int, match.groups())
            layers = [loaded, total] if total > 0 and 0 <= loaded <= total else None
        if 'creating MTP draft context against the target model' in line:
            phase = 'mtp'
        if phase == 'main':
            match = re.search(r'\bn_rs_seq\s*=\s*(\d+)\b', line)
            if match:
                rs_sequences = int(match[1])
        if phase == 'mtp' and re.search(r'(?:KV|kv|cache).*\b(?:shared|sharing)\b', line):
            shared = True
        match = BUFFER.search(line)
        if not match:
            continue
        component, backend, kind, value = match.groups()
        value = float(value)
        if not math.isfinite(value) or value < 0:
            continue
        if generation is None:
            # Without the load boundary this may be a clipped or old fragment.
            continue
        key = (phase, component, backend, kind)
        buffers[key] = {'phase': phase, 'component': component, 'backend': backend,
                        'kind': kind, 'mib': value,
                        'location': 'host' if backend in ('CPU', 'BLAS') or backend.startswith('CPU_')
                        or backend.endswith('_Host') else 'gpu'}
    rows = list(buffers.values())
    return {'load_id': str(generation) if generation is not None else None,
            'gpu_layers': layers, 'buffers': rows, 'mtp_shared_kv': shared, 'rs_sequences': rs_sequences,
            'gpu_identified_mib': round(sum(row['mib'] for row in rows if row['location'] == 'gpu'), 2)
            if any(row['location'] == 'gpu' for row in rows) else None,
            'truncated': truncated,
            'error': 'Current load boundary is outside the bounded log window' if generation is None else None}


def native_allocations(store, runtime):
    launch = runtime.get('launch')
    empty = {'load_id': None, 'gpu_layers': None, 'buffers': [], 'gpu_identified_mib': None,
             'mtp_shared_kv': False, 'error': 'No current launch allocation record'}
    if not launch:
        return empty
    try:
        with store.path('native.log').open('rb') as source:
            import os
            stat = os.fstat(source.fileno())
            if [stat.st_dev, stat.st_ino] != [launch['device'], launch['inode']] or stat.st_size < launch['offset']:
                return {**empty, 'error': 'Native log was replaced or truncated'}
            start = max(launch['offset'], stat.st_size - LOG_LIMIT)
            source.seek(start)
            if start > launch['offset']:
                source.readline()  # Do not parse a partial first record.
                start = source.tell()
            blob = source.read(LOG_LIMIT)
            if blob.count(b'=== my-ai-agent launch ') > 1 or (start > launch['offset'] and b'=== my-ai-agent launch ' in blob):
                return {**empty, 'error': 'Another service launch superseded this record'}
            return allocations(blob, start, start > launch['offset'])
    except (OSError, KeyError, TypeError, ValueError) as exc:
        return {**empty, 'error': str(exc)}


def nvidia_memory():
    binary = shutil.which('nvidia-smi')
    if not binary and Path('/usr/lib/wsl/lib/nvidia-smi').is_file():
        binary = '/usr/lib/wsl/lib/nvidia-smi'
    if not binary:
        return {'devices': [], 'error': 'nvidia-smi is unavailable'}
    base = [binary, '--format=csv,noheader,nounits']
    try:
        fields = ['index', 'name', 'memory.total', 'memory.used', 'memory.free', 'memory.reserved']
        proc = subprocess.run(base + ['--query-gpu=' + ','.join(fields)], capture_output=True, text=True, timeout=3)
        if proc.returncode:
            # Older NVML exposes basic memory but not reserved memory.
            fields = fields[:-1]
            proc = subprocess.run(base + ['--query-gpu=' + ','.join(fields)], capture_output=True, text=True, timeout=3)
        if proc.returncode:
            raise Error((proc.stderr or proc.stdout).strip()[:1000])
        devices = []
        for row in csv.reader(io.StringIO(proc.stdout[:65536])):
            if len(row) != len(fields):
                continue
            def number(value):
                try:
                    result = float(value.strip())
                    return result if math.isfinite(result) and result >= 0 else None
                except ValueError:
                    return None
            devices.append({'index': row[0].strip(), 'name': row[1].strip(),
                            'total_mib': number(row[2]), 'used_mib': number(row[3]),
                            'free_mib': number(row[4]), 'reserved_mib': number(row[5]) if len(row) > 5 else None})
        return {'devices': devices, 'error': None if devices else 'Driver returned no GPU memory data'}
    except (OSError, Error, subprocess.SubprocessError) as exc:
        return {'devices': [], 'error': str(exc)}


class UsageRecorder:
    """Only counts and identity; never store prompts, output or tool payloads."""
    def __init__(self, store, runtime):
        self.store, self.runtime, self.lock = store, runtime, threading.Lock()

    def __call__(self, response):
        with self.lock:
            current = read(self.store.path('runtime.json'), {}) or {}
            service_id = self.runtime.get('launch', {}).get('service_id')
            if not service_id or current.get('launch', {}).get('service_id') != service_id:
                return  # A retired service must not publish counters for its successor.
            usage = response.get('usage') or {}
            def count(key):
                value = usage.get(key)
                return value if type(value) is int and value >= 0 else None
            write(self.store.path('usage.json'), {'service_id': service_id,
                  'fingerprint': self.runtime['fingerprint'], 'key': self.runtime['key'],
                  'load_id': native_allocations(self.store, self.runtime)['load_id'],
                  'input_tokens': count('input_tokens'), 'output_tokens': count('output_tokens'),
                  'recorded_at': time.time()})


def last_usage(store, runtime, load_id):
    usage = read(store.path('usage.json'))
    if not usage or not load_id:
        return None
    expected = {'service_id': runtime.get('launch', {}).get('service_id'),
                'fingerprint': runtime.get('fingerprint'), 'key': runtime.get('key'), 'load_id': load_id}
    return usage if all(usage.get(key) == value for key, value in expected.items()) else None
