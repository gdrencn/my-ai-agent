"""Independent interface catalog."""
MESSAGES = {'about': 'About my-ai-agent',
 'add': 'Install / register model',
 'all_install': 'Install all',
 'allocation_log': 'Allocation records',
 'applied': 'Select Apply changes after editing; Back discards this edit.',
 'apply': 'Apply changes (reload if backend parameters changed)',
 'apply_codex': 'Apply changes',
 'back': 'Back',
 'backend': 'Select a backend',
 'base_label': 'Backend',
 'cancelled': 'Cancelled.',
 'choice_no': 'No',
 'choice_yes': 'Yes',
 'codex_config': 'codex-local configuration',
 'codex_global': 'Codex configuration',
 'codex_saved': 'codex-local configuration saved for the next Codex launch; backend runtime state retained.',
 'compact_readonly': 'Auto-compaction threshold (90%; read-only)',
 'compute': 'Compute buffers',
 'configure': 'Model configuration',
 'context': 'Context size',
 'context_input': 'Context usage (latest input)',
 'context_readonly': 'Context size (follows model; read-only)',
 'context_usage_value': '{tokens} / {context} tokens ({percent:.1f}%)',
 'credential_prompt': 'Token / API key (not echoed):',
 'current': 'Current target: {backend} / {model} / {status}',
 'current_model': 'Current model',
 'current_suffix': ' (current)',
 'default': 'Default (no explicit override)',
 'dirty': 'Changes are pending. Select Apply changes to activate them; Back discards this edit.',
 'done': 'Operation completed.',
 'effective_context': 'Effective context',
 'empty': 'No local models are available. Install / register a model first.',
 'error': 'Error: {error}',
 'exit': 'Exit',
 'extra_allocation': '; additional allocation ',
 'filename': 'Exact relative GGUF filename (includes .gguf; not a URL):',
 'fit': 'Automatic VRAM fit',
 'flash_attention': 'Flash Attention',
 'follow': 'Follow main model',
 'gpu_amounts': 'Total {total}; used {used}; free {free}; driver reserved {reserved}',
 'gpu_layers': 'Model layers on GPU',
 'gpu_memory': 'Whole-device VRAM',
 'gpu_note': 'Whole-device VRAM includes other programs and driver usage; it is separate from identified '
             'allocations.',
 'gpu_sum': 'Identified VRAM allocations',
 'hf': 'Hugging Face GGUF',
 'idle': 'Idle (unloaded)',
 'input_keys': '←/→ Edit · Enter Submit · Esc Cancel',
 'install': 'Install backends / Codex CLI',
 'installed': 'my-ai-agent installed: {executable}\nRun {entry} to open the menu.',
 'installing': 'Installing my-ai-agent v{version}',
 'integer': '{label}: enter a {constraint}integer; blank keeps {value}.',
 'interrupted': 'maa: interrupted.',
 'keep_alive': 'Idle model residency',
 'kv': 'Main model KV format',
 'language': 'Language',
 'language_saved': 'Language saved.',
 'language_title': '请选择界面语言 / Select interface language',
 'last_output': 'Latest output',
 'last_verified_suffix': ' (last verified)',
 'layers_value': '{loaded}/{total} layers ({percent:.1f}%)',
 'loading': 'Loading',
 'local': 'Local GGUF file',
 'main_kv': 'Main model KV',
 'memory_note': 'Buffer values are native allocations from the current load; CPU_Mapped is mapped size, not '
                'actual RSS.',
 'memory_separator': '; ',
 'menu_back': 'Back',
 'menu_cancel': 'Cancel',
 'menu_exit': 'Exit',
 'menu_keys': '↑/↓ Select · Enter/→ Confirm · Esc/← {action}',
 'menu_multi_keys': '↑/↓ Select · Space Toggle · Enter Confirm · Esc {action}',
 'model_applied': 'Model configuration applied.',
 'model_file': 'Model: ',
 'model_name': 'Ollama model name (for example qwen3:0.6b):',
 'model_path': 'Path: ',
 'model_revision': 'Revision: ',
 'model_source': 'Source: ',
 'model_status': 'Current model status',
 'model_title': 'Select a downloaded or registered local llama.cpp GGUF model.',
 'models_menu': 'Local model management',
 'mtp': 'MTP',
 'mtp_compute': 'MTP compute buffers',
 'mtp_kv': 'MTP KV format',
 'mtp_kv_status': 'MTP KV',
 'mtp_unavailable': 'Unavailable',
 'no_target': 'No model selected.',
 'nonnegative': 'nonnegative ',
 'not_applicable': 'Not applicable',
 'not_enabled': 'Not enabled',
 'off': 'Off',
 'off_restore': 'Off (restore original settings)',
 'official': 'Ollama official models',
 'ollama_model_title': 'Select an Ollama local model; the running managed server is queried directly.',
 'on': 'On',
 'options': 'Options',
 'output_buffer': 'Output buffers',
 'path': 'Absolute path to an existing GGUF file:',
 'pause': 'Pause current model to release resources',
 'paused': 'Paused',
 'positive': 'positive ',
 'progress_elapsed': ' — elapsed {elapsed:.1f}s',
 'progress_failed': 'Failed',
 'progress_in_progress': 'In progress',
 'progress_interrupted': 'Interrupted',
 'progress_success': 'Success',
 'progress_wait': ' — waited {elapsed:.1f}s',
 'reasoning': 'Codex reasoning effort',
 'refresh': 'Refresh',
 'repo': 'HF repository (publisher/repository):',
 'reserve_mib': 'Reserved VRAM (MiB)',
 'result': 'Result',
 'rs': 'Recurrent state buffer RS',
 'run_state': 'Runtime state',
 'running': 'Running',
 'saved_context': 'Saved context',
 'saved_suffix': ' (last verified; saved)',
 'select': 'Set local model (switch immediately)',
 'separator': ': ',
 'shared': 'Shared (counted once)',
 'source': 'Select the model source',
 'start': 'Start current model',
 'state_error': 'Cannot read runtime state',
 'statistics_time': 'Statistics time',
 'status': 'Current status and configuration',
 'stopped': 'Paused',
 'stopping': 'Stopping',
 'system_mapped': 'System memory mapping',
 'system_memory': 'System memory ',
 'title': 'my-ai-agent',
 'unavailable': 'Unavailable: no verifiable MTP weights in this model',
 'unchanged': 'Configuration unchanged; current runtime state retained.',
 'unknown': 'Unavailable',
 'unselected': 'Not selected',
 'usage_note': 'Direct connection: the backend provides no verifiable token counts for the latest request; '
               'missing values are not estimated.',
 'weights': 'Model weights',
 'yolo': 'YOLO mode'}
TEXT = {'%(prog)s: error: %(message)s\n': '%(prog)s: error: %(message)s\n',
 'A running systemd system manager is required': 'A running systemd system manager is required',
 'Add a connection first': 'Add a connection first',
 'An unmanaged Ollama server is already running. Stop it before maa model operations.': 'An unmanaged Ollama '
                                                                                        'server is already '
                                                                                        'running. Stop it '
                                                                                        'before maa model '
                                                                                        'operations.',
 'An unmanaged llama.cpp endpoint is already listening; stop it before maa model operations': 'An unmanaged '
                                                                                              'llama.cpp '
                                                                                              'endpoint is '
                                                                                              'already '
                                                                                              'listening; '
                                                                                              'stop it '
                                                                                              'before maa '
                                                                                              'model '
                                                                                              'operations',
 'Backend readiness timed out: {v0}': 'Backend readiness timed out: {v0}',
 'Backup exists; explicit overwrite required': 'Backup exists; explicit overwrite required',
 'Cannot communicate with the systemd system manager: {v0}': 'Cannot communicate with the systemd system '
                                                             'manager: {v0}',
 'Cannot read language configuration {v0}: {v1}': 'Cannot read language configuration {v0}: {v1}',
 'Cannot read native unit state': 'Cannot read native unit state',
 'Cannot read {v0}: {v1}': 'Cannot read {v0}: {v1}',
 'Choose an exact GGUF file; Safetensors repositories cannot be loaded directly': 'Choose an exact GGUF '
                                                                                  'file; Safetensors '
                                                                                  'repositories cannot be '
                                                                                  'loaded directly',
 'Codex CLI is not installed; run maa install codex': 'Codex CLI is not installed; run maa install codex',
 'Codex configuration reader exited before returning its state': 'Codex configuration reader exited before '
                                                                 'returning its state',
 'Codex configuration response is oversized': 'Codex configuration response is oversized',
 'Codex could not return its configuration': 'Codex could not return its configuration',
 'Codex rejected configuration initialization': 'Codex rejected configuration initialization',
 'Codex returned an invalid configuration': 'Codex returned an invalid configuration',
 'Connection ID mismatch': 'Connection ID mismatch',
 'Connection already exists; remove it explicitly before importing': 'Connection already exists; remove it '
                                                                     'explicitly before importing',
 'Connection changed concurrently; close it again': 'Connection changed concurrently; close it again',
 'Connection does not exist': 'Connection does not exist',
 'Connection shutdown not confirmed; local data retained': 'Connection shutdown not confirmed; local data '
                                                           'retained',
 'Connection stopped': 'Connection stopped',
 'Current model or configuration changed during editing; reopen the configuration menu': 'Current model or '
                                                                                         'configuration '
                                                                                         'changed during '
                                                                                         'editing; reopen '
                                                                                         'the configuration '
                                                                                         'menu',
 'Dependencies remain unavailable after installation: {v0}': 'Dependencies remain unavailable after '
                                                             'installation: {v0}',
 'Duplicate or mismatched backup connections': 'Duplicate or mismatched backup connections',
 'Duplicate platform account': 'Duplicate platform account',
 'Exact GGUF file not found: {v0}/{v1}': 'Exact GGUF file not found: {v0}/{v1}',
 'Existing command is not owned by maa: {v0}': 'Existing command is not owned by maa: {v0}',
 'Expected managed key=value: {v0}': 'Expected managed key=value: {v0}',
 'GGUF changed during registration; retry: {v0}': 'GGUF changed during registration; retry: {v0}',
 'GGUF shard must be an existing regular file: {v0}': 'GGUF shard must be an existing regular file: {v0}',
 'HF GGUF checksum mismatch after retry; damaged cache removed: {v0}': 'HF GGUF checksum mismatch after '
                                                                       'retry; damaged cache removed: {v0}',
 'HF GGUF filename must be a relative file path without parent traversal': 'HF GGUF filename must be a '
                                                                           'relative file path without '
                                                                           'parent traversal',
 'HF cache path was replaced by a symbolic link; remove it before retrying: {v0}': 'HF cache path was '
                                                                                   'replaced by a symbolic '
                                                                                   'link; remove it before '
                                                                                   'retrying: {v0}',
 'HF download failed (curl {v0}); partial retained for retry: {v1}': 'HF download failed (curl {v0}); '
                                                                     'partial retained for retry: {v1}',
 'HF metadata/network error: {v0}': 'HF metadata/network error: {v0}',
 'HF partial cache is a symbolic link; remove it before retrying: {v0}': 'HF partial cache is a symbolic '
                                                                         'link; remove it before retrying: '
                                                                         '{v0}',
 'HF publisher/repository': 'HF publisher/repository',
 'HF repository has an incomplete GGUF shard set': 'HF repository has an incomplete GGUF shard set',
 'HF repository must be publisher/repository': 'HF repository must be publisher/repository',
 'HF returned an incomplete GGUF file; retry: {v0}': 'HF returned an incomplete GGUF file; retry: {v0}',
 'HF returned invalid GGUF data; retry: {v0}': 'HF returned invalid GGUF data; retry: {v0}',
 'HTTP {v0} from {v1}: {v2}': 'HTTP {v0} from {v1}: {v2}',
 'Install missing dependencies with your package manager: {v0}': 'Install missing dependencies with your '
                                                                 'package manager: {v0}',
 'Installed backend does not support: {v0}': 'Installed backend does not support: {v0}',
 'Installing dependencies requires root or sudo: {v0}': 'Installing dependencies requires root or sudo: {v0}',
 'Interactive menu requires a terminal; use maa --help for CLI commands': 'Interactive menu requires a '
                                                                          'terminal; use maa --help for CLI '
                                                                          'commands',
 'Invalid Codex TOML: {v0}': 'Invalid Codex TOML: {v0}',
 'Invalid GGUF array': 'Invalid GGUF array',
 'Invalid GGUF header': 'Invalid GGUF header',
 'Invalid GGUF string length': 'Invalid GGUF string length',
 'Invalid GGUF tensor dimensions': 'Invalid GGUF tensor dimensions',
 'Invalid Ollama model name/tag': 'Invalid Ollama model name/tag',
 'Invalid connection ID': 'Invalid connection ID',
 'Invalid connection fields': 'Invalid connection fields',
 'Invalid connection state': 'Invalid connection state',
 'Invalid credential file': 'Invalid credential file',
 'Invalid language configuration: {v0}': 'Invalid language configuration: {v0}',
 'Invalid message deduplication state': 'Invalid message deduplication state',
 'Invalid receive cursor': 'Invalid receive cursor',
 'Invalid receive state': 'Invalid receive state',
 'Language configuration must not be a symbolic link: {v0}': 'Language configuration must not be a symbolic '
                                                             'link: {v0}',
 'Language must be zh_cn or en_us': 'Language must be zh_cn or en_us',
 'Legacy GGUF shard registration is incomplete; register the first shard again before using it': 'Legacy '
                                                                                                 'GGUF shard '
                                                                                                 'registration '
                                                                                                 'is '
                                                                                                 'incomplete; '
                                                                                                 'register '
                                                                                                 'the first '
                                                                                                 'shard '
                                                                                                 'again '
                                                                                                 'before '
                                                                                                 'using it',
 'Legacy maa.service was modified or belongs to another user; refusing to remove it': 'Legacy maa.service '
                                                                                      'was modified or '
                                                                                      'belongs to another '
                                                                                      'user; refusing to '
                                                                                      'remove it',
 'Linux and Python 3.11+ are required': 'Linux and Python 3.11+ are required',
 'Local deletion requires --yes': 'Local deletion requires --yes',
 'Local model catalog was modified; refusing to overwrite it': 'Local model catalog was modified; refusing '
                                                               'to overwrite it',
 'MTP is unavailable: model metadata has no supported MTP weights': 'MTP is unavailable: model metadata has '
                                                                    'no supported MTP weights',
 'Model is not registered: {v0}': 'Model is not registered: {v0}',
 'Model path must be a regular GGUF file': 'Model path must be a regular GGUF file',
 'Native API response exceeded 32 MiB': 'Native API response exceeded 32 MiB',
 'Native backend did not report a valid effective context': 'Native backend did not report a valid effective '
                                                            'context',
 'Native backend exited with code {v0}; inspect maa logs': 'Native backend exited with code {v0}; inspect '
                                                           'maa logs',
 'Native backend readiness timed out: {v0}': 'Native backend readiness timed out: {v0}',
 'Native configuration is not owned by this installation: {v0}': 'Native configuration is not owned by this '
                                                                 'installation: {v0}',
 'Native installation completed but model is absent from the native inventory': 'Native installation '
                                                                                'completed but model is '
                                                                                'absent from the native '
                                                                                'inventory',
 'Native service failed; inspect maa logs': 'Native service failed; inspect maa logs',
 'No private test message received; send the bot a message and retry': 'No private test message received; '
                                                                       'send the bot a message and retry',
 'No saved language and no controlling terminal; use --language zh_cn or --language en_us': 'No saved '
                                                                                            'language and no '
                                                                                            'controlling '
                                                                                            'terminal; use '
                                                                                            '--language '
                                                                                            'zh_cn or '
                                                                                            '--language '
                                                                                            'en_us',
 'No verified context for the current model; run maa start before changing codex-local configuration': 'No '
                                                                                                       'verified '
                                                                                                       'context '
                                                                                                       'for '
                                                                                                       'the '
                                                                                                       'current '
                                                                                                       'model; '
                                                                                                       'run '
                                                                                                       'maa '
                                                                                                       'start '
                                                                                                       'before '
                                                                                                       'changing '
                                                                                                       'codex-local '
                                                                                                       'configuration',
 'Not a supported GGUF v2/v3 file: {v0}': 'Not a supported GGUF v2/v3 file: {v0}',
 'Ollama /api/ps did not report a valid context_length': 'Ollama /api/ps did not report a valid '
                                                         'context_length',
 'Ollama /api/ps did not report effective context_length': 'Ollama /api/ps did not report effective '
                                                           'context_length',
 'Ollama /api/ps returned an invalid model list': 'Ollama /api/ps returned an invalid model list',
 'Ollama loaded model no longer matches the accepted configuration': 'Ollama loaded model no longer matches '
                                                                     'the accepted configuration',
 'Ollama model tag changed; refresh maa models and select the current model again': 'Ollama model tag '
                                                                                    'changed; refresh maa '
                                                                                    'models and select the '
                                                                                    'current model again',
 'Ollama name:tag': 'Ollama name:tag',
 'Ollama original-configuration backup changed; refusing to overwrite it': 'Ollama original-configuration '
                                                                           'backup changed; refusing to '
                                                                           'overwrite it',
 'Ollama requires --name; --path optionally imports GGUF': 'Ollama requires --name; --path optionally '
                                                           'imports GGUF',
 'Platform HTTP {v0}': 'Platform HTTP {v0}',
 'Platform network request failed': 'Platform network request failed',
 'Platform response exceeds size limit': 'Platform response exceeds size limit',
 'Platform returned invalid JSON': 'Platform returned invalid JSON',
 'Quantized KV requires Flash Attention; select f16 before disabling it': 'Quantized KV requires Flash '
                                                                          'Attention; select f16 before '
                                                                          'disabling it',
 'Quantized MTP KV requires Flash Attention; select f16 or follow before disabling it': 'Quantized MTP KV '
                                                                                        'requires Flash '
                                                                                        'Attention; select '
                                                                                        'f16 or follow '
                                                                                        'before disabling it',
 'Registered GGUF changed, is missing or was replaced; register it again before using it: {v0}': 'Registered '
                                                                                                 'GGUF '
                                                                                                 'changed, '
                                                                                                 'is missing '
                                                                                                 'or was '
                                                                                                 'replaced; '
                                                                                                 'register '
                                                                                                 'it again '
                                                                                                 'before '
                                                                                                 'using it: '
                                                                                                 '{v0}',
 'Registered GGUF shard set is incomplete; register it again': 'Registered GGUF shard set is incomplete; '
                                                               'register it again',
 'Select a local model first': 'Select a local model first',
 'Select the first GGUF shard (-00001-of-....gguf)': 'Select the first GGUF shard (-00001-of-....gguf)',
 'Select the first GGUF shard of a valid shard set (-00001-of-....gguf)': 'Select the first GGUF shard of a '
                                                                          'valid shard set '
                                                                          '(-00001-of-....gguf)',
 'Selected Ollama model is not loaded (it may have expired); start it again': 'Selected Ollama model is not '
                                                                              'loaded (it may have expired); '
                                                                              'start it again',
 'Start failed: {v0}\n{v1}': 'Start failed: {v0}\n{v1}',
 'Switch failed: {v0}\n{v1}': 'Switch failed: {v0}\n{v1}',
 'This Ollama runner does not expose the required llama-server fit/draft options. Install the current official Ollama version; legacy runners cannot apply this configuration.': 'This '
                                                                                                                                                                                 'Ollama '
                                                                                                                                                                                 'runner '
                                                                                                                                                                                 'does '
                                                                                                                                                                                 'not '
                                                                                                                                                                                 'expose '
                                                                                                                                                                                 'the '
                                                                                                                                                                                 'required '
                                                                                                                                                                                 'llama-server '
                                                                                                                                                                                 'fit/draft '
                                                                                                                                                                                 'options. '
                                                                                                                                                                                 'Install '
                                                                                                                                                                                 'the '
                                                                                                                                                                                 'current '
                                                                                                                                                                                 'official '
                                                                                                                                                                                 'Ollama '
                                                                                                                                                                                 'version; '
                                                                                                                                                                                 'legacy '
                                                                                                                                                                                 'runners '
                                                                                                                                                                                 'cannot '
                                                                                                                                                                                 'apply '
                                                                                                                                                                                 'this '
                                                                                                                                                                                 'configuration.',
 'Timed out reading Codex configuration': 'Timed out reading Codex configuration',
 'Too many connections': 'Too many connections',
 'Truncated GGUF string': 'Truncated GGUF string',
 'Truncated GGUF: {v0}': 'Truncated GGUF: {v0}',
 'Unexpected platform API address': 'Unexpected platform API address',
 'Unexpected platform response': 'Unexpected platform response',
 'Unknown settings: {v0}': 'Unknown settings: {v0}',
 'Unrecognized receive data; refusing cleanup': 'Unrecognized receive data; refusing cleanup',
 'Unsupported GGUF metadata type: {v0}': 'Unsupported GGUF metadata type: {v0}',
 'Unsupported connection setting': 'Unsupported connection setting',
 'Use --token-file in noninteractive mode': 'Use --token-file in noninteractive mode',
 'Use an absolute, non-symlink backup path': 'Use an absolute, non-symlink backup path',
 'apply current model settings immediately': 'apply current model settings immediately',
 'argument %s: %s': 'argument %s: %s',
 'codex-local is not owned by maa; refusing to overwrite it': 'codex-local is not owned by maa; refusing to '
                                                              'overwrite it',
 'confirm local deletion; does not modify remote accounts': 'confirm local deletion; does not modify remote '
                                                            'accounts',
 'connection ID; omitted means all': 'connection ID; omitted means all',
 'download/import/register an exact model': 'download/import/register an exact model',
 'exact GGUF relative filename': 'exact GGUF relative filename',
 'expected %s argument': 'expected %s argument',
 'expected %s arguments': 'expected %s arguments',
 'expected at least one argument': 'expected at least one argument',
 'expected one argument': 'expected one argument',
 'immediately switch; save boot target': 'immediately switch; save boot target',
 'interface language; otherwise reuse saved selection or ask': 'interface language; otherwise reuse saved '
                                                               'selection or ask',
 'invalid %(type)s value: %(value)r': 'invalid %(type)s value: %(value)r',
 'invalid choice: %(value)r (choose from %(choices)s)': 'invalid choice: %(value)r (choose from %(choices)s)',
 'llama.cpp /props did not report a valid per-slot context': 'llama.cpp /props did not report a valid '
                                                             'per-slot context',
 'llama.cpp /props returned invalid metadata': 'llama.cpp /props returned invalid metadata',
 'llama.cpp did not report effective per-slot n_ctx': 'llama.cpp did not report effective per-slot n_ctx',
 'llama.cpp requires either --path, or both --repo and --file': 'llama.cpp requires either --path, or both '
                                                                '--repo and --file',
 'local GGUF path': 'local GGUF path',
 'maa-local.config.toml already exists and is not owned by maa; refusing to overwrite it': 'maa-local.config.toml '
                                                                                           'already exists '
                                                                                           'and is not owned '
                                                                                           'by maa; refusing '
                                                                                           'to overwrite it',
 'model key returned by maa models/add': 'model key returned by maa models/add',
 'my-ai-agent: manage local models and codex-local on Linux': 'my-ai-agent: manage local models and '
                                                              'codex-local on Linux',
 'official QR login; add or renew existing connection': 'official QR login; add or renew existing connection',
 'options': 'options',
 'positional arguments': 'positional arguments',
 'private JSON backup containing credentials': 'private JSON backup containing credentials',
 'private credential file; otherwise prompt without echo': 'private credential file; otherwise prompt '
                                                           'without echo',
 'refresh native Ollama / list registered llama.cpp models': 'refresh native Ollama / list registered '
                                                             'llama.cpp models',
 'run official native installers': 'run official native installers',
 'show or change interface language': 'show or change interface language',
 "show program's version number and exit": "show program's version number and exit",
 'show this help message and exit': 'show this help message and exit',
 'the following arguments are required: %s': 'the following arguments are required: %s',
 'unrecognized arguments: %s': 'unrecognized arguments: %s',
 'usage: ': 'usage: ',
 'validate and import; connections remain closed': 'validate and import; connections remain closed',
 'write two keys / restore their original values': 'write two keys / restore their original values',
 '{v0}\n{v1}': '{v0}\n{v1}',
 '{v0} is not installed; use maa install': '{v0} is not installed; use maa install',
 '{v0} must be a nonnegative integer': '{v0} must be a nonnegative integer',
 '{v0} must be a positive integer': '{v0} must be a positive integer',
 '{v0} must be a {v1} integer': '{v0} must be a {v1} integer',
 '{v0} must be an integer': '{v0} must be an integer',
 '{v0} must be on or off': '{v0} must be on or off',
 '{v0}: HTTP {v1}: {v2}': '{v0}: HTTP {v1}: {v2}',
 '{v0}: choose from {v1}': '{v0}: choose from {v1}',
 '{v0}: error: {v1}\n': '{v0}: error: {v1}\n',
 '{v0}: only one connection is supported': '{v0}: only one connection is supported',
 '{v0}: use on/off': '{v0}: use on/off',
 '{v0}: {v1}': '{v0}: {v1}',
 '下载 GGUF：{v0}': 'Download GGUF: {v0}',
 '下载安装程序：{v0}': 'Download installer: {v0}',
 '保存 codex-local 配置；保留底座运行状态': 'Save codex-local configuration; retain backend runtime state',
 '修复不完整的 GGUF 缓存：{v0}': 'Repair incomplete GGUF cache: {v0}',
 '停止原底座': 'Stop previous backend',
 '准备 Ollama 模型配置': 'Prepare Ollama model configuration',
 '准备底座服务': 'Prepare backend service',
 '准备模型管理服务': 'Prepare model management service',
 '准备运行依赖': 'Prepare runtime dependencies',
 '切换失败，恢复原目标': 'Switch failed; restore previous target',
 '加载 Ollama 模型': 'Load Ollama model',
 '同步 Codex 本地配置和模型目录': 'Synchronize Codex local configuration and model catalog',
 '启动原生底座': 'Start native backend',
 '启动失败，恢复原暂停状态': 'Start failed; restore previous paused state',
 '启动已保存的原生底座配置': 'Start saved native backend configuration',
 '启动当前模型': 'Start current model',
 '唤醒 llama.cpp 模型': 'Wake llama.cpp model',
 '安装 / 登记模型': 'Install / register model',
 '安装依赖：{v0}': 'Install dependencies: {v0}',
 '安装底座 / Codex CLI': 'Install backends / Codex CLI',
 '官方安装：{v0}': 'Official install: {v0}',
 '官方安装：{v0} — {v1}\n': 'Official install: {v0} — {v1}\n',
 '应用模型配置': 'Apply model configuration',
 '应用配置': 'Apply configuration',
 '当前模型已运行；复用现有底座': 'Current model is running; reuse existing backend',
 '恢复原底座和模型': 'Restore previous backend and model',
 '恢复已提交目标并重新核验原生配置': 'Restore committed target and revalidate native configuration',
 '执行 Ollama 原生下载 / 导入': 'Run native Ollama download / import',
 '暂停当前模型': 'Pause current model',
 '更新 Codex 全局 YOLO 设置': 'Update Codex global YOLO settings',
 '核对 Hugging Face 仓库和精确文件': 'Check Hugging Face repository and exact file',
 '移除旧 maa 常驻服务': 'Remove legacy maa daemon',
 '等待原生底座和模型加载；原生日志：maa logs': 'Wait for native backend and model loading; native logs: maa logs',
 '读取 GGUF 元数据和计算模型身份': 'Read GGUF metadata and compute model identity',
 '读取 Ollama 原生模型清单': 'Read native Ollama model inventory',
 '读取本地模型清单': 'Read local model inventory',
 '配置未变化；保留当前运行状态': 'Configuration unchanged; retain current runtime state',
 '重新下载校验失败的 GGUF 缓存：{v0}': 'Redownload GGUF cache that failed verification: {v0}'}
