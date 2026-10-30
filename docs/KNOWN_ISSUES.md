# Known issues and resolved compatibility reports

## Resolved in 0.1.15: lazy CA-directory detection

The portable-Python 3.14.10 CA-directory false positive recorded during 0.1.13 validation is corrected in 0.1.15. CA availability now accepts readable, indexed and parseable CA files in the effective OpenSSL default/SSL_CERT_DIR directory list without requiring those certificates to be loaded before a TLS request. Empty, missing, invalid, unindexed, CRL-only and leaf-only stores remain unavailable. HTTPS certificate and hostname verification remain enabled.

The historical observation and its explicit CA-file workaround remain part of immutable 0.1.13/0.1.14 evidence. They are not a current workaround requirement. Actual default-directory behavior is verified with portable CPython 3.14.10; synthetic directory-only HTTPS verifies successful trust, wrong-host rejection and empty-trust rejection. See [TLS evidence](../validation/V0_1_15_TLS.json).

## Resolved in 0.1.15: native IPv6 authorities

Both native client URL builders now bracket IPv6 literals. Wildcard IPv6 listeners use ::1 for clients, while native listeners retain their configured bind address. Profiles, native preload/readiness/status and real Codex conversations were verified with both Ollama and llama.cpp, using explicit ::1 and wildcard ::. See [IPv6 evidence](../validation/V0_1_15_IPV6.json).

Native model/protocol limitations remain documented in README.md. A synthetic small-model check is not evidence of MTP performance or general coding quality.
