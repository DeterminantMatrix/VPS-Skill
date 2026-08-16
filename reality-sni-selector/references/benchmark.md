# Benchmark policy

## Fast benchmark

- At most 50 candidates, plus incumbent baseline if needed.
- Five interleaved TCP+TLS samples per candidate.
- Balance samples across the candidate's common public IPv4 addresses.
- Record success rate, P50, max, and MAD.
- Five samples are not enough for a meaningful decisive P95; do not use fast-stage P95 as a hard criterion.

Retain at most 8-10 for deep benchmark.

## Deep benchmark

Default to 20 interleaved samples per candidate. Record:

- success rate
- P50
- P90
- P95
- max
- MAD
- per-IP success and sample count
- DNS/IP consistency observations

## Latency goal

`latency_target_ms = 60` is an advisory goal. If every otherwise-valid target exceeds it, report the best available candidates rather than returning an artificial empty set.

## Ranking

Use lexicographic ranking rather than an opaque weighted score:

1. policy eligibility / Reality final eligibility
2. success rate
3. target-side P50
4. target-side P95
5. MAD/jitter
6. per-IP consistency
7. front-door confidence
8. institutional/locality evidence

The incumbent is a baseline and may remain `BASELINE_ONLY` even if it would not be selectable under current policy.
