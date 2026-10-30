# 0.1.15 independence contract

This release starts from the accepted 0.1.9 product. It has no IM or Web implementation. Bilingual presentation is retained as a self-contained interface improvement.

The product, bootstrap and tests do not identify a container provider, query an instance marker, access a container-management socket, import a sibling project, or depend on a pre-provisioned development image. Operating-system capabilities are checked directly. Linux, Python 3.11+ and a running systemd system manager are installation requirements; privilege is requested only for package and native service operations. Missing supported software dependencies are installed through the available native package manager. Unsupported package managers fail with the missing package list, without guessing a distribution.

No operation creates host mounts, changes namespaces, adjusts container privileges, configures an outer environment, or constrains native HOST settings. Existing native service ownership, conditional state changes and rollback remain in force.

The normal paired entry installs the selected components and runs all portable, installed-observation and baseline functional tests. It downloads two test models, switches/loads them, executes native Responses and Codex conversations/tools, checks the TUI picker and resource allocations, tests lifecycle reuse, rollback and reinstall, and finishes with the test model paused. No check depends on virtualization identity. The complete baseline remains mandatory; observation-only checks do not replace functional acceptance.

YOLO enable, disable and restoration use a private CODEX_HOME. State is determined exclusively from native Codex initialize/initialized/config/read responses, without a permission-challenge operation. Native tool protocol tests remain separate and use private client homes and a fixed test work directory. User permission/recovery bytes and file modes must remain unchanged. Private test homes and invalid-model fixtures are cleaned on normal exit, failure and interruption. Test models remain installed as in 0.1.9.
Acceptance covers source and packaged checks, installation/update in ordinary Linux, dependency success/failure, ordinary-user and root behavior, unchanged configuration during installed checks, native configuration responses, real PTY navigation, deterministic packages, absence of IM payloads, public artifact checksums and frozen previous releases. Product compatibility beyond exercised systems is not implied.

Existing 0.1.9 releases remain immutable. They retain historical environment requirements; new deployment environments are supported beginning with 0.1.10.
