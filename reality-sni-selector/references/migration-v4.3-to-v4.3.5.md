# Migration v4.3 to v4.3.5

v4.3.5 keeps `schema_version: 4` and `worker_protocol: 4`, but changes `implementation_version` to `4.3.5` and changes the six-file worker manifest. Existing managed v4.3 workers are upgraded by the normal managed-worker lifecycle before freeze.

Key changes:

- Deep/Reality becomes target-driven: initial Deep remains 10, then deterministic refill batches consume existing Fast survivors until five `SELECTABLE` candidates are found or the frozen caps/exhaustion condition is reached.
- QUICK deep cap becomes 18, refill batch 4, and Reality cap 16.
- TLS 1.3 and ALPN `h2` become REALITY protocol hard gates.
- cross-site redirects become a hard protocol-policy failure; same-site redirects remain allowed.
- Network Affinity is promoted to an explicit ranking/explanation dimension, with same-ASN as the strongest measured affinity signal.
- TLS protocol compliance and TLS transport reliability are reported separately.
- reports are modularized into executive conclusion, incumbent health card, Top-5 decision table, detailed candidate cards, how-to-choose guidance, search quality, adaptive-pipeline statistics, and full comparison evidence.
- `stage-status.tsv` no longer embeds a stale implementation version in human-readable freeze text.
- transient source failures (timeouts/HTTP 429/5xx) receive at most one bounded retry; non-transient failures are recorded without retry.
- final decision fields keep REALITY protocol failures, safety/front-door policy failures, and reliability failures distinct.

Do not resume an old frozen v4.3 run after worker upgrade. Start a new v4.3.5 selection invocation so the new protocol gates and adaptive limits are frozen consistently.
