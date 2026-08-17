# Benchmark policy v4.5

## Fast stage

QUICK measures at most 36 candidates x 3 interleaved TCP+TLS samples. AUDIT measures at most 50 x 5. Fast is a coarse ordering stage; it preserves bounded Network-Affinity opportunity and does not override Protocol/Policy gates.

## Adaptive Deep stage

- Start with 10 total Deep rows including the incumbent when present.
- Target exactly 20 total same-run samples per candidate; reuse Fast samples and collect only missing samples.
- Require >=95% overall TLS success and >=90% per-IP success when that IP has at least three samples.
- Deep also enforces TLS1.3/h2; an observed downgrade becomes a protocol hard failure.
- Refill from already-Fast-measured `ELIGIBLE` survivors in deterministic batches of 4 when either the independent-family portfolio goal or quality goal is unmet.
- Prefer new registrable-domain families before measuring duplicate-family hostnames.
- QUICK Deep cap: 22 total rows including incumbent. AUDIT Deep cap: 24.
- Never Deep-test the same hostname twice in one run.

A one-time bounded discovery extension may contribute additional Fast/Deep rows when the initial universe cannot satisfy the survivor/quality goals. Its probe budget is separate and capped.

## Portfolio and quality stop

The normal success stop is **not** merely five hostnames.

Require:

1. at least five `SELECTABLE` **independent registrable-domain families**; and
2. at least one selectable candidate meeting the frozen quality target.

Same-family apex/`www` variants may be retained as family alternatives but do not consume duplicate Top-5 slots by default.

The default QUICK quality target is met when either:

- P50 <= `latency_target_ms` (normally 60 ms); or
- P50 <= 1.25 x target, P95 <= 1.60 x target, MAD <= 7.5 ms, and TLS success >=95%.

This is a **search stop/quality label**, not an eligibility hard gate. A fully Protocol/Policy/Reality-valid candidate above the target remains selectable. If five independent families exist but the bounded search never finds a quality-target candidate, return `SUCCESS_QUALITY_BELOW_TARGET`.

## Ordering and near-ties

Use lexicographic ordering with hard eligibility/reliability first. Treat approximately 2 ms of P50 difference as a near-tie band:

1. protocol/policy state;
2. TLS transport reliability;
3. P50 equivalence band;
4. P95;
5. MAD / observed latency consistency;
6. Network Affinity (`SAME_ASN` strongest);
7. exact P50 as a late tie-break;
8. per-IP consistency;
9. front-door confidence;
10. source/provenance evidence.

Network Affinity is a preference after correctness. It never rescues a protocol/policy/reliability failure or a materially worse tail-latency result.
