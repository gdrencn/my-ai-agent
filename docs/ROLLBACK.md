# Rollback baseline for 0.2 development

The current rollback target is **0.1.9 stable**, tag `stable/0.1.9`, source commit `b3189e95d996cbb36911076e5e90ef9feca39021`. Keep this target fixed while developing and testing 0.2. If another 0.1.x stable is accepted later, verify and record the replacement baseline before changing this target; retain the older release.

The [formal release](https://github.com/gdrencn/my-ai-agent/releases/tag/stable/0.1.9) contains the frozen product, paired tester, version metadata, bootstrap, installer, manifests and validation evidence. Neither the tag nor existing release assets may be replaced or deleted.

## Scope and acceptance

This baseline preserves Maa source and installable release artifacts. It is not a snapshot of a user's container, model weights, credentials, Codex sessions or independently installed software.

During the connector-only phase, preserve the 0.1.x state format and native backend/Codex behavior. Connector credentials, configuration, receive state and autostart resources must have independent ownership and cleanup. Before installing the old product, use the newer manager to stop the connectors and disable their autostart. Downgrading the Maa archive alone cannot remove future connector services that 0.1.9 does not know about. Do not use guessed service names or broad file deletion as a substitute for owned cleanup.

Use `--components none` to restore Maa without invoking upstream installers. This does not downgrade Ollama, llama.cpp or Codex CLI. Keep those independently installed components unchanged during this phase unless a separate restoration plan is approved.

Before publishing a 0.2 test, verify a real upgrade/downgrade cycle in an owned disposable mas container: connector shutdown, old product installation, version, retained model/configuration/YOLO setting, native backend and `codex-local` operation, and container reboot with connectors still stopped. The artifact checks below do not establish that future acceptance test.

## Online installation of the fixed baseline

Run this inside the target mas container as its original Maa installation user, after the newer manager has closed the connector module and disabled connector autostart:

```bash
(
    set -eu
    maa_rollback_dir=$(mktemp -d)
    trap 'rm -rf "$maa_rollback_dir"' EXIT
    curl -fsSL https://github.com/gdrencn/my-ai-agent/releases/download/stable/0.1.9/bootstrap.py \
        -o "$maa_rollback_dir/bootstrap.py"
    cd "$maa_rollback_dir"
    printf '%s  %s\n' \
        12d1cf03fd7836e70d66d94f5e985f6e943697e4af663fb1559678293d035a3c \
        bootstrap.py | sha256sum -c -
    python3 bootstrap.py --channel stable --version 0.1.9 --components none
    "$HOME/.local/bin/maa" --version
)
```

The frozen bootstrap requests the exact stable tag, checks the selected channel/version and validates the downloaded product against its manifest. It does not select `latest`. The old `install.sh`, even when fetched from the old tag/release, still downloads `main/bootstrap.py`; use the pinned bootstrap above for this rollback procedure.

## Offline installation

Copy the verified release assets to the target mas container. In that directory, run as the original installation user after the same connector shutdown:

```bash
(
    set -eu
    printf '%s  %s\n' \
        dc808d6dd31eab98fdd98087cad4c6b9c78ee903d42a9a21b01f1e71938ab801 \
        SHA256SUMS | sha256sum -c -
    sha256sum -c SHA256SUMS
    python3 maa.pyz _install --components none
    "$HOME/.local/bin/maa" --version
)
```

This invokes the same frozen product installation path as bootstrap. It still requires the existing mas container, Python 3.11+, native installation environment and any needed sudo access. It does not reinstall external components or repair hypothetical incompatible future state; preserving that state is a development requirement above.

## Source recovery and local copy

An offline developer copy was prepared at `/home/gordon/my-ai-agent-rollback/0.1.9/`. This machine-specific location is not required by Maa or the installer. It contains all 11 existing release assets, `BASELINE.json`, a `source.bundle` containing the stable tag and its reachable history, and `BACKUP_SHA256SUMS` covering the local backup files. No host global Codex data or user runtime data is included.

Verify a copied directory with `sha256sum -c BACKUP_SHA256SUMS`. Recover a separate source checkout with:

```bash
git clone --branch stable/0.1.9 source.bundle my-ai-agent-0.1.9
```

The tag checkout is detached. Create a new branch there if needed; do not move the original tag or reset a working development checkout to recover it.

## Recorded verification boundary

The baseline preparation downloaded all existing stable release assets, verified GitHub asset digests, all three published checksum manifests and the original stable review hashes, checked the numeric version/channel, compared the remote tag with the preserved source commit, and verified recovery into a separate source checkout. The online/offline commands were checked against the frozen installer contract without installing anything on the host.

The 0.1.9 native installation evidence remains in `validation/STABLE_0_1_9_NATIVE.json` and `validation/STABLE_0_1_9_PUBLIC.json`. A downgrade from an implemented 0.2 version has not yet been tested because that implementation does not yet exist.
