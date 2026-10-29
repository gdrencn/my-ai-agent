# 0.1.13 coverage compared with 0.1.9

Every baseline functional check is present in the default paired test entry. Version 0.1.10 additions remain. Test identities and permission writes are isolated; no environment-origin requirement is restored.

| Suite | 0.1.9 | 0.1.13 | Missing |
| --- | ---: | ---: | ---: |
| Portable / real PTY | 90 | 128 | 0 |
| Delivery | 10 | 13 | 0 |
| Installed functional acceptance | 35 | 42 | 0 |

The machine-readable correspondence is [V0_1_13_COVERAGE.json](../validation/V0_1_13_COVERAGE.json). The runtime report requires each native ID to pass, not merely exist in source. Local and public execution receipts establish execution; the inventory alone does not.

## Original native checks

| # | Original ID retained | Verification |
| --- | --- | --- |
| 1 | `installed-version` | Installed archive SHA-256, installed command and paired product version must match. |
| 2 | `explicit-yolo-test-baseline` | Actual enable/disable/reinstall; Agent `config/read`, private off-state checks plus real-home reinstall, restore original fields. |
| 3 | `hf-exact-download` | Register/download the exact HF repository and GGUF file; validate the managed artifact. |
| 4 | `ollama-native-pull` | Use the actual Ollama pull and register the resulting native model. |
| 5 | `hf-invalid-file-rejected` | Reject a missing exact HF filename instead of accepting a model. |
| 6 | `llamacpp-select` | Actually load/switch the backend and model with the requested context, KV and keep-alive settings. |
| 7 | `llamacpp-catalog` | Single-model catalog uses the original model name and actual native effective context. |
| 8 | `llamacpp-responses` | Real nonstreaming and SSE replies from the selected native backend. |
| 9 | `llamacpp-native-function-call` | Native function arguments and tool-result replay against the model. |
| 10 | `llamacpp-codex-cli` | Actual `codex-local exec` conversation, clean parent PATH, warning assertions. |
| 11 | `llamacpp-manager-independent` | Remove manager archive temporarily, run an actual local Codex conversation. |
| 12 | `llamacpp-model-status` | Real current-load model/KV/compute allocations; original GPU assertions when GPU is present; CPU assertions added. |
| 13 | `llamacpp-configuration-without-reload` | Reasoning/YOLO/list/start preserve PID and invocation; paused editing does not wake model. |
| 14 | `llamacpp-codex-model-picker` | Real Codex PTY `/model`, original model name only, clean exit and terminal restoration. |
| 15 | `ollama-select` | Actually load/switch the backend and model with the requested context, KV and keep-alive settings. |
| 16 | `ollama-catalog` | Single-model catalog uses the original model name and actual native effective context. |
| 17 | `ollama-responses` | Real nonstreaming and SSE replies from the selected native backend. |
| 18 | `ollama-native-function-call` | Native function arguments and tool-result replay against the model. |
| 19 | `ollama-codex-cli` | Actual `codex-local exec` conversation, clean parent PATH, warning assertions. |
| 20 | `ollama-manager-independent` | Remove manager archive temporarily, run an actual local Codex conversation. |
| 21 | `ollama-model-status` | Real current-load model/KV/compute allocations; original GPU assertions when GPU is present; CPU assertions added. |
| 22 | `ollama-configuration-without-reload` | Reasoning/YOLO/list/start preserve PID and invocation; paused editing does not wake model. |
| 23 | `ollama-codex-model-picker` | Real Codex PTY `/model`, original model name only, clean exit and terminal restoration. |
| 24 | `ollama-resident-entry-reuses-alias` | Run real Codex against a resident model; native tag digest and modification time remain unchanged. |
| 25 | `ollama-expired-entry-wakes-existing-alias` | Explicitly unload, confirm read-only status does not wake it, then actual Codex wakes the existing unchanged native tag. |
| 26 | `ollama-explicit-start-wakes-without-restart` | Explicit start wakes an idle model without changing native PID, invocation or catalog. |
| 27 | `ollama-unchanged-inventory-reuses-registry` | Repeated real model inventories preserve registry bytes/mtime and native process identity. |
| 28 | `codex-direct-shell-and-result-replay` | Actual Codex executes a fixed shell fixture, creates its proof file, and replays the tool output; freeform tools remain absent. |
| 29 | `pause-start-retains-target` | Pause preserves selection and hides old allocations; start resumes the same selected model. |
| 30 | `interrupted-candidate-restores-accepted-native-target` | Inject uncommitted target/pending state; actual start restores the accepted target, clears pending state and keeps the candidate inactive. |
| 31 | `native-load-failure-rollback` | A real weightless GGUF reaches native loading, fails and rolls back to the accepted running Ollama model. |
| 32 | `invalid-fixture-cleaned` | The failed-load model is removed from the registry/configuration and its temporary directory is cleaned. |
| 33 | `yolo-off` | Actual enable/disable/reinstall; Agent `config/read`, private off-state checks plus real-home reinstall, restore original fields. |
| 34 | `product-reinstall-retains-yolo-off-and-native-instance` | Actual enable/disable/reinstall; Agent `config/read`, private off-state checks plus real-home reinstall, restore original fields. |
| 35 | `yolo-on` | Actual enable/disable/reinstall; Agent `config/read`, private off-state checks plus real-home reinstall, restore original fields. |

## Added native checks

`linux-prerequisites`, `current-model-state`, `independent-launcher`, `codex-version`, `agent-permission-state`, `configuration-retained` retain the 0.1.10 observations. `installed-version` also retains the 0.1.10 installed hash/entry/version pairing enhancements. `user-permissions-retained` adds byte/mode comparison of the invoking user's permission and recovery files.

## Permission-state method

YOLO is not inferred from shell success or a confirmation prompt. On/off and recovery still execute; their state comes from native Agent configuration responses. The real Codex fixed-shell fixture tests function declarations, command execution and output replay as before; it is protocol coverage, not permission-state coverage. The fixture does not read user input, credentials or instructions. All test client and permission homes are removed after use.

## Portable and delivery additions

Every 0.1.12 test remains. The 0.1.10 language, environment, independence and options-menu checks remain. Six new regressions protect discovery of every baseline/previous portable ID, Agent-state disagreement, enable/restore semantics through state reads, interrupted cleanup and rejection of incomplete native coverage, and exact reuse of the written profile/catalog without regeneration. The delivery version-pin fixture now reads the actual product version rather than hardcoding a previous version.

The former deployment-identity gate is not restored. Actual Linux/systemd/dependency checks replace it, as explicitly requested; model and Codex functional acceptance does not depend on where Linux was created. No GPU/MTP hardware claim is derived from a portable fixture.

Current 0.1.13 execution receipts are added after validation. Nine additional process-lifecycle regressions cover successful/nonzero exits with surviving writers, timeout output, checked failure output, interruption with unrelated-session survival, unavailable optional pidfd syscalls, native configuration-reader cleanup, real SIGINT exit 130, normal PTY restoration and early PTY exit. None replaces a baseline test.
