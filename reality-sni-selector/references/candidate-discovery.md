# Candidate discovery v4.4

Run every discovery query and hostname/DNS validation from the selected target VPS. Discovery produces candidates only; it never makes a domain eligible by itself.

## Multi-lane model

Use four complementary lanes:

1. **General Regional** — query nearby OpenStreetMap features that explicitly publish `website`, `contact:website`, or `operator:website`. This lane includes ordinary businesses, organizations, media, service sites, community sites, and institutions. Institution status is not required.
2. **Network Affinity** — use the inventory ingress IPv4 with RIPEstat routing data to identify the containing prefix / announcing ASN, then perform a tiny deterministic sample of Shodan InternetDB passive IP lookups. Extract published hostnames only. Never open TCP connections to sampled addresses and never sweep an ASN/CIDR.
3. **Institutional preference** — retain Wikidata/OpenAlex and institution-tagged OSM records as a high-quality preference lane. Institutional provenance may help prioritization/interpretation but is never an eligibility requirement.
4. **Passive Expansion** — use bounded CT expansion under registrable domains already found by any lane, not only institutional roots.

Fixed regional seed files and the incumbent remain valid inputs outside these lanes.

## Safety boundary

- Never scan raw CIDRs, arbitrary IP ranges, ports, or addresses discovered from BGP data.
- RIPEstat is routing metadata only.
- InternetDB requests are passive third-party lookups; QUICK uses a fixed small IP sample and no candidate TCP/TLS traffic is sent to those sampled IPs.
- Candidate TCP/TLS/HEAD/Reality measurements still begin only after a hostname resolves through normal candidate validation.
- Keep transient source retry bounded to one short retry for timeout, HTTP 429, and 5xx failures.

## QUICK profile

Keep overall runtime close to v4.3.5 while reallocating discovery breadth:

- source pool cap: 520;
- validated hostname cap: 240;
- nominal validated breadth goal: 200;
- effective Protocol/Policy-eligible survivor goal: 15;
- General Regional OSM record cap: 1,100;
- Network Affinity: at most 4 announced prefixes considered and 24 passive InternetDB IP lookups;
- eligibility pool: 80.

`coverage.status` is no longer derived from hostname count alone. Preserve:

- `breadth_status`: validated-hostname breadth;
- `quality_status`: number of effective `ELIGIBLE` survivors versus the profile goal;
- `active_discovery_lanes` and per-lane counts;
- combined `status`: `GOOD`, `LIMITED`, or `SPARSE`.

A large institutional-only list is not sufficient for `GOOD` multi-lane coverage.

## Lane reserves

Discovery provenance must influence measurement opportunity without bypassing gates.

QUICK reserves bounded eligibility-pool space for Network Affinity, General Regional, and Institutional lanes. Fast/initial Deep also reserve a small number of slots for measured network-affinity candidates. These are opportunity reserves only:

- TLS1.3/h2/certificate/redirect minimums still apply;
- CDN/shared-platform hard policy still applies;
- reliability still applies;
- Reality 5/5 still applies.

Same-ASN never rescues an otherwise rejected candidate and does not override materially worse tail latency/stability.

## Network Affinity funnel

Record enough evidence to explain why the final Top 5 does or does not contain SAME_ASN choices:

```text
affinity hostnames discovered
-> validated
-> SAME_ASN seen at Gate
-> SAME_ASN eligible
-> Fast
-> Deep
-> Reality tested
-> Reality passed
-> SELECTABLE
```

If no SAME_ASN candidate survives, distinguish "none discovered" from "discovered but rejected".

## AUDIT profile

Use the same multi-lane architecture with broader fixed caps: source 1,200, validated 600, nominal breadth goal 400, effective eligible survivor goal 25, up to 6 announced prefixes considered, and 48 passive InternetDB IP lookups. AUDIT remains bounded and does not perform raw network scans.
