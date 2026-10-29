# 0.1.10 independence contract

This release starts from the accepted 0.1.9 product. It has no IM or Web implementation. Bilingual presentation is retained as a self-contained interface improvement.

The product, bootstrap and tests do not identify a container provider, query an instance marker, access a container-management socket, import a sibling project, or depend on a pre-provisioned development image. Operating-system capabilities are checked directly. Linux, Python 3.11+ and a running systemd system manager are installation requirements; privilege is requested only for package and native service operations. Missing supported software dependencies are installed through the available native package manager. Unsupported package managers fail with the missing package list, without guessing a distribution.

No operation creates host mounts, changes namespaces, adjusts container privileges, configures an outer environment, or constrains native HOST settings. Existing native service ownership, conditional state changes and rollback remain in force.

The normal paired test entry installs the explicitly selected components and runs portable tests plus read-only installed-product checks. It does not download test models, change the selected model, pause/start/reconfigure existing services, change the user's YOLO choice, request Agent tool execution, or require a particular virtualization environment. YOLO is checked from the Agent's configuration response without starting a model turn. Configuration-write/recovery tests use private fixture directories. Test reports describe observations and unavailable optional software accurately.

Acceptance covers source and packaged checks, installation/update in ordinary Linux, dependency success/failure, ordinary-user and root behavior, unchanged configuration during installed checks, native configuration responses, real PTY navigation, deterministic packages, absence of IM payloads, public artifact checksums and frozen previous releases. Product compatibility beyond exercised systems is not implied.

Existing 0.1.9 releases remain immutable. They retain historical environment requirements; new deployment environments are supported beginning with 0.1.10.
