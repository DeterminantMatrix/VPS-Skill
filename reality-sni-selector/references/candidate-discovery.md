# Candidate discovery and probe-pool selection

Run all discovery from the target VPS.

## Sources

Use bounded combinations of:

- fixed region seeds;
- Wikidata nearby institutional websites;
- OpenStreetMap/Overpass institutional websites;
- OpenAlex city institutions;
- passive CT names under already known institutional base domains;
- IPv4 DNS validation.

Do not scan raw CIDRs or arbitrary IP space.

## Coverage

Aim for at least 400 validated public-IPv4 hostnames within the fixed source/discovered caps.

- `GOOD`: >=400 validated hostnames
- `LIMITED`: 100-399
- `SPARSE`: <100

`LIMITED` and `SPARSE` runs remain usable but must be labeled `PROVISIONAL`. Preserve source errors such as CT failure-budget exhaustion, HTTP errors, and timeouts.

## Eligibility-pool diversity

The 120-candidate eligibility cap is not a simple source-order slice. Keep the incumbent, then deterministically favor diversity across:

- registrable domain;
- initial IPv4 fingerprint;
- organization label;
- source priority;
- measured locality/distance when present.

Use progressive passes: strict diversity, relaxed diversity, then deterministic fill. Candidates left outside the budget receive `DEFERRED:DIVERSITY_BUDGET` when diversity caused the skip, otherwise `DEFERRED:PROBE_BUDGET`.
