# Benchmark policy

## QUICK Fast stage

- At most 30 candidates including the incumbent baseline.
- Exactly 3 interleaved TCP+TLS samples per candidate.
- Use this stage only for coarse ordering; do not treat a 3-sample tail percentile as decisive.

## AUDIT Fast stage

- At most 50 candidates including the incumbent.
- 5 interleaved samples per candidate.

## Deep stage

- At most 10 candidates including the incumbent.
- Target exactly 20 **total same-run samples** per candidate.
- Reuse Fast samples, then interleave only the missing samples. QUICK therefore normally adds 17 samples, not another independent 20.
- Report success rate, P50, P90, P95, max, MAD, and per-IP statistics.
- Require >=95% overall TLS success for selectable non-incumbents.
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

The incumbent is guaranteed as a baseline but receives no policy exemption in its separate incumbent assessment. `latency_target_ms` remains advisory.
