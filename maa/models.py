"""Native Ollama inventory/import and precise, pinned HF GGUF downloads."""
from contextlib import contextmanager
import json
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import urllib.error
import urllib.request
from urllib.parse import quote
from .backends import binary, ollama_endpoint, ollama_environment, wait_api, stop_process
from .gguf import metadata
from .http import request
from .store import Error, identity


def file_identity(path):
    stat = Path(path).stat()
    return [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns]


def verify_file(model):
    if model['backend'] == 'llamacpp' and file_identity(model['path']) != model['file_identity']:
        raise Error('Registered GGUF changed or was replaced; register it again before using it')


def local_model(path, backend='llamacpp', name=None):
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise Error('Model path must be a regular GGUF file')
    info = metadata(path)
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    key = identity(backend, str(path) + '@' + digest.hexdigest())
    return {'key': key, 'backend': backend, 'name': name or path.name, 'path': str(path),
            'file_identity': file_identity(path), 'sha256': digest.hexdigest(), 'metadata': info,
            'mtp_supported': info['maa.mtp_supported'], 'source': 'local'}


@contextmanager
def ollama_session(log):
    # Callers suspend the single managed service first. No models are loaded here.
    try:
        request(ollama_endpoint() + '/api/version', timeout=1)
    except Error:
        pass
    else:
        raise Error('An unmanaged Ollama server is already running. Stop it before maa model operations.')
    with open(log, 'ab') as output:
        process = subprocess.Popen([binary('ollama'), 'serve'], env=ollama_environment(),
                                   stdout=output, stderr=output)
        try:
            wait_api(ollama_endpoint() + '/api/version', process)
            yield
        finally:
            stop_process(process)


def ollama_inventory(store):
    rows = request(ollama_endpoint() + '/api/tags')['models']
    result = []
    for row in rows:
        name = row['name']
        if re.fullmatch(r'maa-[0-9a-f]{24}:latest', name):
            continue  # Private adaptation aliases are not user model choices.
        info = request(ollama_endpoint() + '/api/show', {'model': name}, timeout=60)
        data = info.get('model_info', {})
        arch = data.get('general.architecture', '')
        tensors = info.get('tensors', [])
        mtp = bool(data.get(arch + '.nextn_predict_layers', 0) or
                   (arch in ('qwen35', 'qwen35moe') and any(t.get('name', '').startswith('mtp.') for t in tensors)))
        model = {'key': identity('ollama', name + '@' + str(row.get('digest'))), 'backend': 'ollama', 'name': name,
                 'digest': row.get('digest'), 'metadata': data, 'mtp_supported': mtp,
                 'source': 'ollama', 'capabilities': info.get('capabilities', [])}
        store.register(model)
        result.append(model)
    return result


def ollama_install(store, name, gguf=None):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./:-]*', name) or '..' in name:
        raise Error('Invalid Ollama model name/tag')
    if gguf:
        path = Path(gguf).expanduser().resolve(strict=True)
        metadata(path)
        spec = store.path('import.Modelfile')
        spec.write_text('FROM ' + json.dumps(str(path)) + '\n')
        cmd = [binary('ollama'), 'create', name, '-f', str(spec)]
    else:
        cmd = [binary('ollama'), 'pull', name]
    subprocess.run(cmd, check=True, env=ollama_environment())
    models = ollama_inventory(store)
    normalized = name if ':' in name else name + ':latest'
    try:
        return next(row for row in models if row['name'] == normalized)
    except StopIteration:
        raise Error('Native installation completed but model is absent from the native inventory') from None


def hf_input(repo, filename):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise Error('HF repository must be publisher/repository')
    file = PurePosixPath(filename)
    if not filename or file.is_absolute() or '..' in file.parts or '\\' in filename or any(ord(c) < 32 for c in filename):
        raise Error('HF GGUF filename must be a relative file path without parent traversal')
    if not filename.lower().endswith('.gguf'):
        raise Error('Choose an exact GGUF file; Safetensors repositories cannot be loaded directly')


def hf_download(store, repo, filename):
    hf_input(repo, filename)
    headers = {}
    if os.environ.get('HF_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['HF_TOKEN']
    url = 'https://huggingface.co/api/models/' + repo + '/revision/main'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
            info = json.load(response)
    except urllib.error.HTTPError as exc:
        reason = 'Model repository not found' if exc.code == 404 else 'HF authentication/access error' if exc.code in (401, 403) else 'HF HTTP error'
        raise Error(f'{reason}: HTTP {exc.code}: {repo}') from exc
    except (OSError, ValueError) as exc:
        raise Error(f'HF metadata/network error: {exc}') from exc
    files = {row['rfilename'] for row in info['siblings']}
    if filename not in files:
        raise Error(f'Exact GGUF file not found: {repo}/{filename}')
    names = [filename]
    split = re.fullmatch(r'(.*)-(\d{5})-of-(\d{5})\.gguf', filename)
    if split:
        if split[2] != '00001':
            raise Error('Select the first GGUF shard (-00001-of-....gguf)')
        names = [f'{split[1]}-{n:05d}-of-{int(split[3]):05d}.gguf' for n in range(1, int(split[3]) + 1)]
        if any(name not in files for name in names):
            raise Error('HF repository has an incomplete GGUF shard set')
    commit = info['sha']
    folder = store.path('models') / identity('hf', repo + '@' + commit)
    for name in names:
        destination = folder / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            continue
        partial = destination.with_name(destination.name + '.part')
        # curl owns native progress and transfer failures; the model name is not
        # misreported as invalid when a network/disk failure occurs.
        link = f'https://huggingface.co/{repo}/resolve/{commit}/{quote(name, safe="/")}'
        cmd = ['curl', '--fail', '--location', '--retry', '2', '--continue-at', '-', '--output', str(partial), link]
        # Keep a token out of command argv/process listings.
        config = '' if not headers else 'header = ' + json.dumps('Authorization: ' + headers['Authorization']) + '\n'
        if config:
            cmd[1:1] = ['--config', '-']
        completed = subprocess.run(cmd, input=config, text=True)
        if completed.returncode:
            raise Error(f'HF download failed (curl {completed.returncode}); partial retained for retry: {partial}')
        if partial.stat().st_size == 0:
            raise Error('HF returned an empty GGUF file')
        partial.replace(destination)
    model = local_model(folder / filename)
    model.update(key=identity('llamacpp', repo + '@' + commit + '/' + filename),
                 name=repo + '/' + filename, source='hf', repo=repo, filename=filename, revision=commit)
    store.register(model)
    return model
