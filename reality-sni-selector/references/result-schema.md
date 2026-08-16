# Result schema v4

The worker returns one JSON object with:

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
rejections
warnings
errors
counts
```

## Independent candidate dimensions

Keep these separate:

- `policy_eligibility`: `ELIGIBLE`, `REVIEW_REQUIRED`, `HARD_REJECTED`, `BASELINE_ONLY`
- `benchmark_eligibility`: `PASS` or a benchmark hard-failure state
- `reality_compatibility`: `PASS`, `FAIL`, `NOT_TESTED`
- `final_state`: `SELECTABLE`, `REVIEW_REQUIRED`, `POLICY_REJECTED`, `REALITY_FAILED`, `NOT_REALITY_TESTED`, `BASELINE`, or ranked-out equivalent

`SELECTABLE` requires policy eligibility, benchmark pass, Reality PASS, and clean cleanup. Reality PASS never clears a policy rejection.

## Coverage

Return:

- `goal`
- `validated`
- `status`: `GOOD`, `LIMITED`, `SPARSE`
- `selection_maturity`: `MATURE` only for GOOD, otherwise `PROVISIONAL`
- `source_errors`

## Comparison

Produce a recommendation-sorted multi-dimensional comparison with at least five distinct measured domains whenever at least five exist. Include the incumbent baseline even if this extends the table beyond five rows.

Each comparison row should include, when measurable:

- recommendation rank and level;
- hostname;
- final/policy state;
- benchmark stage;
- front-door class/provider/platform;
- success rate;
- P50/P90/P95/MAD/max;
- per-IP consistency;
- Reality compatibility and sanitized failure summary;
- ASN/organization evidence and exact-target-ASN flag;
- incumbent P50 improvement;
- warnings/review notes.

If fewer than five distinct measured domains exist, return all available rows and emit `INSUFFICIENT_COMPARISON_DOMAINS`.
