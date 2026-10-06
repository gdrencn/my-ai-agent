"""Read GGUF metadata/tensor names without loading weight data."""
import struct
from .store import Error

FORMATS = {0:'B', 1:'b', 2:'H', 3:'h', 4:'I', 5:'i', 6:'f', 7:'?', 10:'Q', 11:'q', 12:'d'}


def metadata(path):
    with open(path, 'rb') as source:
        def unpack(fmt):
            size = struct.calcsize('<' + fmt)
            data = source.read(size)
            if len(data) != size:
                raise Error(f'Truncated GGUF: {path}')
            return struct.unpack('<' + fmt, data)[0]

        def string(keep=True):
            length = unpack('Q')
            if length > 64 * 1024 * 1024:
                raise Error('Invalid GGUF string length')
            if keep:
                value = source.read(length)
                if len(value) != length:
                    raise Error('Truncated GGUF string')
                return value.decode('utf-8', errors='replace')
            source.seek(length, 1)

        def value(kind, keep=True):
            if kind in FORMATS:
                return unpack(FORMATS[kind])
            if kind == 8:
                return string(keep)
            if kind == 9:
                element, count = unpack('I'), unpack('Q')
                if count > 10_000_000 or element == 9:
                    raise Error('Invalid GGUF array')
                if element in FORMATS:
                    source.seek(struct.calcsize('<' + FORMATS[element]) * count, 1)
                else:
                    for _ in range(count):
                        value(element, False)
                return None
            raise Error(f'Unsupported GGUF metadata type: {kind}')

        if source.read(4) != b'GGUF' or unpack('I') not in (2, 3):
            raise Error(f'Not a supported GGUF v2/v3 file: {path}')
        tensors, pairs = unpack('Q'), unpack('Q')
        if pairs > 100_000 or tensors > 1_000_000:
            raise Error('Invalid GGUF header')
        result = {}
        for _ in range(pairs):
            key, kind = string(), unpack('I')
            val = value(kind)
            if val is not None:
                result[key] = val
        legacy_mtp = False
        for _ in range(tensors):
            name, dimensions = string(), unpack('I')
            if dimensions > 8:
                raise Error('Invalid GGUF tensor dimensions')
            source.seek(8 * dimensions + 4 + 8, 1)
            legacy_mtp |= name.startswith('mtp.')
        arch = result.get('general.architecture', '')
        result['maa.mtp_supported'] = bool(result.get(arch + '.nextn_predict_layers', 0) or
                                          (arch in ('qwen35', 'qwen35moe') and legacy_mtp))
        return result
