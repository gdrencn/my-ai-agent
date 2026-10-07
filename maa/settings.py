"""One validated schema for menus, CLI, persisted models and adapters."""
from .store import Error

KV = ('f16', 'q8_0', 'q4_0')
KEEP = ('5m', '10m', '30m', '-1')
EFFORT = ('default', 'none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')
DEFAULTS = dict(context=262144, kv='q8_0', flash_attention=True, fit=True,
                reserve_mib=0, keep_alive='5m', mtp=True, mtp_kv='follow', reasoning='default')
BACKEND_KEYS = tuple(key for key in DEFAULTS if key != 'reasoning')


def settings(saved=None, changes=None, mtp_supported=False):
    values = {**DEFAULTS, **(saved or {}), **(changes or {})}
    unknown = set(values) - set(DEFAULTS)
    if unknown:
        raise Error('Unknown settings: ' + ', '.join(sorted(unknown)))
    for key in ('context', 'reserve_mib'):
        if type(values[key]) is not int or values[key] < (1 if key == 'context' else 0):
            raise Error(f'{key} must be a {"positive" if key == "context" else "nonnegative"} integer')
    for key in ('flash_attention', 'fit', 'mtp'):
        if type(values[key]) is not bool:
            raise Error(f'{key} must be on or off')
    for key, choices in (('kv', KV), ('mtp_kv', ('follow',) + KV), ('keep_alive', KEEP), ('reasoning', EFFORT)):
        if values[key] not in choices:
            raise Error(f'{key}: choose from {", ".join(choices)}')
    if not mtp_supported:
        if (changes or {}).get('mtp') is True:
            raise Error('MTP is unavailable: model metadata has no supported MTP weights')
        values['mtp'] = False
    if not values['flash_attention'] and values['kv'] != 'f16':
        raise Error('Quantized KV requires Flash Attention; select f16 before disabling it')
    if values['mtp'] and not values['flash_attention'] and draft_kv(values) != 'f16':
        raise Error('Quantized MTP KV requires Flash Attention; select f16 or follow before disabling it')
    return values


def draft_kv(values):
    return values['kv'] if values['mtp_kv'] == 'follow' else values['mtp_kv']


def duration(value):
    return -1 if value == '-1' else int(value[:-1]) * 60
