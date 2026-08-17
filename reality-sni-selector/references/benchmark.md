# Benchmark policy v4.4

## QUICK Fast stage

- At most **36** candidates including the incumbent baseline.
- Exactly 3 interleaved TCP+TLS samples per candidate.
- Use this stage for coarse ordering only.

## AUDIT Fast stage

- At most 50 candidates including the incumbent.
- 5 interleaved samples per candidate.

## Adaptive Deep stage

- Start with **10** total Deep rows including the incumbent when present.
- Target exactly 20 **total same-run samples** per candidate.
- Reuse Fast samples and measure only the missing samples.
- If fewer than five `SELECTABLE` candidates have been produced, take the next already-Fast-measured `ELIGIBLE` survivors in deterministic batches of **4** and Deep-test them.
- QUICK Deep cap: **18** total rows including incumbent. AUDIT Deep cap: **20**.
- Never Deep-test the same hostname twice in one run.
- Require >=95% overall TLS success for selectable non-incumbents and >=90% per-IP success when that IP has at least three samples.
- Deep samples also enforce TLS 1.3 and ALPN h2; a protocol downgrade found during Deep becomes a hard protocol failure.

## Ordering and near-ties

Use lexicographic ordering with protocol/policy/reliability first. Treat approximately **2 ms of P50 difference as a near-tie band**.

1. policy/protocol state;
2. reliability/success rate;
3. P50 equivalence band;
4. P95;
5. MAD;
6. observed Network Affinity (`SAME_ASN` strongest, then same organization or IPv4 /16, then same country, then different/unknown);
7. exact P50 as a late tie-break;
8. per-IP consistency;
9. front-door confidence;
10. source evidence.

Network Affinity is a near-tie preference. It must never override a protocol hard failure, reliability failure, or a materially worse latency result.

The incumbent is guaranteed as a baseline but receives no policy exemption in its separate assessment. `latency_target_ms` remains advisory.
