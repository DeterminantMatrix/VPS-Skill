# Candidate discovery

## Goal

Build a bounded pool of public IPv4 hostnames associated with suitable institutions in the target VPS region. Discovery itself runs on the target VPS.

## Sources

Use, in order:

1. the resolved incumbent and any optional fixed region-specific seed hostnames;
2. nearby Wikidata official-website records when usable coordinates are available;
3. nearby OpenStreetMap website/contact:website records for institutional categories;
4. bounded OpenAlex institutional homepage supplement when a city is available;
5. passive CT names under known institutional base domains;
6. explicitly configured bounded passive supplements.

A bundled seed file is not mandatory. Do not substitute a seed list from the controller's region.

Do not expand an ASN into CIDRs and scan it. PTR is optional and must remain tightly budgeted if later enabled.

## Location degradation

If precise location is unavailable, continue with fixed region seeds and safe passive expansion. Emit `LOCATION_DEGRADED`. Never substitute the controller's city or coordinates.

If observed geolocation materially conflicts with the inventory region, emit `REGION_MISMATCH_REVIEW`; avoid coordinate-radius discovery and keep the run on the declared regional seed set rather than silently switching regions.

## Candidate hygiene

Prefer normal web front-door hostnames. Exclude obvious service labels such as `smtp`, `imap`, `mail`, `mx`, `ns`, `ftp`, `vpn`, `admin`, `cpanel`, and `autodiscover` unless the incumbent itself uses such a name.

Treat `example.org`, `www.example.org`, and `portal.example.org` as distinct candidates.

## Coverage states

- `GOOD`: >= 400 validated public IPv4 hostnames
- `LIMITED`: 100-399
- `SPARSE`: < 100

Coverage is descriptive; it is not a reason to increase probe budgets mid-run.
