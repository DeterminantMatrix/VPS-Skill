# Certificate, Website, and Traffic Gate

Read this reference for every serious finalist before high-sample benchmarking.

## Certificate

Inspect the leaf certificate and complete SAN list:

```bash
timeout 10 openssl s_client -connect <DOMAIN>:443 -servername <DOMAIN> </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates -ext subjectAltName
```

For A:

- require the exact hostname as an explicit SAN;
- reject wildcard-only coverage;
- reject origin, mismatched, expired, or unrelated platform certificates;
- reject large unrelated shared SAN sets;
- require at least 30 days remaining.

For a Primary candidate, also record the negotiated TLS version and ALPN. Require TLS 1.3 and `h2` evidence before spending browser or 20-round benchmark budget. A generic `compatibility_pass` flag is not enough.

Apex plus `www` is a clean small SAN set.

## DNS, network, and CDN

Resolve all current A/AAAA records and document:

- tested IPs;
- ASN and organization;
- city/region/country;
- reverse DNS when useful;
- CDN, Anycast, cloud load balancer, or shared hosting;
- semantic and network identity mismatches.

Do not trust a scanner's `CDN: none` label. Do not automatically reject every CDN. A regional, active organization with a dedicated exact certificate and stable behavior can pass when the shared-front-door tradeoff is documented.

When the selection mode is `strict_no_cdn`, reject known CDN/platform/shared-front-door candidates before browser inspection. A CNAME to the same organization's apex is not by itself a CDN; classify the CNAME target and the returned IP/ASN instead of using a blanket CNAME rule.

Classify the organization after hard protocol gates. Prefer, in order, same-ASN universities, libraries, museums, research institutes/centers, think tanks, nonprofits, charities, and public organizations; then same-region versions of those organizations; then other suitable direct organizations. This is a preference only and never overrides certificate, TLS, WAF, front-door, or website failures.

## Deterministic footprint pass

Run one bounded document request per candidate:

```bash
python "<SKILL_DIR>/scripts/inspect_site_footprint.py" <DOMAIN...>
```

Record final URL, status, document bytes, visible-text estimate, link/image/script/style counts, title, and placeholder markers. This is a first pass only.

## Browser pass

Open each exact finalist hostname once in a real browser. Inspect:

- meaningful rendered content;
- normal navigation and coherent sections;
- identifiable organization;
- current events, notices, products, services, or other signs of operation;
- WAF/403 behavior;
- unrelated redirects;
- blank, parked, default, for-sale, maintenance, or one-logo holding pages.

Classify:

- `substantial`
- `small-active`
- `uncertain`
- `placeholder`

Allow at most one same-host or same-organization redirect for a Primary candidate. Multi-hop, unrelated, login-enforcing, or challenge redirects are a hard failure for the strict gate. Preserve the requested hostname, final URL, and organization relationship as separate evidence fields.

Static technology is neutral. A useful static documentation or institution site can be substantial. A single image with no navigation is a placeholder.

`placeholder` cannot exceed C. `uncertain` cannot exceed B until resolved.

## Traffic plausibility

REALITY implementations and versions can differ, so verify actual behavior when it matters. In general, the target can receive TLS handshakes and invalid/fallback connections. Do not equate proxy payload bytes with target traffic.

When a production node exists, run on the VPS:

```bash
python3 observe_connection_rate.py --port 443 --seconds 20
```

Treat `/proc/net/snmp` passive-open deltas as system-wide approximations. Use per-service logs, nftables/conntrack, eBPF, or implementation-specific counters when available. Never present the approximation as an exact REALITY rate.

Judge whether the observed connection pattern is plausible for the site's public footprint:

- low-rate traffic can fit a small but active regional site;
- higher or unknown rates favor an established institution or higher-traffic public site;
- an empty or abandoned page is unsuitable regardless of low latency;
- if uncertainty remains, downgrade instead of inventing a threshold.

## Request budget

- Use TLS-only or normal `HEAD` for broad filtering when supported.
- Load browser subresources only for the single browser inspection.
- Reserve document `GET` requests for finalists.
- State that command-line GETs fetch the document but not its images/CSS/scripts.
- Stop on `429`, `Retry-After`, repeated `403/5xx`, resets, or distress signals.
