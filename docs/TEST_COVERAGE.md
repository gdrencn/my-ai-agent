# 0.1.11 coverage compared with 0.1.9

Every baseline functional check is present in the default paired test entry. Version 0.1.10 additions remain. Test identities and permission writes are isolated; no environment-origin requirement is restored.

| Suite | 0.1.9 | 0.1.11 | Missing |
| --- | ---: | ---: | ---: |
| Portable / real PTY | 90 | 118 | 0 |
| Delivery | 10 | 13 | 0 |
| Installed functional acceptance | 35 | 42 | 0 |

The machine-readable correspondence is [V0_1_11_COVERAGE.json](../validation/V0_1_11_COVERAGE.json). The runtime report requires each native ID to pass, not merely exist in source. Local and public execution receipts establish execution; the inventory alone does not.

## Original native checks

| # | Original ID retained | Verification |
| --- | --- | --- |
| 1 | `installed-version` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 2 | `explicit-yolo-test-baseline` | Actual enable/disable/reinstall; Agent `config/read`, private `CODEX_HOME`, restore original fields. |
| 3 | `hf-exact-download` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 4 | `ollama-native-pull` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 5 | `hf-invalid-file-rejected` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 6 | `llamacpp-select` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 7 | `llamacpp-catalog` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 8 | `llamacpp-responses` | Real nonstreaming and SSE replies from the selected native backend. |
| 9 | `llamacpp-native-function-call` | Native function arguments and tool-result replay against the model. |
| 10 | `llamacpp-codex-cli` | Actual `codex-local exec` conversation, clean parent PATH, warning assertions. |
| 11 | `llamacpp-manager-independent` | Remove manager archive temporarily, run an actual local Codex conversation. |
| 12 | `llamacpp-model-status` | Real current-load model/KV/compute allocations; original GPU assertions when GPU is present; CPU assertions added. |
| 13 | `llamacpp-configuration-without-reload` | Reasoning/YOLO/list/start preserve PID and invocation; paused editing does not wake model. |
| 14 | `llamacpp-codex-model-picker` | Real Codex PTY `/model`, original model name only, clean exit and terminal restoration. |
| 15 | `ollama-select` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 16 | `ollama-catalog` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 17 | `ollama-responses` | Real nonstreaming and SSE replies from the selected native backend. |
| 18 | `ollama-native-function-call` | Native function arguments and tool-result replay against the model. |
| 19 | `ollama-codex-cli` | Actual `codex-local exec` conversation, clean parent PATH, warning assertions. |
| 20 | `ollama-manager-independent` | Remove manager archive temporarily, run an actual local Codex conversation. |
| 21 | `ollama-model-status` | Real current-load model/KV/compute allocations; original GPU assertions when GPU is present; CPU assertions added. |
| 22 | `ollama-configuration-without-reload` | Reasoning/YOLO/list/start preserve PID and invocation; paused editing does not wake model. |
| 23 | `ollama-codex-model-picker` | Real Codex PTY `/model`, original model name only, clean exit and terminal restoration. |
| 24 | `ollama-resident-entry-reuses-alias` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 25 | `ollama-expired-entry-wakes-existing-alias` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 26 | `ollama-explicit-start-wakes-without-restart` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 27 | `ollama-unchanged-inventory-reuses-registry` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 28 | `codex-direct-shell-and-result-replay` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 29 | `pause-start-retains-target` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 30 | `interrupted-candidate-restores-accepted-native-target` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 31 | `native-load-failure-rollback` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 32 | `invalid-fixture-cleaned` | Original real lifecycle/download/catalog/rollback assertion retained; see the same named step in `test/native.py`. |
| 33 | `yolo-off` | Actual enable/disable/reinstall; Agent `config/read`, private `CODEX_HOME`, restore original fields. |
| 34 | `product-reinstall-retains-yolo-off-and-native-instance` | Actual enable/disable/reinstall; Agent `config/read`, private `CODEX_HOME`, restore original fields. |
| 35 | `yolo-on` | Actual enable/disable/reinstall; Agent `config/read`, private `CODEX_HOME`, restore original fields. |

## Added native checks

`linux-prerequisites`, `current-model-state`, `independent-launcher`, `codex-version`, `agent-permission-state`, `configuration-retained` retain the 0.1.10 observations. `installed-version` also retains the 0.1.10 installed hash/entry/version pairing enhancements. `user-permissions-retained` adds byte/mode comparison of the invoking user's permission and recovery files.

## Permission-state method

YOLO is not inferred from shell success or a confirmation prompt. On/off and recovery still execute; their state comes from native Agent configuration responses. The real Codex fixed-shell fixture tests function declarations, command execution and output replay as before; it is protocol coverage, not permission-state coverage. The fixture does not read user input, credentials or instructions. All test client and permission homes are removed after use.

## Portable and delivery additions

The 0.1.10 language, environment, independence and options-menu checks remain. Five new regressions protect discovery of every baseline/previous portable ID, Agent-state disagreement, enable/restore semantics through state reads, interrupted cleanup and rejection of incomplete native coverage. The delivery version-pin fixture now reads the actual product version rather than hardcoding a previous version.

The former deployment-identity gate is not restored. Actual Linux/systemd/dependency checks replace it, as explicitly requested; model and Codex functional acceptance does not depend on where Linux was created. No GPU/MTP hardware claim is derived from a portable fixture.
