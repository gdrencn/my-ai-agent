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
from .output import stage, native_output


def file_identity(path):
    stat = Path(path).stat()
    return [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns]


def shard_paths(path):
    path = Path(path)
    split = re.fullmatch(r'(.*)-(\d{5})-of-(\d{5})\.gguf', path.name)
    if not split:
        return [path]
    count = int(split[3])
    if split[2] != '00001' or not 1 <= count <= 10000:
        raise Error('Select the first GGUF shard of a valid shard set (-00001-of-....gguf)')
    return [path.with_name(f'{split[1]}-{n:05d}-of-{count:05d}.gguf') for n in range(1, count + 1)]


def verify_file(model):
    if model['backend'] != 'llamacpp':
        return
    paths = shard_paths(model['path'])
    records = model.get('files')
    if records is None:
        if len(paths) > 1:
            raise Error('Legacy GGUF shard registration is incomplete; register the first shard again before using it')
        records = [{'path': model['path'], 'file_identity': model['file_identity']}]
    if [str(path) for path in paths] != [row['path'] for row in records]:
        raise Error('Registered GGUF shard set is incomplete; register it again')
    for row in records:
        try:
            valid = file_identity(row['path']) == row['file_identity']
        except OSError:
            valid = False
        if not valid:
            raise Error('Registered GGUF changed, is missing or was replaced; register it again before using it: ' + row['path'])


def local_model(path, backend='llamacpp', name=None):
    stage('读取 GGUF 元数据和计算模型身份')
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise Error('Model path must be a regular GGUF file')
    info, records = None, []
    for shard in shard_paths(path):
        if not shard.is_file():
            raise Error('GGUF shard must be an existing regular file: ' + str(shard))
        initial = file_identity(shard)
        shard_info = metadata(shard)
        if info is None:
            info = shard_info
        digest = hashlib.sha256()
        with shard.open('rb') as source:
            for chunk in iter(lambda: source.read(4 * 1024 * 1024), b''):
                digest.update(chunk)
        if file_identity(shard) != initial:
            raise Error('GGUF changed during registration; retry: ' + str(shard))
        records.append({'path': str(shard), 'file_identity': initial, 'sha256': digest.hexdigest()})
    digest = records[0]['sha256'] if len(records) == 1 else hashlib.sha256(
        json.dumps([(row['path'], row['sha256']) for row in records]).encode()).hexdigest()
    key = identity(backend, str(path) + '@' + digest)
    return {'key': key, 'backend': backend, 'name': name or path.name, 'path': str(path),
            'file_identity': records[0]['file_identity'], 'sha256': digest, 'files': records, 'metadata': info,
            'mtp_supported': info['maa.mtp_supported'], 'source': 'local'}


@contextmanager
def ollama_session(log, values=None):
    # Callers suspend the single managed service first. No models are loaded here.
    try:
        request(ollama_endpoint() + '/api/version', timeout=1)
    except Error:
        pass
    else:
        raise Error('An unmanaged Ollama server is already running. Stop it before maa model operations.')
    with open(log, 'ab') as output:
        process = subprocess.Popen([binary('ollama'), 'serve'], env=ollama_environment(values),
                                   stdout=output, stderr=output)
        try:
            wait_api(ollama_endpoint() + '/api/version', process)
            yield
        finally:
            stop_process(process)


def ollama_inventory(store):
    stage('读取 Ollama 原生模型清单')
    rows = request(ollama_endpoint() + '/api/tags')['models']
    result = []
    for row in rows:
        name = row['name']
        if re.fullmatch(r'maa-(?:(?:source-)?[0-9a-f]{24}|rollback-[0-9a-f]{32}):latest', name):
            continue  # Private adaptation aliases are not user model choices.
        info = request(ollama_endpoint() + '/api/show', {'model': name}, timeout=60)
        data = info.get('model_info', {})
        arch = data.get('general.architecture', '')
        tensors = info.get('tensors', [])
        mtp = bool(data.get(arch + '.nextn_predict_layers', 0) or
                   (arch in ('qwen35', 'qwen35moe') and any(t.get('name', '').startswith('mtp.') for t in tensors)))
        from .store import read
        origin = read(store.path('ollama-originals.json'), {}).get(name)
        managed = origin and row.get('digest') in (origin['digest'], origin.get('configured_digest'))
        digest = origin['digest'] if managed else row.get('digest')
        model = {'key': identity('ollama', name + '@' + str(digest)), 'backend': 'ollama', 'name': name,
                 'digest': digest, 'metadata': data, 'mtp_supported': mtp,
                 'source': 'ollama', 'capabilities': info.get('capabilities', [])}
        store.register(model)
        result.append(model)
    return result


def ollama_input(name, gguf=None):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./:-]*', name) or '..' in name:
        raise Error('Invalid Ollama model name/tag')
    if gguf:
        path = Path(gguf).expanduser().resolve(strict=True)
        for shard in shard_paths(path):
            metadata(shard)


def ollama_install(store, name, gguf=None):
    ollama_input(name, gguf)
    if gguf:
        path = Path(gguf).expanduser().resolve(strict=True)
        spec = store.path('import.Modelfile')
        spec.write_text('FROM ' + json.dumps(str(path)) + '\n')
        cmd = [binary('ollama'), 'create', name, '-f', str(spec)]
    else:
        cmd = [binary('ollama'), 'pull', name]
    stage('执行 Ollama 原生下载 / 导入')
    with native_output():
        subprocess.run(cmd, check=True, env=ollama_environment())
    return name if ':' in name else name + ':latest'


def hf_input(repo, filename):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise Error('HF repository must be publisher/repository')
    file = PurePosixPath(filename)
    if not filename or file.is_absolute() or '..' in file.parts or '\\' in filename or any(ord(c) < 32 for c in filename):
        raise Error('HF GGUF filename must be a relative file path without parent traversal')
    if not filename.lower().endswith('.gguf'):
        raise Error('Choose an exact GGUF file; Safetensors repositories cannot be loaded directly')


def hf_download(store, repo, filename):
    stage('核对 Hugging Face 仓库和精确文件')
    hf_input(repo, filename)
    headers = {}
    if os.environ.get('HF_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['HF_TOKEN']
    url = 'https://huggingface.co/api/models/' + repo + '/revision/main?blobs=true'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
            info = json.load(response)
    except urllib.error.HTTPError as exc:
        reason = 'Model repository not found' if exc.code == 404 else 'HF authentication/access error' if exc.code in (401, 403) else 'HF HTTP error'
        raise Error(f'{reason}: HTTP {exc.code}: {repo}') from exc
    except (OSError, ValueError) as exc:
        raise Error(f'HF metadata/network error: {exc}') from exc
    files = {row['rfilename']: row for row in info['siblings']}
    if filename not in files:
        raise Error(f'Exact GGUF file not found: {repo}/{filename}')
    names = [filename]
    split = re.fullmatch(r'(.*)-(\d{5})-of-(\d{5})\.gguf', filename)
    if split:
        if split[2] != '00001' or not 1 <= int(split[3]) <= 10000:
            raise Error('Select the first GGUF shard (-00001-of-....gguf)')
        names = [f'{split[1]}-{n:05d}-of-{int(split[3]):05d}.gguf' for n in range(1, int(split[3]) + 1)]
        if any(name not in files for name in names):
            raise Error('HF repository has an incomplete GGUF shard set')
    commit = info['sha']
    folder = store.path('models') / identity('hf', repo + '@' + commit)
    with store.lock('download-' + identity('hf', repo + '@' + commit + '/' + filename)):
        for attempt in range(2):
            _hf_files(folder, names, repo, commit, files, headers)
            model = local_model(folder / filename)
            damaged = [name for row, name in zip(model['files'], names)
                       if (files[name].get('lfs') or {}).get('sha256') and
                       row['sha256'] != files[name]['lfs']['sha256']]
            if not damaged:
                break
            for name in damaged:
                (folder / name).unlink()
            if attempt:
                raise Error('HF GGUF checksum mismatch after retry; damaged cache removed: ' + ', '.join(damaged))
            stage('重新下载校验失败的 GGUF 缓存：' + ', '.join(damaged))
    model.update(key=identity('llamacpp', repo + '@' + commit + '/' + filename),
                 name=repo + '/' + filename, source='hf', repo=repo, filename=filename, revision=commit)
    return model


def _hf_files(folder, names, repo, commit, files, headers):
    for name in names:
        hf_input(repo, name)
        destination = folder / name
        if not destination.parent.resolve().is_relative_to(folder.resolve()) or destination.is_symlink():
            raise Error('HF cache path was replaced by a symbolic link; remove it before retrying: ' + str(destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        record = files[name]
        size = record.get('size') or (record.get('lfs') or {}).get('size')
        if destination.exists():
            try:
                metadata(destination)
                valid = size is None or destination.stat().st_size == size
            except (Error, OSError):
                valid = False
            if valid:
                continue
            stage('修复不完整的 GGUF 缓存：' + name)
            destination.unlink()
        partial = destination.with_name(destination.name + '.part')
        if partial.is_symlink():
            raise Error('HF partial cache is a symbolic link; remove it before retrying: ' + str(partial))
        # curl owns native progress and transfer failures; the model name is not
        # misreported as invalid when a network/disk failure occurs.
        link = f'https://huggingface.co/{repo}/resolve/{commit}/{quote(name, safe="/")}'
        cmd = ['curl', '--fail', '--location', '--retry', '2', '--continue-at', '-', '--output', str(partial), link]
        # Keep a token out of command argv/process listings.
        config = '' if not headers else 'header = ' + json.dumps('Authorization: ' + headers['Authorization']) + '\n'
        if config:
            cmd[1:1] = ['--config', '-']
        stage('下载 GGUF：' + name)
        with native_output():
            completed = subprocess.run(cmd, input=config, text=True)
        if completed.returncode:
            raise Error(f'HF download failed (curl {completed.returncode}); partial retained for retry: {partial}')
        if partial.stat().st_size == 0 or (size is not None and partial.stat().st_size != size):
            partial.unlink()
            raise Error('HF returned an incomplete GGUF file; retry: ' + name)
        try:
            metadata(partial)
        except Error:
            partial.unlink()
            raise Error('HF returned invalid GGUF data; retry: ' + name) from None
        partial.replace(destination)
