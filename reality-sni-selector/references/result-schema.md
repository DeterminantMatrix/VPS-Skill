# Result schema

The target worker returns one JSON object containing:

```text
schema_version
status
frozen_run
preflight
regional_candidates
candidates
probe_pool
eligibility
fast_benchmark
deep_benchmark
reality
top5
rejections
warnings
errors
counts
```

## Candidate states

Use independent dimensions where possible:

- `eligibility`: `ELIGIBLE`, `REVIEW_REQUIRED`, `HARD_REJECTED`, `BASELINE_ONLY`
- `execution`: `PROBED`, `DEFERRED_BUDGET`, `TEMPORARY_ERROR`, `SOURCE_ERROR`, `NOT_SELECTED`
- `final`: `SELECTABLE`, `REALITY_FAILED`, `RANKED_OUT`, `BASELINE_ONLY`, `PENDING_REALITY`

## Required count distinctions

Always distinguish:

- discovered/validated
- selected into eligibility pool
- deferred by probe budget
- hard rejected
- review required
- fast benchmarked
- deep benchmarked
- Reality tested
- selectable

A deferred candidate is never counted as failed.

## Top 5

Each row should include, when measurable:

- hostname
- incumbent flag
- source/category/locality evidence
- current IPv4 set
- front-door classification and evidence
- TLS versions / ALPN observations
- certificate identity/expiry summary
- fast and deep success rates
- P50/P90/P95/MAD/max
- per-IP consistency
- Reality result
- comparison with incumbent P50
- warnings/review notes

Unknown values must remain explicit `null`/`unknown`; do not invent them.
