# Migration v4 to v4.1

v4.1 keeps `schema_version: 4` and `worker_protocol: 4`, but adds `implementation_version: 4.1` and changes the worker manifest. A v4 worker therefore fails closed by build/version validation and must be deliberately redeployed.

Key changes:

- QUICK becomes the default profile; AUDIT is explicit.
- QUICK uses smaller discovery/eligibility/Fast pools while preserving Deep reliability thresholds.
- Deep reuses same-run Fast samples and tops candidates up to 20 total samples.
- CT becomes QUICK backfill rather than an unconditional pass when regional sources are already sufficient.
- Candidate Reality tests fail fast after the first clean transport failure and continue down the ranked queue until five selectable candidates or the cap is reached.
- The run emits `incumbent_assessment` and `incumbent-assessment.json` with an explicit current-SNI verdict.

- Target selectors may be exact IPv4/name/alias or a uniquely high-confidence fuzzy inventory name; fuzzy decisions are explicitly recorded.
- Controller artifacts always go to a dedicated run directory instead of the invocation parent directory.
- Exit 126/127 with `No such file or directory`/missing-command/bad-interpreter evidence maps to `TARGET_WORKER_UNAVAILABLE`, with a bounded secret-redacted stderr summary in controller metadata.
- Maintenance mode verifies the deployed wrapper without `run`; the returned worker identity provides protocol/version/manifest evidence without candidate traffic.
- Read-only local Skill validation must redirect Python bytecode caches or use a writable checkout.
