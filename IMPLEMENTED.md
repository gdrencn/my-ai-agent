# my-ai-agent 0.1.11 implementation

## Verified scope

Restored every 0.1.9 native functional acceptance step to the normal paired test entry. Real HF GGUF and Ollama downloads, model loading/switching, native streaming/nonstreaming Responses, function calls and replay, actual codex-local conversations, manager-independent execution, real PTY model selection, GPU allocation assertions, lifecycle reuse, interrupted candidate recovery, invalid-load rollback, fixture cleanup and reinstall all execute again. No observation-only check substitutes for a functional check.

YOLO enable/disable/restoration still execute. Their state is read exclusively through native Codex initialize/initialized/config/read. Writes use a private CODEX_HOME; user permission/recovery bytes and file modes are verified unchanged. Fixed Agent shell/result replay remains a separate protocol test. Private client homes do not copy user credentials, instructions or global configurations. End/failure/interrupt cleanup removes private homes and the invalid-model fixture. Downloaded test models remain installed and the final test target is paused, matching the baseline contract.

All 0.1.10 installed observations remain. The original installed-version check also retains the stronger installed archive hash, entry and paired version verification. Frozen coverage inventories and CI/source/package checks reject missing baseline tests. Each native report lists all 35 original check IDs, missing IDs and additions.

## Validation

118 source portable/real-PTY tests, the identical 118 packaged tests outside the checkout, and 13 delivery tests passed. All 90 portable and 10 delivery baseline IDs remain; all 0.1.10 additions remain. Five new portable regressions guard restored native coverage, Agent-state comparison, private permission restoration and interrupted cleanup. See [the full correspondence](docs/TEST_COVERAGE.md) and [machine-readable inventory](validation/V0_1_11_COVERAGE.json).

Ordinary-user preliminary functional acceptance passed all 42 checks. Root acceptance on the frozen payloads passed all 42 checks, including original NVIDIA GPU model/KV/compute and driver-memory assertions for both backends. The preliminary ordinary-user tester is identified separately in the local receipt; final-byte public ordinary-user acceptance is pending. Actual upstream programs: Codex 0.165.0, llama.cpp app b11941, Ollama 0.40.12. Native autostart after reboot and launcher operation were also verified with the installed manager archive removed and then restored.

An additional real CPU-only llama.cpp load passed model/KV/compute host-buffer assertions; GPU is explicitly recorded unavailable, not accepted from CPU data. The official native installer reprobed CPU after test hardware changed.

Python 3.11 grammar, shell syntax, deterministic builds, product/test package boundaries and absence of runtime environment-provider coupling passed. The runtime Maa product differs from 0.1.10 only in version; model/service/configuration behavior is unchanged. Independent Linux dependency handling, configurable native HOST, bilingual Options menu and first-install-only YOLO remain. No IM/Web payload is included. Shared global development and interaction guidelines are unchanged.

Release/public acceptance remains pending until published receipts are added. Stable 0.1.9 and all delivered test releases stay immutable. External-machine user acceptance, non-apt native distribution acceptance, large-model and MTP performance are not claimed by these fixtures.

Local evidence: [V0_1_11_LOCAL.json](validation/V0_1_11_LOCAL.json), [root native report](validation/V0_1_11_ROOT_NATIVE.json), [CPU allocation report](validation/V0_1_11_CPU.json).
