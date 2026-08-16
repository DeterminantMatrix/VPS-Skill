# Migration v4 to v4.1

v4.1 keeps `schema_version: 4` and `worker_protocol: 4`, but adds `implementation_version: 4.1` and changes the worker manifest. A v4 worker therefore fails closed by build/version validation and must be deliberately redeployed.

Key changes:

- QUICK becomes the default profile; AUDIT is explicit.
- QUICK uses smaller discovery/eligibility/Fast pools while preserving Deep reliability thresholds.
- Deep reuses same-run Fast samples and tops candidates up to 20 total samples.
- CT becomes QUICK backfill rather than an unconditional pass when regional sources are already sufficient.
- Candidate Reality tests fail fast after the first clean transport failure and continue down the ranked queue until five selectable candidates or the cap is reached.
- The run emits `incumbent_assessment` and `incumbent-assessment.json` with an explicit current-SNI verdict.
