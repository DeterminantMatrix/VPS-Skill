# Candidate discovery v4.5

Run every discovery query and hostname/DNS validation from the selected target VPS. Discovery only creates candidates; Protocol / Safety / Reliability / Reality decide eligibility.

## Multi-lane model

Use four complementary lanes:

1. **General Regional** — nearby public website metadata without requiring an institution class.
2. **Network Affinity** — inventory ingress IPv4 -> RIPEstat routing/ASN/prefix metadata -> tiny deterministic Shodan InternetDB passive IP sample -> published hostnames only.
3. **Institutional preference** — Wikidata/OpenAlex plus institution-tagged OSM as a high-quality preference lane, never a prerequisite.
4. **Passive Expansion** — bounded CT expansion under registrable domains found by any lane.

Fixed regional seed files and the incumbent remain valid inputs outside the four lanes.

## Safety boundary

- Never scan raw CIDRs, ASNs, arbitrary IP ranges, ports, or BGP-derived addresses.
- RIPEstat is routing metadata only.
- InternetDB requests are passive third-party metadata lookups. Do not open candidate TCP/TLS connections to sampled addresses until a published hostname is discovered and passes normal hostname/DNS validation.
- Retry a transient source timeout / HTTP 429 / 5xx at most once.

## Regional metadata hygiene

Regional/Institutional directories can contain social-profile or aggregator URLs instead of a site's own domain. Filter common third-party profile/platform bases (for example Facebook, Instagram, LinkedIn, YouTube, TikTok, X/Twitter, Linktree and travel aggregators) **only when they arrive as Regional/Institutional metadata**.

This is a discovery-noise filter, not a REALITY hard policy. An explicit seed or an independently discovered Network-Affinity hostname may still be evaluated normally.

## Lane-aware bounded selection

Global caps must not let a large General Regional query starve smaller lanes. Before applying source-record and validated-hostname hard caps:

- preserve bounded reserve opportunity for Network Affinity, Institutional, General Regional, and Passive Expansion;
- prefer distinct registrable-domain families inside each reserve;
- let unused reserve flow back to deterministic common fill;
- record requested/actual reserve counts and whether the global cap was hit.

QUICK defaults:

- source pool cap: 520;
- validated hostname cap: 240;
- nominal breadth goal: 200;
- effective Protocol/Policy `ELIGIBLE` survivor goal: 15;
- General Regional ingest cap: 340 source records before common fill;
- Network Affinity: at most 4 announced prefixes considered and 24 passive InternetDB IP lookups;
- eligibility pool: 80.

AUDIT uses broader bounded caps: source 1,200, validated 600, breadth goal 400, survivor goal 25, up to 6 prefixes and 48 passive lookups.

## CT behavior

Do not let an early General Regional success suppress all Passive Expansion. When the primary source-stop target is already met, retain a very small bounded CT base pass so the passive lane has representation. Full CT remains backfill/extension rather than an unbounded crawl.

## Coverage and saturation

Report separately:

- `breadth_status`: validated count versus breadth goal;
- `quality_status`: effective `ELIGIBLE` count versus survivor goal;
- `active_discovery_lanes`, `lane_counts`, `source_counts`;
- `saturation.source_pool_cap_hit`, `saturation.validated_cap_hit`, eligibility/extension cap hits;
- safe source-error subtypes;
- combined `status`.

A run can execute its configured search well while still being unable to claim global optimality. Cap saturation and source failures therefore feed Global Optimality Confidence separately from Run Coverage Confidence.

## Quality-driven extension

If the initial bounded universe has too few effective survivors **or** the initial Deep set has no candidate meeting the frozen quality target, permit one bounded discovery extension. Probe only a capped set of newly validated candidates and never restart/retest the original universe.

The extension is a quality/coverage recovery path, not an excuse to grow an unlimited search.

## Network Affinity funnel

Record both hostname and registrable-family counts through:

```text
discovered -> validated -> SAME_ASN Gate -> Eligible -> Fast -> Deep -> Reality PASS -> SELECTABLE
```

Also report unique endpoint/IP-set count at the final stage. If no SAME_ASN family survives, distinguish "none discovered" from "discovered but rejected later".
