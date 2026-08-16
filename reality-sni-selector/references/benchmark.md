# Benchmark policy

## Fast stage

- At most 50 candidates including the incumbent baseline when available.
- Exactly 5 interleaved TCP+TLS samples per candidate by default.
- Balance samples deterministically across current common IPv4s.
- Use success rate, P50, MAD, and max for coarse ranking.
- Do not use a five-sample P95 as a decisive statistic.

## Deep stage

- At most 10 candidates including the incumbent baseline.
- Exactly 20 interleaved samples per candidate by default.
- Report success rate, P50, P90, P95, max, MAD, and per-IP statistics.
- Require >=95% overall TLS success for non-incumbents.
- Require >=90% per-IP success when that IP has at least three samples.

## Ordering

Use lexicographic ordering:

1. policy state: `ELIGIBLE` before `REVIEW_REQUIRED`;
2. reliability/success rate;
3. P50;
4. P95;
5. MAD;
6. per-IP consistency;
7. front-door confidence;
8. exact target ASN as a late preference;
9. source/locality evidence.

The incumbent is guaranteed as a baseline but does not gain policy preference merely because it is incumbent.

`latency_target_ms` is advisory. Return the best evidence even when every candidate is above the target.
