# Migration v4.1 to v4.2

v4.2 keeps `schema_version: 4` and `worker_protocol: 4` while changing `implementation_version` to `4.2` and therefore changing the worker manifest.

Main change: worker readiness is now managed automatically before the SNI run is frozen.

- Probe `/usr/local/bin/reality-sni-target-worker identity` first.
- If the exact v4.2 manifest/wrapper is already present, continue without writes.
- If the worker is absent, bootstrap the fixed worker automatically.
- If a reviewed v4/v4.1 pre-marker worker is detected by exact legacy hashes, upgrade it automatically.
- If `.managed.json` proves an existing install is managed by this Skill, safely upgrade it when stale.
- If fixed paths contain unknown content, fail `WORKER_PATH_CONFLICT` and do not overwrite it.
- Freeze candidate-selection parameters **after** the worker is exact and ready, so a missing worker no longer creates a dead frozen run.
- Write `worker-lifecycle.json` for readiness/bootstrap audit evidence.
- Support `--worker-bootstrap never` for fail-closed/no-write operation and `--worker-ready-only` for readiness-only preparation.

QUICK/AUDIT candidate logic, incumbent assessment, shared-platform policy, Fast-to-Deep sample reuse, Reality fail-fast behavior, and final multi-domain reporting remain unchanged from v4.1.
