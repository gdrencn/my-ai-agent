# my-ai-agent 0.1.10 implementation

## Verified source stage

Based on accepted stable/0.1.9 (source b3189e95d996cbb36911076e5e90ef9feca39021). Model lifecycle and native direct Codex behavior are retained. Presentation carries forward independent Chinese/English preferences, template diagnostics and catalogs; language/about are grouped under Options. No IM or Web runtime is included.

Removed deployment-identity checks from bootstrap, installation and service management. Linux, Python and live systemd are checked directly. Missing software dependencies use a shared native package command table; generated shell entries prepare bootstrap prerequisites. No system upgrade, outer-environment configuration or HOST restriction is introduced.

Installed checks were replaced with read-only version, prerequisite, current model state, launcher and native Codex configuration observations. Portable configuration/recovery checks use private fixtures. The runtime query sends only initialize/initialized/config/read, starts no Agent turn and returns only permission fields. It terminates its child process group on success/failure/timeout. Default tests no longer download models, switch targets or force a YOLO baseline. Reports are private and configuration bytes are compared before/after installed checks.

113 source portable/PTY regressions and 13 delivery regressions passed. The identical paired package passed outside the checkout. Ordinary-user checks passed 113 paired and seven read-only installed checks with each real backend; root passed 113 paired and seven read-only installed checks. An ordinary Linux test identity completed official Ollama, llama.cpp and Codex installation using the new installer. The same final hashes were verified in both identities. Service commands now resolve curl/truncate from installed tools instead of assuming fixed executable paths. Installed acceptance verifies the installed archive hash and command version against its paired product. Public v0.1.10 is published as a prerelease. All eight initial assets were downloaded anonymously, compared byte for byte and checked against both manifests. The actual public main/test/test.sh entry installed 0.1.10 with --components none and passed 113 portable/PTY plus seven read-only installed checks, retaining the existing off YOLO choice. Source, tag and main CI passed. Existing stable 0.1.9 and experimental 0.2.2 metadata/assets are unchanged; latest formal release remains stable/0.1.9. Historical 0.1.9 implementation evidence is preserved in docs/history/0.1.9/IMPLEMENTED.md; it is not new acceptance for this release.

Validation receipt: [V0_1_10_LOCAL.json](validation/V0_1_10_LOCAL.json). Product SHA-256: `5f54863a6cd17db845518c6d14ff57b68cdf4afa5ea4866f15dd4b717a4cf849`; paired tester: `96860d437da5cbba01599f607862343c79151ea27bb7f87ba82ac87c0910528f`. No native GPU/MTP or non-apt distribution acceptance is claimed.

The owned Linux validation environment also rebooted successfully with its installed manager archive removed: the selected native backend autostarted, and codex-local --version remained usable. The manager archive was restored after the check. No Agent tools were executed.

Public verification: [V0_1_10_PUBLIC.json](validation/V0_1_10_PUBLIC.json). Product/test bytes are frozen; user acceptance on other machines remains pending.

Owned validation environments were deleted after public acceptance. [V0_1_10_CLEANUP.json](validation/V0_1_10_CLEANUP.json) completes the cleanup that was pending at the public-download receipt. Shared global guidelines and host Codex were not modified.
