# Migration v4.2 to v4.3

v4.3 keeps `schema_version: 4` and `worker_protocol: 4`, changes `implementation_version` to `4.3`, and changes the six-file worker manifest. The v4.2 managed worker is therefore upgraded automatically by the existing v4.3 lifecycle when the selected SSH alias can manage the fixed paths.

## Main behavior changes

- QUICK candidate breadth increases moderately: source cap 520, validated cap 240, coverage goal 200, eligibility 80, Fast 36 x 3, Deep up to 10 x 20 total, Reality cap 10 while still targeting five selectable results.
- P50 differences inside a 2 ms equivalence window no longer win ranking by themselves; P95, MAD and stability evidence break near-ties.
- Every compared candidate receives policy, Reality, TLS, performance, runtime-stability, durability-risk and confidence dimensions.
- Candidate confidence and search-coverage confidence are separate.
- Incumbent assessment explicitly explains when the current SNI is faster but still must be replaced because of a higher-priority policy failure.
- `decision-summary.json` is added, and the final model response is governed by `reporting.md` so five selectable candidates cannot be silently reduced to three.

No production sing-box/network configuration is changed by this migration.
