# my-ai-agent 0.1.10 requirements

The current release follows [the independence contract](docs/INDEPENDENCE.md). The 0.1.9 model, Codex, native-service, rollback and terminal requirements remain applicable except for environment identity restrictions and destructive native acceptance. Their original text is preserved in [the baseline requirements](docs/history/0.1.9/REQUIREMENTS.md).

1. Support qualifying Linux installations without identifying a container provider or host/container role.
2. Check Linux, Python 3.11+, actual systemd availability and required software. Prepare missing supported packages through a shared dependency implementation. Do not assume preinstalled tools or auto-configure an outer environment.
3. Preserve model defaults, per-model settings, HOST configurability, ownership guards, rollback, independent codex-local and first-install-only YOLO behavior.
4. Ship no IM runtime, IM menu, Web runtime or dependency on another project.
5. Preserve Chinese/English selection and saved preferences. Put language and version/about in one Options submenu.
6. Default installed checks are read-only: observe version, capabilities, current native service and Agent effective configuration; never force YOLO, run Agent tools, change the selected target or download test models.
7. Use private fixtures for configuration, command-output and service transaction regression checks, without virtualization assumptions. Never copy real credentials into test fixtures or reports.
8. Pin the public test entry to 0.1.10; retain explicit version overrides and immutable previous releases. Publish a paired test release after verification; stable remains unchanged.
9. Audit source imports, hardcoded paths, external commands, package content, documentation, dependency failures and public artifacts. Record completed checks separately from pending external-machine acceptance.
