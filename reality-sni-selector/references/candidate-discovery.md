# Candidate discovery and probe-pool selection

Run all discovery from the target VPS.

## Sources

Use bounded combinations of fixed region seeds, Wikidata, OpenStreetMap/Overpass, OpenAlex, passive CT under already known institutional base domains, and IPv4 DNS validation. Never scan raw CIDRs or arbitrary IP space.

Independent primary metadata sources may run concurrently. For transient timeout/HTTP 429/5xx failures, retry that source at most once with a short delay; non-transient HTTP failures are recorded immediately. A failed source never blocks the rest of QUICK discovery.

## QUICK profile v4.3.5

Aim for **200** validated public-IPv4 hostnames within a **520-source / 240-validated** cap. Collect primary regional institutional sources first. If the source record pool reaches about **300** records, skip passive CT. Otherwise expand regional discovery and use CT only as backfill until the stop target/caps or CT failure budget is reached.

- `GOOD`: >=200 validated hostnames
- `LIMITED`: 100-199
- `SPARSE`: <100

A GOOD QUICK run is `QUICK_CONFIDENT`, not an exhaustive internet search. A SPARSE run may still yield high-confidence individual candidates when the full Policy/Deep/Reality gates pass; report search confidence separately from candidate confidence.

## AUDIT profile

Restore the broader source cap 1,200, validated cap 600, and coverage goal 400. AUDIT retains the broad expanded/CT pass.

- `GOOD`: >=400
- `LIMITED`: 100-399
- `SPARSE`: <100

GOOD AUDIT coverage is `AUDIT_MATURE`; lower coverage is `PROVISIONAL`.

## Eligibility-pool diversity

QUICK selects at most **80** candidates; AUDIT at most 120. Keep the incumbent, then deterministically favor diversity across registrable domain, initial IPv4 fingerprint, organization, source priority, and locality. Use strict diversity, relaxed diversity, then deterministic fill. Deferred candidates are not failures.
