# Development and test publication

Python 3.11+, Linux/systemd inside mas. Product has only standard-library runtime plus pinned vendored tomlkit 0.13.3, including its license and provenance. Native installers and models are external dependencies.

## Source map

| Module | Responsibility |
| --- | --- |
| store | atomic JSON, ownership identities, process locking |
| settings | shared validated defaults/options |
| models / gguf | native inventory/import, pinned exact HF downloads, bounded GGUF metadata |
| backends | native arguments/environment/capability checks and observation |
| service | one systemd unit, accepted boot target, native process and API adapter lifetime |
| manager | shared transactions, rollback, pause/resume, maintenance and local launch |
| codex | lossless two-key global edits/recovery, dedicated local profile and immutable local model catalogs |
| bridge | stateless Responses/chat protocol conversion, namespace/custom tools and SSE |
| menu / text / output / i18n / ui | inline terminal controls, Chinese catalog and business menu |
| cli / install | public commands, container guard and official installation |
| bootstrap | numeric prerelease discovery and checksummed version pairing |

## Verification

```bash
python3 scripts/build.py
python3 -m unittest discover -v
cd /tmp
python3 -I /absolute/project/dist/maa-test.pyz --unit --product /absolute/project/dist/maa.pyz
```

Build twice and compare bytes. Check Python 3.11 grammar, shell syntax, package boundaries and manifests. Product excludes test/documentation/validation payloads; tester includes only needed tests and native runner. Tests use private MAA_HOME and CODEX_HOME. PTY tests use real controlling terminals.

Native tests must be inside an owned disposable mas container; install product, official tools and run test/native.py or paired tester --native. Record software versions, frozen program hash, exact passed checks, cleanup and evidence limitations. Restart the container separately to verify autostart of the selected target after pause. Run as the ordinary sandbox user as well as root when installation/unit behavior changes.

The paired tester includes test/codex_ui.py and drives the real Codex `/model` picker for both backends. Check original display names, exact native aliases, effective context and absence of embedded-fallback/metadata warnings. Verify resident Ollama entry and forced idle unload/wake without changing alias digest or modification time. The invalid GGUF fixture must be unregistered and its failed configuration removed even when a check raises; legacy cleanup recognizes only the exact old fixture signature. test/codex_tool.py separately verifies real shell execution/replay with a deterministic upstream fixture; it does not measure model competence.

Progress belongs on stderr. Real PTY checks cover immediate feedback, one-line phase/timer refresh, native output ownership, failure and cursor restoration. Nonterminal checks require parseable stdout JSON, no ANSI and no repeated timer ticks. `codex-local` explicitly uses the official `--no-daemon` option; do not hide native diagnostics. Catalogs use content-addressed immutable files so restoring a profile also restores its prior model/context metadata. Do not copy a developer's global Codex model cache or instructions into generated metadata.

## Artifacts and release

Build produces maa.pyz, maa-test.pyz, VERSION.json, bootstrap.py, install.sh and SHA256SUMS. Numeric version lives only in maa/__init__.py. VERSION.json pairs the test channel/version; SHA256SUMS covers the other five payloads. Test publication can add frozen validation JSON and its checksum.

Commit verified source/docs to main, tag v0.1.2, publish GitHub prerelease. Never replace an existing tag/release/asset. Download every asset again and verify local byte equality, manifest and the public installer. Changes after freeze require a new version unless they only record validation/documentation and do not alter frozen payloads. Stable promotion needs user acceptance.

The official upstream installers resolve their own current versions; do not claim their future releases are identical to the versions in our validation receipt. Models are pinned to HF commits or native Ollama digests after download.
