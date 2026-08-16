# Gates and evidence policy

Hard gates run before ranking. Latency cannot rescue a hard failure.

## Hard reject

Use hard rejection only for correctness/safety failures:

| Requirement | Hard code |
|---|---|
| at least one public IPv4 A record | `HARD:NO_PUBLIC_IPV4` |
| SNI TLS reachable on a common IPv4 | `HARD:TLS_UNREACHABLE` |
| certificate chain/time validity | `HARD:CERT_INVALID` |
| certificate matches exact hostname or acceptable wildcard | `HARD:CERT_IDENTITY` |
| confirmed shared public CDN/front door | `HARD:KNOWN_PUBLIC_CDN` |

A common A record with zero successful TLS samples is materially failing. Partial cheap-gate instability is a review/reliability signal and is measured again in benchmark instead of being automatically converted into a two-sample false negative.

## Soft signals / review

Do not hard reject solely because of:

- TLS 1.2 instead of TLS 1.3: `WARN:TLS12_ONLY`
- no negotiated h2: `WARN:NO_H2`
- 403/429/5xx/405 HEAD response
- cross-host redirect
- unknown external CNAME / insufficient direct-vs-edge evidence
- temporary DNS or HTTP metadata errors when TLS identity can still be measured

Use `REVIEW:EDGE_UNKNOWN` for unresolved edge evidence. Unknown is not equivalent to public CDN.

## Public CDN evidence

`HARD:KNOWN_PUBLIC_CDN` requires strong evidence such as a recognized provider CNAME or provider-specific edge header, optionally corroborated by provider network/organization evidence.

Recognize common shared public edges such as Cloudflare, CloudFront/Amazon edge, Akamai, Fastly, Azure CDN/Front Door, CDN77, Netlify, Vercel, and Imperva/Incapsula.

A generic cloud-hosting ASN alone is not sufficient proof of public CDN.

## Redirects and HTTP

Do not follow redirects during evidence collection. Record Location only.

- same-host/same-site redirect: informational
- cross-site redirect: warning/review signal
- HTTP status is separate from transport success
- 429 should trigger cooldown/no further HTTP requests to that hostname in the same stage
