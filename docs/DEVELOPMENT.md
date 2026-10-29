# Development and publication

The current requirements are in REQUIREMENTS.md and docs/INDEPENDENCE.md. Product and tests are self-contained Linux code: no sibling checkout, instance marker, container-manager command or outer-environment configuration. The immutable baseline is stable/0.1.9. The 0.1.13 tree excludes IM and Web.

## Shared modules

- environment: Linux/systemd prerequisites, dependency detection, one native package command table.
- install: language selection, dependency preparation, owned installation transaction and official component installers.
- manager/service: model transactions, native units, pause/start, ownership checks and rollback.
- models/gguf/backends/telemetry: model inventory/download, native arguments and read-only observations.
- codex/agent_status: lossless YOLO/profile configuration, independent launcher and bounded native configuration query without Agent turns.
- preferences/i18n/locales/menu/text/output/ui: shared bilingual presentation and terminal handling.
- bootstrap: verified version/channel asset pairing. Old frozen products retain their own historical installer contract.

The build generates shell entries from scripts/entry.template.sh and environment.PACKAGE_MANAGERS. Shell bootstrap only prepares tools needed to run the verified Python installer. Product dependency checks prepare operation-specific tools and CA certificates. Never infer a capability from the operating environment's origin. systemd availability includes a live manager query; command existence alone is insufficient.

## Checks

```bash
python3 scripts/build.py
python3 scripts/test_bootstrap.py
python3 -m unittest discover -v -b
cd /tmp
python3 -I /absolute/project/dist/maa-test.pyz --unit --product /absolute/project/dist/maa.pyz
```

Portable tests isolate MAA_HOME, CODEX_HOME, XDG_CONFIG_HOME and command/service fixtures. No portable test invokes an actual package installer. The paired --native path runs installed observations first, then every 0.1.9 functional acceptance check. Its full contract is documented in README.md. Test components must be installed; --components none is not a reduced test mode.

Permission-write checks use private CODEX_HOME and read Agent config/read responses. Agent tools and fixed shell-result replay test the protocol and remain separate coverage. Neither confirms a YOLO state from command execution. Client homes contain only test settings/catalogs, never user credentials or instructions. User permission/recovery files must remain byte/mode identical.

The frozen inventory in test/coverage.py contains all 90 portable, 10 delivery and 35 native baseline IDs, plus every 0.1.10 addition. Native acceptance fails if any required check is missing. scripts/check_coverage.py writes the source correspondence. Test newly installed software and upgrades in prepared ordinary Linux identities with GPU and root coverage. CPU-only runtime explicitly records GPU unavailability and exercises real host buffers instead. No test assumes a container technology or preinstalled image.
Build twice and compare artifacts. Check Python 3.11 grammar, shell syntax, package/import boundaries, catalogs and manifests. Source-only UI provenance and historical validation receipts describe code origin and past evidence, not runtime prerequisites. Shared development/interaction guidelines are unchanged.

## Release

0.1.13 test uses tag v0.1.13 and an immutable prerelease. Generated test entries pin its version, because frozen 0.2.x experimental releases also exist. Explicit --version overrides are supported. Default numeric discovery remains available to historical bootstraps.

After verified source/docs reach main and CI passes, publish paired maa.pyz, maa-test.pyz, VERSION.json, bootstrap.py, install.sh and SHA256SUMS. Include validation receipts and their checksum. Download public assets again, compare bytes and run the public entry. Additional fixes after handing the user a test command need a new version. Stable requires user acceptance and must preserve the approved product/test bytes. Do not replace existing releases, tags or assets. New deployments cannot assume old frozen products support their environment.
