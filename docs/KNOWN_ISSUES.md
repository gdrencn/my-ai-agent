# Known issues

## CA directories loaded lazily by a Python SSL build

Observed during extra 0.1.13 validation with portable CPython 3.14.10. The interpreter used `/etc/ssl/certs` as a valid default certificate directory and no default certificate file. A real urllib HTTPS request succeeded, but a fresh `ssl.create_default_context().get_ca_certs()` returned an empty list because OpenSSL loads CA-directory entries lazily. `maa.environment.missing_dependencies()` currently interprets that list as a missing `ca-certificates` package. Reinstalling the already-present OS package does not resolve that false positive.

For this owned validation environment, `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt` explicitly selects the already-installed system bundle; prerequisite checks and HTTPS then use that file. This is test-environment configuration, not a change to the Maa dependency check. The ordinary system-Python 3.12 environments and the user's reported system-Python 3.14 installation had already passed CA checks.

This independent compatibility issue is recorded for separate discussion and remains unresolved in 0.1.13. No original prerequisite check was removed or suppressed. The 0.1.13 code change addresses owned Codex process termination before temporary-directory cleanup.
