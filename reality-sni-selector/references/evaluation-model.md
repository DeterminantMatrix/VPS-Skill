# REALITY target evaluation model v4.4

This Skill separates upstream REALITY target requirements from its own conservative operational policy. Do not describe project-specific heuristics as protocol requirements.

## Upstream basis

Primary references:

- XTLS/REALITY README: https://github.com/XTLS/REALITY/blob/main/README.en.md
- XTLS RealiTLScanner: https://github.com/XTLS/RealiTLScanner
- RealiTLScanner TLS feasibility implementation: https://github.com/XTLS/RealiTLScanner/blob/main/scanner.go
- Xray REALITY transport documentation: https://github.com/XTLS/Xray-docs-next/blob/main/docs/config/transports/reality.md

For ordinary proxy use, the XTLS REALITY README describes the target-site minimum as an overseas/non-GFW target that supports TLS 1.3 and H2 and is not used for redirecting, except that a main domain may redirect to its `www` form. It lists closer target IP, encrypted post-ServerHello handshake behavior, and OCSP Stapling as bonuses. The official RealiTLScanner marks a target infeasible when TLS is not 1.3 or ALPN is not `h2`. Current Xray documentation also recommends using a target/certificate in the same ASN when practical and warns that shared CDN targets can turn the REALITY fallback behavior into an unintended forwarding path.

## L0 — REALITY protocol minimum

A candidate cannot become `SELECTABLE` unless current target-side observations satisfy all available hard requirements:

- usable public IPv4 on TCP/443;
- valid certificate chain/time and SNI identity;
- TLS 1.3;
- ALPN `h2`;
- no confirmed cross-site redirect. Same-site/root-to-www redirect is accepted.

Codes: `HARD:NO_PUBLIC_IPV4`, `HARD:TLS_UNREACHABLE`, `HARD:CERT_INVALID`, `HARD:CERT_IDENTITY`, `HARD:REALITY_MIN_TLS13`, `HARD:REALITY_MIN_H2`, `HARD:REALITY_CROSS_SITE_REDIRECT`.

If redirect evidence cannot be observed, do not invent a PASS; preserve REVIEW/unknown evidence.

## L1 — safety and camouflage policy

Project policy is intentionally stricter than upstream minimum compatibility:

- confirmed shared public CDN/front door -> `HARD:KNOWN_PUBLIC_CDN`;
- confirmed shared managed platform/front door -> `HARD:KNOWN_SHARED_PLATFORM`;
- missing edge evidence never proves a direct origin.

These are safety/camouflage policy decisions, not claims that the underlying TLS target is technically incapable of REALITY.

### Network Affinity

Treat measured affinity as a preference, not a hard requirement:

1. `SAME_ASN` — strongest signal and aligned with current Xray best-practice guidance;
2. same observed organization or coarse IPv4 /16 proximity — project heuristic only;
3. same country — weak locality evidence;
4. different/unknown — no affinity bonus.

Affinity may break a near-tie only after protocol, safety, and reliability gates. A materially worse tail-latency/stability result must not be hidden by a same-ASN bonus.

## L2 — actual REALITY integration

Static TLS properties do not prove implementation compatibility. Require the isolated target-side sing-box Reality fixture to pass 5/5 transports with 5/5 cleanups for a candidate to become `SELECTABLE`. A clean first failure makes 5/5 impossible and may fail-fast that candidate. Dirty cleanup invalidates the run.

This is a local target-VPS integration test, not proof of a real client-to-VPS network path.

## L3 — reliability and performance

After L0/L1 pass:

- overall Deep TLS success must be >=95%;
- sufficiently sampled per-IP success must be >=90%;
- compare P50, P95, MAD, tail spread, per-IP consistency, and DNS volatility;
- use the frozen 2 ms P50 near-tie band to prevent tiny median differences from dominating the recommendation.

Keep protocol compliance separate from TLS reliability. A TLS transport can be 100% reliable and still fail REALITY protocol minimum because it negotiates TLS 1.2 or lacks H2.

## L4 — operational bonuses and heuristics

These may be shown as information/tie-break evidence but are not hard gates unless separately configured:

- OCSP Stapling — upstream bonus;
- X25519MLKEM768 support — current Xray can use it when the target supports it;
- durability/operational-risk heuristic derived from current DNS, front-door, source, organization, and stability evidence.

The current worker does not require OCSP or post-quantum key exchange for selection. Do not invent either value when it was not measured.

## Final precedence

Use this order:

1. REALITY protocol minimum;
2. safety/camouflage policy;
3. Reality integration and cleanup;
4. transport reliability;
5. performance and near-tie ranking;
6. Network Affinity and other evidence-bounded bonuses/heuristics.

Lower latency never rescues a hard failure in a higher layer.
