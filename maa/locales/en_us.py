"""Project-owned en_us interface catalog."""
MESSAGES = {'im_menu': 'Chat connections',
 'im_platform': 'Platform',
 'im_name': 'Local name',
 'im_identity': 'Platform account',
 'im_platforms': 'Platform connections',
 'im_program': 'Connector program',
 'im_backups': 'Backup and recovery',
 'im_runtime_state': 'Runtime state (read-only)',
 'im_read_error': 'Cannot read status; retrying automatically',
 'im_stale': 'These are the last observed values; the current state is unknown.',
 'im_removed': 'Another operation deleted this connection. Return to the parent menu.',
 'im_connection_state': 'Connection state',
 'im_received': 'Texts received',
 'im_sent': 'Messages sent',
 'im_uncertain': 'Uncertain deliveries',
 'im_last_received': 'Last received',
 'im_last_sent': 'Last sent',
 'im_error': 'Diagnostic',
 'im_qr': 'Scan the QR code with WeChat, or open the official authorization link below. Ctrl+C cancels.',
 'im_backup_path': 'Absolute export path (contains credentials; keep it private):',
 'im_overwrite': 'File {path} exists. Overwrite it?',
 'im_exported': 'Connection backup exported: {path}',
 'im_name_input': 'Local name (blank uses the platform name):',
 'im_token': 'Token / API key (hidden input):',
 'im_owner_input': 'Telegram user ID (positive integer; blank allows binding later):',
 'im_verify': 'Enter the pairing code shown in WeChat:',
 'im_added': 'Added and kept closed. Bind a user, enable the connection, then send a private text to receive the '
             'fixed test reply.',
 'im_switch': 'Connection enabled',
 'im_reply': 'Fixed test reply',
 'im_credential': 'Credential',
 'im_credential_set': 'Configured',
 'im_owner': 'Allowed test user',
 'im_unbound': 'Not bound',
 'im_export': 'Export this connection',
 'im_delete': 'Delete local connection',
 'im_edit': 'Enter the new value (blank keeps {value}):',
 'im_close_to_bind': 'Close this connection before binding a test user.',
 'im_owner_manual': 'Enter user ID',
 'im_owner_receive': 'Receive a private message and confirm its user',
 'im_send_private': 'Send a private text to this Telegram bot; you will confirm the sender ID after it arrives.',
 'im_wait_private': 'Waiting for a Telegram private test message',
 'im_confirm_owner': 'Allow user {owner} to test this bot?',
 'im_confirm_delete': 'Delete local credentials, configuration and receive state for {name}? The remote account '
                      'is retained.',
 'im_add': 'Add connection',
 'im_module_switch': 'All connections enabled',
 'im_connections': ' connections',
 'im_install': 'Install / update connector program',
 'im_installed': 'Installed',
 'im_not_installed': 'Not installed',
 'im_export_all': 'Export all connections',
 'im_import': 'Import connection backup',
 'im_import_path': 'Absolute connection backup path:',
 'im_imported': 'Connections imported and kept closed. Authorize again if credentials have expired.',
 'im_uninstall': 'Uninstall chat connectors',
 'im_closed': 'Closed',
 'im_test_only': 'Basic send/receive test: fixed text replies only; Codex is not connected yet.',
 'im_confirm_uninstall': 'Uninstall connectors and delete all local connection data? Remote accounts, local '
                         'models and Codex are retained.',
 'menu_keys': '↑/↓ Select · Enter/→ Confirm · Esc/← {action}',
 'menu_multi_keys': '↑/↓ Select · Space Toggle · Enter Confirm · Esc {action}',
 'menu_cancel': 'Cancel',
 'menu_back': 'Back',
 'menu_exit': 'Exit',
 'input_keys': '←/→ Edit · Enter Submit · Esc Cancel',
 'choice_no': 'No',
 'choice_yes': 'Yes',
 'title': 'my-ai-agent',
 'install': 'Install backends / Codex CLI',
 'add': 'Install / register model',
 'select': 'Set local model (switch immediately)',
 'configure': 'Model configuration',
 'pause': 'Pause current model to release resources',
 'start': 'Start current model',
 'yolo': 'YOLO mode',
 'models_menu': 'Local model management',
 'codex_config': 'codex-local configuration',
 'codex_global': 'Codex configuration',
 'model_status': 'Current model status',
 'refresh': 'Refresh',
 'off_restore': 'Off (restore original settings)',
 'current_model': 'Current model',
 'run_state': 'Runtime state',
 'base_label': 'Backend',
 'dirty': 'Changes are pending. Select Apply changes to activate them; Back discards this edit.',
 'applied': 'Select Apply changes after editing; Back discards this edit.',
 'status': 'Current status and configuration',
 'about': 'About my-ai-agent',
 'back': 'Back',
 'exit': 'Exit',
 'cancelled': 'Cancelled.',
 'done': 'Operation completed.',
 'empty': 'No local models are available. Install / register a model first.',
 'backend': 'Select a backend',
 'source': 'Select the model source',
 'official': 'Ollama official models',
 'hf': 'Hugging Face GGUF',
 'local': 'Local GGUF file',
 'model_name': 'Ollama model name (for example qwen3:0.6b):',
 'repo': 'HF repository (publisher/repository):',
 'filename': 'Exact relative GGUF filename (includes .gguf; not a URL):',
 'path': 'Absolute path to an existing GGUF file:',
 'model_file': 'Model: ',
 'model_source': 'Source: ',
 'model_revision': 'Revision: ',
 'model_path': 'Path: ',
 'context': 'Context size',
 'kv': 'Main model KV format',
 'flash_attention': 'Flash Attention',
 'fit': 'Automatic VRAM fit',
 'reserve_mib': 'Reserved VRAM (MiB)',
 'keep_alive': 'Idle model residency',
 'mtp': 'MTP',
 'mtp_kv': 'MTP KV format',
 'reasoning': 'Codex reasoning effort',
 'on': 'On',
 'off': 'Off',
 'follow': 'Follow main model',
 'default': 'Default (no explicit override)',
 'apply': 'Apply changes (reload if backend parameters changed)',
 'apply_codex': 'Apply changes',
 'unchanged': 'Configuration unchanged; current runtime state retained.',
 'codex_saved': 'codex-local configuration saved for the next Codex launch; backend runtime state retained.',
 'model_applied': 'Model configuration applied.',
 'unavailable': 'Unavailable: no verifiable MTP weights in this model',
 'integer': '{label}: enter a {constraint}integer; blank keeps {value}.',
 'positive': 'positive ',
 'nonnegative': 'nonnegative ',
 'no_target': 'No model selected.',
 'running': 'Running',
 'stopped': 'Paused',
 'idle': 'Idle (unloaded)',
 'paused': 'Paused',
 'loading': 'Loading',
 'stopping': 'Stopping',
 'unselected': 'Not selected',
 'state_error': 'Cannot read runtime state',
 'unknown': 'Unavailable',
 'not_applicable': 'Not applicable',
 'not_enabled': 'Not enabled',
 'mtp_unavailable': 'Unavailable',
 'shared': 'Shared (counted once)',
 'context_readonly': 'Context size (follows model; read-only)',
 'compact_readonly': 'Auto-compaction threshold (90%; read-only)',
 'gpu_layers': 'Model layers on GPU',
 'weights': 'Model weights',
 'main_kv': 'Main model KV',
 'rs': 'Recurrent state buffer RS',
 'compute': 'Compute buffers',
 'output_buffer': 'Output buffers',
 'mtp_kv_status': 'MTP KV',
 'mtp_compute': 'MTP compute buffers',
 'gpu_sum': 'Identified VRAM allocations',
 'gpu_memory': 'Whole-device VRAM',
 'effective_context': 'Effective context',
 'context_input': 'Context usage (latest input)',
 'saved_context': 'Saved context',
 'last_output': 'Latest output',
 'statistics_time': 'Statistics time',
 'memory_note': 'Buffer values are native allocations from the current load; CPU_Mapped is mapped size, not '
                'actual RSS.',
 'gpu_note': 'Whole-device VRAM includes other programs and driver usage; it is separate from identified '
             'allocations.',
 'current': 'Current target: {backend} / {model} / {status}',
 'model_title': 'Select a downloaded or registered local llama.cpp GGUF model.',
 'ollama_model_title': 'Select an Ollama local model; the running managed server is queried directly.',
 'result': 'Result',
 'error': 'Error: {error}',
 'language': 'Language',
 'language_title': '请选择界面语言 / Select interface language',
 'language_saved': 'Language saved.',
 'separator': ': ',
 'current_suffix': ' (current)',
 'saved_suffix': ' (last verified; saved)',
 'last_verified_suffix': ' (last verified)',
 'layers_value': '{loaded}/{total} layers ({percent:.1f}%)',
 'system_mapped': 'System memory mapping',
 'system_memory': 'System memory ',
 'memory_separator': '; ',
 'extra_allocation': '; additional allocation ',
 'allocation_log': 'Allocation records',
 'gpu_amounts': 'Total {total}; used {used}; free {free}; driver reserved {reserved}',
 'context_usage_value': '{tokens} / {context} tokens ({percent:.1f}%)',
 'usage_note': 'Direct connection: the backend provides no verifiable token counts for the latest request; '
               'missing values are not estimated.',
 'all_install': 'Install all',
 'wechat_label': 'WeChat',
 'im_connected': 'Connected',
 'im_connecting': 'Connecting',
 'im_connection_error': 'Connection error',
 'credential_prompt': 'Token / API key (not echoed):',
 'wechat_pairing_prompt': 'WeChat pairing code:',
 'progress_in_progress': 'In progress',
 'progress_success': 'Success',
 'progress_interrupted': 'Interrupted',
 'progress_failed': 'Failed',
 'progress_wait': ' — waited {elapsed:.1f}s',
 'progress_elapsed': ' — elapsed {elapsed:.1f}s',
 'installing': 'Installing my-ai-agent v{version}',
 'installed': 'my-ai-agent installed: {executable}\nRun {entry} to open the menu.',
 'interrupted': 'maa: interrupted.'}

TEXT = {'%(prog)s: error: %(message)s\n': '%(prog)s: error: %(message)s\n',
 'Add a connection first': 'Add a connection first',
 'An unmanaged Ollama server is already running. Stop it before maa model operations.': 'An unmanaged Ollama '
                                                                                        'server is already '
                                                                                        'running. Stop it before '
                                                                                        'maa model operations.',
 'An unmanaged llama.cpp endpoint is already listening; stop it before maa model operations': 'An unmanaged '
                                                                                              'llama.cpp endpoint '
                                                                                              'is already '
                                                                                              'listening; stop it '
                                                                                              'before maa model '
                                                                                              'operations',
 'Backend readiness timed out: {v0}': 'Backend readiness timed out: {v0}',
 'Backup exists; explicit overwrite required': 'Backup exists; explicit overwrite required',
 'Bind a Telegram test user before enabling': 'Bind a Telegram test user before enabling',
 'Cannot read language configuration {v0}: {v1}': 'Cannot read language configuration {v0}: {v1}',
 'Cannot read {v0}: {v1}': 'Cannot read {v0}: {v1}',
 'Choose an exact GGUF file; Safetensors repositories cannot be loaded directly': 'Choose an exact GGUF file; '
                                                                                  'Safetensors repositories '
                                                                                  'cannot be loaded directly',
 'Close this Telegram connection before binding': 'Close this Telegram connection before binding',
 'Codex CLI is not installed; run maa install codex': 'Codex CLI is not installed; run maa install codex',
 'Connection ID mismatch': 'Connection ID mismatch',
 'Connection already exists; remove it explicitly before importing': 'Connection already exists; remove it '
                                                                     'explicitly before importing',
 'Connection changed concurrently; close it again': 'Connection changed concurrently; close it again',
 'Connection does not exist': 'Connection does not exist',
 'Connection shutdown not confirmed; local data retained': 'Connection shutdown not confirmed; local data '
                                                           'retained',
 'Connector backup exceeds size limit': 'Connector backup exceeds size limit',
 'Connector installation changed; retry the command': 'Connector installation changed; retry the command',
 'Connector installation was modified or is not owned: {v0}': 'Connector installation was modified or is not '
                                                              'owned: {v0}',
 'Connector installation was removed; retry the command': 'Connector installation was removed; retry the command',
 'Connector state belongs to another user': 'Connector state belongs to another user',
 'Connector state directory must not be a symlink': 'Connector state directory must not be a symlink',
 'Connector state file must not be a symlink': 'Connector state file must not be a symlink',
 'Connectors require systemd inside mas': 'Connectors require systemd inside mas',
 'Current model or configuration changed during editing; reopen the configuration menu': 'Current model or '
                                                                                         'configuration changed '
                                                                                         'during editing; reopen '
                                                                                         'the configuration menu',
 'Duplicate or mismatched backup connections': 'Duplicate or mismatched backup connections',
 'Duplicate platform account': 'Duplicate platform account',
 'Exact GGUF file not found: {v0}/{v1}': 'Exact GGUF file not found: {v0}/{v1}',
 'Existing command is not owned by maa: {v0}': 'Existing command is not owned by maa: {v0}',
 'Expected a WeChat connection': 'Expected a WeChat connection',
 'Expected managed key=value: {v0}': 'Expected managed key=value: {v0}',
 'Export outside the connector state directory': 'Export outside the connector state directory',
 'GGUF changed during registration; retry: {v0}': 'GGUF changed during registration; retry: {v0}',
 'GGUF shard must be an existing regular file: {v0}': 'GGUF shard must be an existing regular file: {v0}',
 'HF GGUF checksum mismatch after retry; damaged cache removed: {v0}': 'HF GGUF checksum mismatch after retry; '
                                                                       'damaged cache removed: {v0}',
 'HF GGUF filename must be a relative file path without parent traversal': 'HF GGUF filename must be a relative '
                                                                           'file path without parent traversal',
 'HF cache path was replaced by a symbolic link; remove it before retrying: {v0}': 'HF cache path was replaced by '
                                                                                   'a symbolic link; remove it '
                                                                                   'before retrying: {v0}',
 'HF download failed (curl {v0}); partial retained for retry: {v1}': 'HF download failed (curl {v0}); partial '
                                                                     'retained for retry: {v1}',
 'HF metadata/network error: {v0}': 'HF metadata/network error: {v0}',
 'HF partial cache is a symbolic link; remove it before retrying: {v0}': 'HF partial cache is a symbolic link; '
                                                                         'remove it before retrying: {v0}',
 'HF publisher/repository': 'HF publisher/repository',
 'HF repository has an incomplete GGUF shard set': 'HF repository has an incomplete GGUF shard set',
 'HF repository must be publisher/repository': 'HF repository must be publisher/repository',
 'HF returned an incomplete GGUF file; retry: {v0}': 'HF returned an incomplete GGUF file; retry: {v0}',
 'HF returned invalid GGUF data; retry: {v0}': 'HF returned invalid GGUF data; retry: {v0}',
 'HTTP {v0} from {v1}: {v2}': 'HTTP {v0} from {v1}: {v2}',
 'Install the connector module first': 'Install the connector module first',
 'Install/configure inside a mas container, not on the host': 'Install/configure inside a mas container, not on '
                                                              'the host',
 'Installed backend does not support: {v0}': 'Installed backend does not support: {v0}',
 'Interactive menu requires a terminal; use maa --help for CLI commands': 'Interactive menu requires a terminal; '
                                                                          'use maa --help for CLI commands',
 'Invalid Codex TOML: {v0}': 'Invalid Codex TOML: {v0}',
 'Invalid GGUF array': 'Invalid GGUF array',
 'Invalid GGUF header': 'Invalid GGUF header',
 'Invalid GGUF string length': 'Invalid GGUF string length',
 'Invalid GGUF tensor dimensions': 'Invalid GGUF tensor dimensions',
 'Invalid Ollama model name/tag': 'Invalid Ollama model name/tag',
 'Invalid Telegram bot Token': 'Invalid Telegram bot Token',
 'Invalid WeChat receive cursor': 'Invalid WeChat receive cursor',
 'Invalid WhatsApp creator ID': 'Invalid WhatsApp creator ID',
 'Invalid connection ID': 'Invalid connection ID',
 'Invalid connection fields': 'Invalid connection fields',
 'Invalid connection state': 'Invalid connection state',
 'Invalid connector backup format': 'Invalid connector backup format',
 'Invalid connector configuration version/structure': 'Invalid connector configuration version/structure',
 'Invalid connector counter': 'Invalid connector counter',
 'Invalid connector runtime state': 'Invalid connector runtime state',
 'Invalid connector time': 'Invalid connector time',
 'Invalid connector {v0}': 'Invalid connector {v0}',
 'Invalid credential file': 'Invalid credential file',
 'Invalid language configuration: {v0}': 'Invalid language configuration: {v0}',
 'Invalid message deduplication state': 'Invalid message deduplication state',
 'Invalid or oversized connector backup': 'Invalid or oversized connector backup',
 'Invalid receive cursor': 'Invalid receive cursor',
 'Invalid receive state': 'Invalid receive state',
 'Language must be zh_cn or en_us': 'Language must be zh_cn or en_us',
 'Legacy GGUF shard registration is incomplete; register the first shard again before using it': 'Legacy GGUF '
                                                                                                 'shard '
                                                                                                 'registration is '
                                                                                                 'incomplete; '
                                                                                                 'register the '
                                                                                                 'first shard '
                                                                                                 'again before '
                                                                                                 'using it',
 'Legacy maa.service was modified or belongs to another user; refusing to remove it': 'Legacy maa.service was '
                                                                                      'modified or belongs to '
                                                                                      'another user; refusing to '
                                                                                      'remove it',
 'Local deletion requires --yes': 'Local deletion requires --yes',
 'Local model catalog was modified; refusing to overwrite it': 'Local model catalog was modified; refusing to '
                                                               'overwrite it',
 'MTP is unavailable: model metadata has no supported MTP weights': 'MTP is unavailable: model metadata has no '
                                                                    'supported MTP weights',
 'Model is not registered: {v0}': 'Model is not registered: {v0}',
 'Model path must be a regular GGUF file': 'Model path must be a regular GGUF file',
 'Native API response exceeded 32 MiB': 'Native API response exceeded 32 MiB',
 'Native backend autostart requires systemd inside mas': 'Native backend autostart requires systemd inside mas',
 'Native backend did not report a valid effective context': 'Native backend did not report a valid effective '
                                                            'context',
 'Native backend exited with code {v0}; inspect maa logs': 'Native backend exited with code {v0}; inspect maa '
                                                           'logs',
 'Native backend readiness timed out: {v0}': 'Native backend readiness timed out: {v0}',
 'Native configuration is not owned by this installation: {v0}': 'Native configuration is not owned by this '
                                                                 'installation: {v0}',
 'Native installation completed but model is absent from the native inventory': 'Native installation completed '
                                                                                'but model is absent from the '
                                                                                'native inventory',
 'Native service failed; inspect maa logs': 'Native service failed; inspect maa logs',
 'No private test message received; send the bot a message and retry': 'No private test message received; send '
                                                                       'the bot a message and retry',
 'No saved language and no controlling terminal; use --language zh_cn or --language en_us': 'No saved language '
                                                                                            'and no controlling '
                                                                                            'terminal; use '
                                                                                            '--language zh_cn or '
                                                                                            '--language en_us',
 'No verified context for the current model; run maa start before changing codex-local configuration': 'No '
                                                                                                       'verified '
                                                                                                       'context '
                                                                                                       'for the '
                                                                                                       'current '
                                                                                                       'model; '
                                                                                                       'run maa '
                                                                                                       'start '
                                                                                                       'before '
                                                                                                       'changing '
                                                                                                       'codex-local '
                                                                                                       'configuration',
 'Not a mas-managed container': 'Not a mas-managed container',
 'Not a supported GGUF v2/v3 file: {v0}': 'Not a supported GGUF v2/v3 file: {v0}',
 'Ollama /api/ps did not report a valid context_length': 'Ollama /api/ps did not report a valid context_length',
 'Ollama /api/ps did not report effective context_length': 'Ollama /api/ps did not report effective '
                                                           'context_length',
 'Ollama /api/ps returned an invalid model list': 'Ollama /api/ps returned an invalid model list',
 'Ollama loaded model no longer matches the accepted configuration': 'Ollama loaded model no longer matches the '
                                                                     'accepted configuration',
 'Ollama model tag changed; refresh maa models and select the current model again': 'Ollama model tag changed; '
                                                                                    'refresh maa models and '
                                                                                    'select the current model '
                                                                                    'again',
 'Ollama name:tag': 'Ollama name:tag',
 'Ollama original-configuration backup changed; refusing to overwrite it': 'Ollama original-configuration backup '
                                                                           'changed; refusing to overwrite it',
 'Ollama requires --name; --path optionally imports GGUF': 'Ollama requires --name; --path optionally imports '
                                                           'GGUF',
 'Quantized KV requires Flash Attention; select f16 before disabling it': 'Quantized KV requires Flash Attention; '
                                                                          'select f16 before disabling it',
 'Quantized MTP KV requires Flash Attention; select f16 or follow before disabling it': 'Quantized MTP KV '
                                                                                        'requires Flash '
                                                                                        'Attention; select f16 or '
                                                                                        'follow before disabling '
                                                                                        'it',
 'Refusing symlink in connector installation': 'Refusing symlink in connector installation',
 'Registered GGUF changed, is missing or was replaced; register it again before using it: {v0}': 'Registered GGUF '
                                                                                                 'changed, is '
                                                                                                 'missing or was '
                                                                                                 'replaced; '
                                                                                                 'register it '
                                                                                                 'again before '
                                                                                                 'using it: {v0}',
 'Registered GGUF shard set is incomplete; register it again': 'Registered GGUF shard set is incomplete; register '
                                                               'it again',
 'Run WeChat QR authorization in an interactive terminal': 'Run WeChat QR authorization in an interactive '
                                                           'terminal',
 'Select a local model first': 'Select a local model first',
 'Select the first GGUF shard (-00001-of-....gguf)': 'Select the first GGUF shard (-00001-of-....gguf)',
 'Select the first GGUF shard of a valid shard set (-00001-of-....gguf)': 'Select the first GGUF shard of a valid '
                                                                          'shard set (-00001-of-....gguf)',
 'Selected Ollama model is not loaded (it may have expired); start it again': 'Selected Ollama model is not '
                                                                              'loaded (it may have expired); '
                                                                              'start it again',
 'Start failed: {v0}\n{v1}': 'Start failed: {v0}\n{v1}',
 'Switch failed: {v0}\n{v1}': 'Switch failed: {v0}\n{v1}',
 'Telegram allowed numeric user ID': 'Telegram allowed numeric user ID',
 'Telegram owner must be a numeric user ID': 'Telegram owner must be a numeric user ID',
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
 'Too many connections': 'Too many connections',
 'Truncated GGUF string': 'Truncated GGUF string',
 'Truncated GGUF: {v0}': 'Truncated GGUF: {v0}',
 'Unexpected platform API address': 'Unexpected platform API address',
 'Unknown connector platform': 'Unknown connector platform',
 'Unknown settings: {v0}': 'Unknown settings: {v0}',
 'Unmanaged connector service overrides; remove them explicitly first': 'Unmanaged connector service overrides; '
                                                                        'remove them explicitly first',
 'Unrecognized connector data; refusing broad cleanup': 'Unrecognized connector data; refusing broad cleanup',
 'Unrecognized receive data; refusing cleanup': 'Unrecognized receive data; refusing cleanup',
 'Unsupported GGUF metadata type: {v0}': 'Unsupported GGUF metadata type: {v0}',
 'Unsupported connection setting': 'Unsupported connection setting',
 'Untrusted WeChat API address': 'Untrusted WeChat API address',
 'Use --token-file in noninteractive mode': 'Use --token-file in noninteractive mode',
 'Use an absolute, non-symlink backup path': 'Use an absolute, non-symlink backup path',
 'WeChat QR authorization timed out': 'WeChat QR authorization timed out',
 'WeChat QR expired or blocked; generate a new QR': 'WeChat QR expired or blocked; generate a new QR',
 'WeChat QR response incomplete': 'WeChat QR response incomplete',
 'WeChat authorization response incomplete': 'WeChat authorization response incomplete',
 'WeChat reports an existing binding; retain existing credentials or generate a fresh authorization': 'WeChat '
                                                                                                      'reports an '
                                                                                                      'existing '
                                                                                                      'binding; '
                                                                                                      'retain '
                                                                                                      'existing '
                                                                                                      'credentials '
                                                                                                      'or '
                                                                                                      'generate a '
                                                                                                      'fresh '
                                                                                                      'authorization',
 'WeChat requires the QR-authorized user ID': 'WeChat requires the QR-authorized user ID',
 'apply current model settings immediately': 'apply current model settings immediately',
 'argument %s: %s': 'argument %s: %s',
 'basic Telegram/WhatsApp/WeChat connectors; no Codex integration': 'basic Telegram/WhatsApp/WeChat connectors; '
                                                                    'no Codex integration',
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
 'llama.cpp /props did not report a valid per-slot context': 'llama.cpp /props did not report a valid per-slot '
                                                             'context',
 'llama.cpp /props returned invalid metadata': 'llama.cpp /props returned invalid metadata',
 'llama.cpp did not report effective per-slot n_ctx': 'llama.cpp did not report effective per-slot n_ctx',
 'llama.cpp requires either --path, or both --repo and --file': 'llama.cpp requires either --path, or both --repo '
                                                                'and --file',
 'local GGUF path': 'local GGUF path',
 'maa-local.config.toml already exists and is not owned by maa; refusing to overwrite it': 'maa-local.config.toml '
                                                                                           'already exists and is '
                                                                                           'not owned by maa; '
                                                                                           'refusing to overwrite '
                                                                                           'it',
 'model key returned by maa models/add': 'model key returned by maa models/add',
 'my-ai-agent: manage local models and codex-local inside mas': 'my-ai-agent: manage local models and codex-local '
                                                                'inside mas',
 'official QR login; add or renew existing connection': 'official QR login; add or renew existing connection',
 'options': 'options',
 'positional arguments': 'positional arguments',
 'private JSON backup containing credentials': 'private JSON backup containing credentials',
 'private credential file; otherwise prompt without echo': 'private credential file; otherwise prompt without '
                                                           'echo',
 'receive one Telegram private message and display candidate user ID': 'receive one Telegram private message and '
                                                                       'display candidate user ID',
 'refresh native Ollama / list registered llama.cpp models': 'refresh native Ollama / list registered llama.cpp '
                                                             'models',
 'renew an existing WeChat connection': 'renew an existing WeChat connection',
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
 '修改聊天接入配置': 'Update connection configuration',
 '停止原底座': 'Stop previous backend',
 '准备 Ollama 模型配置': 'Prepare Ollama model configuration',
 '准备底座服务': 'Prepare backend service',
 '准备模型管理服务': 'Prepare model management service',
 '切换失败，恢复原目标': 'Switch failed; restore previous target',
 '删除本地聊天接入': 'Delete local connection',
 '加载 Ollama 模型': 'Load Ollama model',
 '卸载聊天连接器': 'Uninstall chat connectors',
 '同步 Codex 本地配置和模型目录': 'Synchronize Codex local configuration and model catalog',
 '启动原生底座': 'Start native backend',
 '启动失败，恢复原暂停状态': 'Start failed; restore previous paused state',
 '启动已保存的原生底座配置': 'Start saved native backend configuration',
 '启动当前模型': 'Start current model',
 '唤醒 llama.cpp 模型': 'Wake llama.cpp model',
 '安装 / 登记模型': 'Install / register model',
 '安装底座 / Codex CLI': 'Install backends / Codex CLI',
 '安装聊天连接器': 'Install chat connectors',
 '官方安装：{v0}': 'Official install: {v0}',
 '官方安装：{v0} — {v1}\n': 'Official install: {v0} — {v1}\n',
 '导入聊天接入': 'Import connections',
 '导出聊天接入': 'Export connections',
 '应用模型配置': 'Apply model configuration',
 '应用配置': 'Apply configuration',
 '当前模型已运行；复用现有底座': 'Current model is running; reuse existing backend',
 '微信需要配对码。\n': 'WeChat requires a pairing code.\n',
 '恢复原底座和模型': 'Restore previous backend and model',
 '恢复已提交目标并重新核验原生配置': 'Restore committed target and revalidate native configuration',
 '执行 Ollama 原生下载 / 导入': 'Run native Ollama download / import',
 '暂停当前模型': 'Pause current model',
 '更新 Codex 全局 YOLO 设置': 'Update Codex global YOLO settings',
 '更新已安装的聊天连接器': 'Update installed chat connectors',
 '核对 Hugging Face 仓库和精确文件': 'Check Hugging Face repository and exact file',
 '添加聊天接入': 'Add connection',
 '移除旧 maa 常驻服务': 'Remove legacy maa daemon',
 '等待 Telegram 私聊测试消息': 'Wait for a Telegram private test message',
 '等待原生底座和模型加载；原生日志：maa logs': 'Wait for native backend and model loading; native logs: maa logs',
 '等待微信扫码授权': 'Wait for WeChat QR authorization',
 '获取微信授权二维码': 'Obtain WeChat authorization QR code',
 '读取 GGUF 元数据和计算模型身份': 'Read GGUF metadata and compute model identity',
 '读取 Ollama 原生模型清单': 'Read native Ollama model inventory',
 '读取本地模型清单': 'Read local model inventory',
 '配置未变化；保留当前运行状态': 'Configuration unchanged; retain current runtime state',
 '重新下载校验失败的 GGUF 缓存：{v0}': 'Redownload GGUF cache that failed verification: {v0}',
 '验证 Telegram 接入凭证': 'Validate Telegram connection credential',
 'Language configuration must not be a symbolic link: {v0}': 'Language configuration must not be a symbolic link: '
                                                             '{v0}',
 'Connection stopped': 'Connection stopped',
 'Platform response exceeds size limit': 'Platform response exceeds size limit',
 'Platform returned invalid JSON': 'Platform returned invalid JSON',
 'Platform HTTP {v0}': 'Platform HTTP {v0}',
 'Unexpected platform response': 'Unexpected platform response',
 'Platform network request failed': 'Platform network request failed',
 'Telegram rejected API request': 'Telegram rejected API request',
 'Telegram bot identity unavailable': 'Telegram bot identity unavailable',
 'Telegram webhook information unavailable': 'Telegram webhook information unavailable',
 'This Telegram bot already uses a webhook; use a separate bot or remove its webhook explicitly': 'This Telegram '
                                                                                                  'bot already '
                                                                                                  'uses a '
                                                                                                  'webhook; use a '
                                                                                                  'separate bot '
                                                                                                  'or remove its '
                                                                                                  'webhook '
                                                                                                  'explicitly',
 'Invalid Telegram update list': 'Invalid Telegram update list',
 'WeChat authorization expired; authorize again': 'WeChat authorization expired; authorize again',
 'WeChat rejected API request': 'WeChat rejected API request',
 'WeChat reply context token unavailable': 'WeChat reply context token unavailable',
 'Cannot read native unit state': 'Cannot read native unit state'}
