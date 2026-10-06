# my-ai-agent Implementation — 0.1.1 test

Verified on 2026-10-06 against REQUIREMENTS.md. Product version: 0.1.1. Test release is authorized; stable promotion requires user acceptance.

## Completed behavior

| Requirement | Implementation and verification |
| --- | --- |
| Install inside mas | Instance management marker checked through devlxd; ordinary user uses sudo only for the root-only marker read and system installation. Official Ollama, llama.cpp and Codex installers executed in separate disposable mas containers. Host Codex and mas source are untouched. |
| Menu and CLI | Shared Manager/settings operations; mas-derived inline Screen. Install, register, select, configure, pause, start, YOLO, status and About actions; CLI help/version/JSON/errors. First selection opens defaults before loading; cancellation preserves the previous target. |
| Models | Native Ollama pull/import/inventory; exact HF repository/file download pinned to commit, split GGUF handling, local GGUF registration, cached files. Wrong input and native errors remain visible. No online search or Safetensors conversion. |
| Durable identity | Backend plus Ollama digest, HF commit/file or local file SHA-256. Config saved for each identity; registered local file replacement refused before service changes. |
| Shared settings | Context 262144, q8_0 main KV, Flash Attention on, fit on, reserve 0, keep-alive 5m, supported MTP on, draft KV follow, reasoning default omitted. CLI and menu use one validated schema; choices and integer inputs match requirements. Quantized KV requires Flash Attention. |
| Native configuration | Model sampling/template and unmanaged native defaults preserved. No GPU placement or MTP candidate-length menu. llama.cpp has one inference slot; supported candidate defaults and draft KV are mapped per backend. Native help/model metadata checks refuse unsupported combinations. |
| Switching and recovery | Stop previous service, load candidate, observe effective context, write local Codex profile, commit configuration and boot selection. Failures restore selection/profile/configuration and report service recovery. Actual native load failure tested. Interrupted transactions cannot become accepted boot targets. |
| Lifetime | One owned systemd maa.service runs one native backend and the adapter. Official Ollama daemon stopped/disabled. Pause retains selection; restart of the container starts the saved target. Both root/Ollama and ordinary-user/llama.cpp boot paths tested. |
| Runtime truth | Ollama /api/ps and llama.cpp /props report effective context. llama.cpp completes a minimum inference before selection acceptance. Resource information comes from native metadata/current launch logs; unavailable GPU layer counts remain unknown, never inferred from previous logs. |
| Global YOLO | Only approval_policy and sandbox_mode changed. First write saves existence and original TOML values; repeat-on retains backup; off restores/deletes those keys. Unrelated comments, multiline strings, date values and later edits preserved. CODEX_HOME respected. |
| codex-local | Dedicated maa-local.config.toml profile, actual selected model/endpoint/context, Responses API, no OpenAI auth. Auto-compaction is floor(effective context × 90%). Reasoning values passed unchanged; no permission flags or web_search configuration written. Model/provider rerouting overrides rejected. |
| Responses compatibility | Local stateless bridge covers text/reasoning streaming, ordinary/namespace/custom function declarations and call results, replay, usage and errors. Real Codex namespace shell tool execution verified with a deterministic native-response fixture. |
| Search | No hosted Web Search implementation. Codex's default hosted-search declaration is omitted from native tool declarations; runtime reports hosted_web_search=false. Existing MCP functions preserved. Ollama login alone does not provide Codex search integration. |
| Packaging | Deterministic standalone product/test zipapps with pinned tomlkit 0.13.3 and license. Product excludes tests, reports and project documentation. Bootstrap pairs VERSION.json, manifest and assets. |

## Verification evidence

Local receipts: [validation/V0_1_1_LOCAL.json](validation/V0_1_1_LOCAL.json), [validation/V0_1_1_NATIVE.json](validation/V0_1_1_NATIVE.json).

- **Portable:** 25 tests pass from source and from the packaged tester outside the checkout. Includes real HTTP/SSE calls, cross-process TOML recovery, failed switch/crashed transaction cases, settings and model input checks, and three real PTY tests.
- **Product PTY:** a 12 × 40 terminal drives first model configuration, integer editing, cancellation without changing the target, About/version, main-menu exit and terminal restoration. Inline history is retained.
- **Native:** 16 checks pass with official Ollama 0.35.1, llama.cpp b11429 and Codex CLI 0.160.1 as ordinary sandbox user. Covers actual HF/Ollama downloads, both backend selections, text/SSE, model function calls and replay, actual Codex CLI, pause/start, native load failure rollback and YOLO off/on. Root-container native checks also passed during development.
- **Configuration/boot:** actual q4_0/context/keep-alive changes accepted by both backends; switching back restores saved configuration. Frozen product installed and restarted as root and sandbox user; one native process, enabled owned unit, inactive official Ollama daemon, healthy adapter, context and 90% profile synchronization verified.
- **Fault-injected protocol:** real Codex executes a shell command and returns its output through the bridge against a deterministic upstream fixture. This proves protocol/client integration, not small-model coding competence.
- **Build:** Python 3.11 syntax, shell syntax, reproducible bytes, package boundaries, VERSION/manifest and installed archive hashes checked.

The ordinary-user official llama.cpp installer selected its CUDA build. Ollama reported size_vram equal to size for the tested small model; this is not evidence that larger models or the default 262144 context fit entirely in GPU memory. llama.cpp's default native log verbosity does not always expose layer counts, so that field can remain null.

Both tested Qwen3 0.6B models lack MTP weights. MTP detection, follow/override logic and supported flag construction are checked with metadata fixtures; **native MTP inference, large-model stability and performance have not been accepted**. HF authenticated/restricted repositories, split GGUF downloads and forced process-crash recovery have portable/implementation coverage, not complete native acceptance. Upstream installer versions may change after this receipt.

## Publication stage

Frozen v0.1.1 product/test assets are ready for GitHub prerelease publication. Public asset download and public installer/test entry verification are recorded separately after publication; they are not claimed by the local receipts above. Stable is not published.
