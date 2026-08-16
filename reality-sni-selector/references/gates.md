# Gates and edge/platform evidence

Latency and Reality compatibility cannot rescue a hard policy failure.

## Hard reject

| Requirement / policy | Code |
|---|---|
| no usable public IPv4 | `HARD:NO_PUBLIC_IPV4` |
| SNI TLS unreachable on a common IPv4 | `HARD:TLS_UNREACHABLE` |
| certificate chain/time invalid | `HARD:CERT_INVALID` |
| certificate identity mismatch | `HARD:CERT_IDENTITY` |
| confirmed shared public CDN/front door | `HARD:KNOWN_PUBLIC_CDN` |
| confirmed shared managed platform/front door | `HARD:KNOWN_SHARED_PLATFORM` |
| deep overall TLS success <95% | `HARD:TLS_SUCCESS_LT_95` |
| sufficiently sampled IPv4 success <90% | `HARD:IP_SUCCESS_LT_90` |

## Front-door classes

Use:

- `DIRECT_CONFIRMED`
- `DIRECT_LIKELY`
- `UNKNOWN_EDGE_EVIDENCE`
- `UNKNOWN_TOOLING`
- `SHARED_PLATFORM_CONFIRMED`
- `PUBLIC_CDN_CONFIRMED`

Missing evidence is never direct evidence. If HEAD evidence is unavailable and no stronger classification is available, use `UNKNOWN_EDGE_EVIDENCE`, not `DIRECT_LIKELY`.

## Public CDN evidence

Recognize high-confidence CNAME/header/network-organization evidence for shared public edges such as Cloudflare, CloudFront, Akamai, Fastly, Azure CDN/Front Door, CDN77, Netlify, Vercel, and Imperva/Incapsula. Do not classify a generic cloud-hosting ASN alone as CDN.

## Pantheon shared-platform policy

Treat Pantheon as `SHARED_PLATFORM_CONFIRMED` when high-confidence evidence includes one or more of:

- a Pantheon platform hostname/CNAME such as `*.pantheonsite.io`, `*.pantheon.io`, or `*.gotpantheon.com`;
- Pantheon-specific response headers such as `X-Pantheon-Styx-Hostname`, `X-Pantheon-Endpoint`, or `X-Pantheon-Edge-Server`;
- network-organization evidence identifying Pantheon.

Under the fixed strict shared-edge policy, classify it as `HARD:KNOWN_SHARED_PLATFORM` even if the site passes TLS, latency, and Reality integration.

Rationale: Pantheon documents that every Pantheon site uses its Global CDN and that inbound IPs are shared. The classifier therefore must not rely on a visible CDN CNAME alone.

## Soft/review signals

Do not hard reject solely for:

- TLS 1.2 instead of TLS 1.3 (`WARN:TLS12_ONLY`);
- no h2 (`WARN:NO_H2`);
- 403/405/429/5xx HEAD response;
- cross-site redirect;
- unknown external CNAME or insufficient edge evidence;
- bounded metadata source failure.

Use `REVIEW:EDGE_UNKNOWN` for unresolved edge evidence.
