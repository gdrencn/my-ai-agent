# my-ai-agent 0.1.14 implementation

## Verified correction

The reported installation stopped before functional tests, in sudo systemctl stop. The common output runner captured inherited diagnostics until command exit, hiding sudo-rs authentication prompts. The sudo command and capture behavior were already present in 0.1.9; the 0.1.13 process-lifecycle correction did not introduce them. Prior NOPASSWD validation did not exercise password authentication.

All privileged operations now share a terminal-aware path. Root runs directly. Interactive commands forward native diagnostics immediately, including when stdout is captured or discarded. A noninteractive sudo validation probe determines whether Maa progress must yield the terminal; the actual command retains normal sudo authentication policy. Passwords remain exclusively between native sudo and the controlling terminal. Neither Maa nor the test runner reads or stores them. Noninteractive or explicitly captured privileged calls use sudo -n and fail promptly when authentication is unavailable. Recovery no longer suppresses sudo stderr. No sudo policy, global timestamp setting or password helper is installed.

The shared output runner supports live inherited stderr with independently captured stdout and an optional stderr copy. Native acceptance uses that common path, so child Maa authentication is not hidden by the test harness. Structured stdout, native output, checked errors, partial timeout diagnostics and terminal restoration remain covered. Existing output handling is retained for normal commands. Native units still execute native programs; codex-local remains an independent shell launcher. No Maa runtime service or process is added.

## Current verification

138 source portable/PTY and 13 delivery tests passed. The same 138 packaged tests passed outside the checkout. Every 0.1.9, 0.1.10, 0.1.11, 0.1.12 and 0.1.13 portable ID remains; ten new authentication/output regressions were added. Python 3.11 grammar, shell syntax, deterministic build and independent-product package checks passed.

Seven actual authentication scenarios passed separately with sudo-rs 0.2.13 on Python 3.14.4 and classic sudo 1.9.15p5 on Python 3.12.3: piped stdin with captured stdout and cache reuse, nested live diagnostic capture, wrong-password retry, interruption, prompt-free noninteractive failure, zero-duration timestamps and command-specific NOPASSWD. Authentication prompts remained visible across progress ticks, test passwords were not echoed, and terminal flags were restored.

The final candidate passed 138 paired tests plus all 42 native checks in both an ordinary-user Python 3.14.4 environment and a root Python 3.12.3 environment with Git available. Both GPU backend paths, real native Responses and Codex conversations, the actual model picker, manager independence, expiry/reuse, rollback, exact written profiles, real-home/private-off reinstall and permission restoration passed.

Evidence: [local checks](validation/V0_1_14_LOCAL.json), [ordinary-user native report](validation/V0_1_14_NATIVE.json), [root native report](validation/V0_1_14_ROOT_NATIVE.json), [real authentication matrix](validation/V0_1_14_AUTHENTICATION.json), [coverage](validation/V0_1_14_COVERAGE.json). Tag CI exposed a test-harness race: PTY EOF can precede waitpid readiness. The harness now waits within its original deadline, with a deterministic early-EOF regression. The final ordinary-user/root reruns passed 138 paired and all 42 native checks each. Public-entry verification is pending at this stage. Historical releases remain unchanged. The known portable-Python CA-directory detection issue is independent and remains documented in docs/KNOWN_ISSUES.md.
