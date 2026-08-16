# Result schema v4 / implementation 4.2

The worker returns one JSON object containing at least:

```text
schema_version
worker
status
frozen_run
preflight
coverage
regional_candidates
candidates
probe_pool
eligibility
fast_benchmark
deep_benchmark
reality
preliminary_top5
top5
comparison
incumbent_assessment
rejections
warnings
errors
counts
```

## Independent candidate dimensions

Keep policy eligibility, benchmark eligibility, Reality compatibility, and final state separate. `SELECTABLE` requires a clean policy state, benchmark reliability pass, Reality 5/5 PASS, and clean cleanup. Reality PASS never clears a policy rejection.

## Current SNI assessment

`incumbent_assessment` contains:

- hostname;
- machine code and Chinese verdict;
- confidence;
- reason codes;
- current policy/reliability/P50/P95/MAD/Reality-control metrics;
- best fully selectable alternative and relative improvements when available.

See `incumbent-assessment.md` for verdict precedence.

## Coverage

Return profile (`quick`/`audit`), goal, validated count, `GOOD/LIMITED/SPARSE`, selection maturity (`QUICK_CONFIDENT`, `AUDIT_MATURE`, or `PROVISIONAL`), CT-skip evidence, and source errors.

## Comparison

Produce a recommendation-sorted multi-dimensional comparison with at least five distinct measured domains whenever at least five exist. Include the incumbent baseline even if this extends the table. Include final/policy state, front-door/platform, TLS success, P50/P90/P95/MAD/max, Reality result/failure stage, ASN/organization evidence, and incumbent P50 improvement. Never fabricate rows.

## Efficiency counters

Counts should include Fast/Deep candidate counts, reused Fast samples inside Deep, newly measured Deep samples, Reality candidates attempted, Reality passes, selectable count, and selectable target.


## Controller worker lifecycle artifact

The controller writes `worker-lifecycle.json` before freeze. It records the preflight identity state, whether the fixed worker was already ready/installed/upgraded, the expected manifest/wrapper hash, backup metadata when applicable, and the post-bootstrap identity result. This artifact contains no SNI candidate measurements.
