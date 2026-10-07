# Development and test publication

Python 3.11+, Linux/systemd inside mas. Product has only standard-library runtime plus pinned vendored tomlkit 0.13.3, including its license and provenance. Native installers and models are external dependencies.

## Source map

| Module | Responsibility |
| --- | --- |
| store | atomic JSON, ownership identities, process locking |
| settings | shared validated defaults/options |
| models / gguf | native inventory/import, pinned exact HF downloads, bounded GGUF metadata |
| backends | native arguments/environment/capability checks and observation |
| telemetry | bounded current-load allocation logs, GPU driver observations and no conversation interception |
| service | one-shot native unit configuration, readiness and rollback |
| manager | shared transactions, rollback, pause/resume, maintenance; no runtime local launch |
| codex | lossless two-key global edits/recovery, dedicated local profile and immutable local model catalogs |
| menu / text / output / i18n / ui | inline terminal controls, Chinese catalog and business menu |
| cli / install | public commands, container guard and official installation |
| bootstrap | numeric prerelease discovery and checksummed version pairing |

## Lifecycle trigger audit (0.1.8)

| Entry | Native lifecycle behavior |
| --- | --- |
| YOLO on/off; install/update Codex CLI | Edit/install Codex only; no backend stop, start, wake or reload; CLI, menu and product installer share this rule |
| Configure reasoning only | Transactional profile/per-model state update using accepted context; preserve running/paused state |
| Apply unchanged settings | No lifecycle operation |
| Select another backend/model; change a backend key | Full stop/prepare/start/verify/commit transaction with rollback |
| Select the current unchanged target; maa start | Reuse resident instance, wake idle model, or start verified saved units from pause |
| Missing/changed/unverified native configuration or interrupted pending target | Full revalidation on explicit start/select using the accepted selection; unit/preload file hashes guard saved-unit reuse |
| Pull/create the selected Ollama public tag | No automatic switch; invalidate native-configuration reuse because native model parameters may change |
| Update the active backend or install all components | Maintenance stop/install/start/verify, synchronize actual context; preserve previous paused state |
| Install an inactive backend | Ownership preflight plus official installer; retain the current model |
| Upgrade maa with --components none | Replace owned management entrypoints only; retain native instance and profile |
| Ollama inventory on owned running Ollama | Read tags/show directly; never unload or reload |
| Ollama model operation without a running owned Ollama | Exclusive temporary native service with previous target restored if it was running |
| HF download/local GGUF scan | Outside control.lock; per-target download lock, then brief registration lock |
| Native pull/create on owned running Ollama | Outside control.lock; backend download lock; an explicit pause/switch may interrupt transfer, never restore a stale selection |
| Main-menu summary | Native read-only state/context only; skip allocations and GPU memory |
| Full status/logs/codex-local | Read-only observations or direct native client execution; no maa-triggered reload |

Ctrl+C restores the previous target/state and retains KeyboardInterrupt/130. Paused saved-unit startup failures restore the paused state. Interrupted transfer and restore failures retain accurate diagnostics. Forced termination remains outside normal rollback guarantees.

Native startup always receives an explicit target: only an active selection transaction passes a candidate. Readiness never consumes a saved Ollama context as evidence of current residency. Maintenance recovery includes the initial stop and retains interrupt identity if restoration also fails.

Maintenance revalidates an interrupted candidate using the accepted target and re-enables accepted autostart after successful recovery from an official backend update.

Product installation validates entrypoint/native ownership and both Codex TOML files before replacing files. Entry-writing failure restores the previous archive/commands/modes and initial Codex edits; migration and official component installation happen after entry commit. First product installation enables YOLO, while later product/Codex updates retain current settings and recovery bytes. Existing legacy state counts as an upgrade. Official dependency installers are external and their own modifications are not rolled back.

Ollama inventory caches registered metadata by native/original digest, recognizes tracked configured manifests, batches changed rows once and avoids unchanged writes. A newly installed target query ignores unrelated details. Model choice details preserve full HF paths/revisions and local paths; collision labels include enough source information to distinguish them.

GGUF records contain the entire shard set (path, file identity, SHA-256). Verify all identities before lifecycle mutation. Legacy split records without full identities require registration again. HF requests file metadata (`blobs=true`), pins the repository commit, checks size and available LFS SHA-256, and retries only damaged cached shards once. The API's file-metadata behavior is documented in the [official HfApi reference](https://huggingface.co/docs/huggingface_hub/en/package_reference/hf_api#huggingface_hub.HfApi.model_info). Cached symlinks outside the target directory are refused.

Readonly option activation is handled inside Screen.choose rather than rebuilding the business menu. Model picker defaults follow the current backend/key; focus details show filename/source with wrapped text. Unavailable request counters are consolidated only in menu output; CLI null fields remain stable. Passed test output is buffered; failed diagnostics are retained. The real Codex tool fixture returns its complete details to the native JSON report and prints JSON only when run standalone.

## Commands

```bash
python3 scripts/build.py
python3 -m unittest discover -v -b
cd /tmp
python3 -I /absolute/project/dist/maa-test.pyz --unit --product /absolute/project/dist/maa.pyz
```

Build twice and compare bytes. Check Python 3.11 grammar, shell syntax, package boundaries and manifests. Product excludes test/documentation/validation payloads; tester includes only needed tests and native runner. Tests use private MAA_HOME and CODEX_HOME. PTY tests use real controlling terminals.

Native tests must be inside an owned disposable mas container; install product, official tools and run test/native.py or paired tester --native. Record software versions, frozen program hash, exact passed checks, cleanup and evidence limitations. Restart the container separately to verify autostart of the selected target after pause. Run as the ordinary sandbox user as well as root when installation/unit behavior changes.

The paired tester includes test/codex_ui.py and drives the real Codex `/model` picker for both backends. Check original display names, exact native names, effective context and absence of embedded-fallback/metadata warnings. Verify resident Ollama entry and forced idle unload/wake without changing native tag digest or modification time. The invalid GGUF fixture must be unregistered and its failed configuration removed even when a check raises; legacy cleanup recognizes only the exact old fixture signature. test/codex_tool.py separately verifies real shell execution/replay with a deterministic upstream fixture; it does not measure model competence.

Status uses separate observers: Ollama `/api/ps`, llama.cpp `/props`; never use inference or `/slots` in the status path. Native initialization logs are bounded to 4 MiB, checked against file identity and launch offset, then reset at each real tensor load. Discard no_alloc fit probes and stale retries. Buffer records replace matching phase/component/backend/kind entries; classify CPU_Mapped as mappings and CUDA_Host as host allocations. Freeze phase attribution at the native model-loaded marker. A missing load boundary, replaced/truncated log or missing field stays unknown. MTP and RS fixtures must not be described as native model acceptance. Driver free memory is reported directly, not derived from total minus used.

Direct mode has no usage recorder. Old usage.json must not influence status; unavailable token counts remain null. Real backend checks verify native allocations, whole-GPU observations, read-only status and unloaded/paused behavior. PTY checks cover grouped navigation, colored values, pending changes, readonly fields, YOLO recovery, narrow terminals and NO_COLOR.

Native backend units run only official backend executables and native curl preload. No maa service, proxy, thread or Python process remains after a management command exits. Test removal of the installed archive while running Codex and restarting the container. Candidate validation disables autostart until acceptance; interrupted management must not boot a candidate. Normal failures restore native files, enablement, original Ollama tag, profile and previous running/paused state. A forcibly killed transaction may require maa start to revalidate the saved target.

Progress and terminal-facing command output belong on stderr. output.run owns command/output coordination: ordinary commands buffer actual diagnostics while the timer remains alive; native installers and downloads stream through a PTY when attached to a terminal and through a pipe otherwise. Explicitly captured/redirected streams keep their subprocess contract. Fully captured native help, unit-state and driver queries have no terminal output to coordinate. privileged only adds sudo and calls output.run; business callers do not add terminal gaps or suspend timers. diagnostic uses the same writer for owned notices. Actual output erases the active progress row without committing it; the writer tracks split UTF-8 and split terminal controls and adds a line ending only when necessary. Its reader finishes before the management command returns; no runtime service is added.

Real PTY checks replay the terminal controls and assert retained rows, including consecutive silent commands, slow-command timer refresh, diagnostics, native output with/without a final newline, interruption and return to a menu. Nonterminal checks require parseable stdout JSON, no progress ANSI and no repeated timer ticks. Additional installed-command PTY checks cover both backend switches, same-backend configuration, pause, official Codex installation, Ollama pull and HF curl download. The 0.1.8 tests checked control sequences and a permissive newline bound but missed repeated silent-command handoffs; those checks did not establish correct retained terminal rows.

`codex-local` explicitly uses the official `--no-daemon` option; do not hide native diagnostics. Catalogs use content-addressed immutable files so restoring a profile also restores its prior model/context metadata. Do not copy a developer's global Codex model cache or instructions into generated metadata.

The independent launcher must find the official ~/.local/bin/codex immediately after installation without relying on .bashrc or inherited user PATH. Test it with a space-containing HOME and an environment that has only system binary directories; verify argument forwarding and exec PID with the installed manager absent. Each real native codex-local greeting check also uses a PATH without the user bin directory. Run fresh official installation and paired tests in one non-login process with that same baseline PATH.

## Artifacts and release

Build produces maa.pyz, maa-test.pyz, VERSION.json, bootstrap.py, install.sh and SHA256SUMS. Numeric version lives only in maa/__init__.py. VERSION.json pairs the test channel/version; SHA256SUMS covers the other five payloads. Test publication can add frozen validation JSON and its checksum. The repository validation manifest covers all checked-in receipts; the release validation manifest covers that version's initial local/native receipts. Public evidence is appended with a separate PUBLIC_SHA256SUMS; never overwrite a released manifest.

Commit verified source/docs to main, tag v0.1.9, publish GitHub prerelease. Never replace an existing tag/release/asset. Download every asset again and verify local byte equality, manifest and the public installer. Changes after freeze require a new version unless they only record validation/documentation and do not alter frozen payloads. Stable promotion needs user acceptance.

The official upstream installers resolve their own current versions; do not claim their future releases are identical to the versions in our validation receipt. Models are pinned to HF commits or native Ollama digests after download.
