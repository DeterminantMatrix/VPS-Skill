---
name: reality-sni-selector
description: Compare, validate, and optionally roll out REALITY target/SNI profiles for VPS nodes using Xray, sing-box, mihomo, x-ui/3x-ui, or ShellCrash. Use when selecting or replacing REALITY serverName/target/dest/handshake.server, comparing candidate domains, checking REALITY compatibility, investigating target-specific handshake failures, or safely changing a production REALITY SNI.
---

# REALITY SNI Selector

## Goal

Choose a REALITY target/SNI that works with the user's actual server core, client core, network path, and fingerprint. Keep the workflow short and evidence-driven.

Treat a candidate as a **profile**, not just a domain:

```text
(target host:port, SNI, server core/version, client core/version, fingerprint, address family)
```

A domain is not good or bad in isolation. Implementation interoperability can change the result.

## Core rules

- Keep the incumbent as the control whenever it currently works.
- Preserve exact hostnames. Do not silently add or remove `www`.
- Keep server `target`/`dest`/`handshake.server` and allowed/client `serverName` consistent unless the implementation intentionally separates them.
- Prefer the XTLS target profile: TLS 1.3, ALPN `h2`, valid certificate for the SNI, and X25519 compatibility.
- A wildcard certificate is not an automatic rejection if normal certificate verification accepts the requested SNI.
- **Strict no-CDN policy:** confirmed CDN or shared platform front doors are a hard rejection. This includes Cloudflare, CloudFront/AWS shared fronts, Akamai, Fastly, Azure Front Door/CDN, and comparable shared edge services.
- Decide CDN/front-door status from DNS/CNAME, resolved IP/ASN/provider, and other concrete network evidence. Do not reject by brand-like substrings alone.
- If CDN/front-door status is still unknown, the candidate cannot be Primary until it is verified as direct.
- Redirects, famous/sensitive brands, network distance, and wildcard certificates remain risk or tie-breaker evidence unless they cause an actual protocol/config failure.
- Do not rank a target from scanner output alone. For finalists, test REALITY with the actual core pair when possible.
- If every candidate fails similarly, investigate core/version/fingerprint/config interoperability before blaming the SNI.
- Do not expose UUIDs, private keys, short IDs, proxy passwords, panel credentials, tokens, or full secret-bearing configs.
- Make production changes only when explicitly requested or authorized.

## Skip by default

Do **not** perform these unless the user specifically asks or troubleshooting requires them:

- browser inspection;
- website text/content-size scoring;
- organization type scoring;
- target traffic-volume estimation;
- mandatory same-ASN or same-provider requirements;
- certificate remaining-days thresholds beyond normal certificate validity;
- fixed 100-point scoring;
- mandatory multi-window or exhaustive discovery rounds;
- large web-research sweeps after a clear winner exists.

## Inputs

Infer what is already available. Only gather information that changes the result:

- VPS/region and actual address family;
- server core and version: Xray, sing-box, panel-managed Xray, or other;
- client core and version: mihomo, sing-box, Xray, etc.;
- current target/SNI and whether it works;
- candidate list or scanner output if available;
- actual client fingerprint;
- whether this is comparison-only or an authorized live change.

## Workflow

### 1. Build a small candidate pool

Use the incumbent plus candidates from existing scan results, RealiTLScanner/RealityChecker, or focused discovery. Read [references/discovery.md](references/discovery.md) only when candidates must be discovered.

Keep roughly 5-12 plausible candidates for the cheap probe. Do not chase arbitrary category quotas.

### 2. Run the target probe

Use the bundled probe from the VPS or an equivalent test from the same network path:

```bash
python3 scripts/probe_target.py <DOMAIN...>
```

Record:

- TLS 1.3;
- ALPN `h2`;
- normal certificate/SNI verification;
- X25519 probe result;
- remote IP;
- CNAME chain and best-effort ASN/provider evidence;
- CDN/shared-front-door classification;
- one HTTP `HEAD` status and redirect target when available.

Reject a candidate from the normal pool when TLS 1.3, `h2`, certificate/SNI verification, or X25519 compatibility clearly fails. Also reject any candidate confirmed as a CDN/shared platform front door. If directness is unknown, do not promote it to a finalist until verified.

Keep at most 2-4 **verified-direct** finalists.

### 3. Test actual REALITY interoperability

For each finalist, use an isolated temporary listener/client or another safe test with the **actual server and client core family** when practical.

Record only:

```text
server_core/version
client_core/version
fingerprint
candidate
success/failure
error class
```

Interpretation rules:

- If one target fails while another succeeds under the same core pair and fingerprint, treat the failure as target-specific evidence.
- If all targets fail, check server/client version compatibility, REALITY client-version handling, key/short-id pairing, clock, fingerprint, and config mapping before changing the ranking.
- A working real REALITY path overrides a contradictory generic scanner result.

### 4. Benchmark TLS handshakes only

For finalists and the incumbent, avoid downloading pages. Measure fresh TCP + TLS handshakes:

```bash
python3 scripts/benchmark_tls.py --rounds 8 --family ipv4 <INCUMBENT> <FINALIST...>
```

Use the address family that production actually uses. Compare:

- success rate;
- TCP p50/p95;
- TLS-handshake p50/p95/max;
- remote IP stability.

Do not over-read tiny differences. Prefer p95/stability over a few milliseconds of p50.

### 5. Rank with simple gates

Use this order:

1. CDN/front-door status is verified `direct`;
2. recommended target profile passes;
3. actual REALITY succeeds under the tested core pair;
4. stable low TLS p95 and failure rate;
5. fewer remaining risk flags;
6. network proximity is a tie-breaker;
7. keep the incumbent when candidates are effectively tied.

Hard rejection flags:

- `cdn/shared-front-door` — confirmed shared CDN/edge/platform front door;
- `cdn-unknown` — not eligible for Primary until directness is verified.

Other risk flags:

- `redirect` — especially an unrelated cross-host redirect;
- `famous/sensitive-target` — blocking/fingerprinting policy risk;
- `far-network` — weaker camouflage/latency fit;
- `wildcard-cert` — less specific identity, but not invalid when verification passes;
- `implementation-interop` — result depends on a particular core/version combination.

### 6. Roll out only when authorized

Read [references/live-rollout.md](references/live-rollout.md) only for a live change.

## Fixed comparison table

Whenever comparing two or more domains, always use this exact column order:

| Rank | Domain | CDN/front door | TLS profile | REALITY | TCP/TLS p50-p95 | Target IP / network | Risk flags | Pros | Cons | Verdict |
|---:|---|---|---|---|---|---|---|---|---|---|

Formatting rules:

- `CDN/front door`: use only `direct ✅`, `<provider> ❌`, or `unknown ⚠️`. A row with `❌` or `unknown ⚠️` cannot be Primary.
- `TLS profile`: compact form such as `1.3 ✅ · h2 ✅ · X25519 ✅ · cert ✅`.
- `REALITY`: state the tested core pair, e.g. `Xray→mihomo ✅`, or `not tested`.
- `TCP/TLS p50-p95`: show both when measured, e.g. `TCP 18/24 ms · TLS 31/42 ms`.
- `Target IP / network`: show the observed IP and only verified ASN/region/proximity facts.
- `Risk flags`: use `none` or short comma-separated flags.
- `Pros` and `Cons`: each should be concise and evidence-based.
- `Verdict`: use only `Primary`, `Backup`, or `Reject`.

Before the table, print only:

```text
Primary: <DOMAIN>
Reason: <one concise sentence>
```

After the table, if configuration mapping is relevant, print only the exact safe mapping:

```text
target/dest/handshake.server: <DOMAIN>:443
serverName/SNI: <DOMAIN>
Production: verified | not tested | rollback required
```

Do not bury the comparison in a long narrative unless the user asks for analysis.

## Stack notes

### Xray / x-ui / 3x-ui

Typical paired fields:

```text
target/dest: <DOMAIN>:443
serverNames: <DOMAIN>
client serverName/SNI: <DOMAIN>
```

Inspect the installed Xray version and REALITY version constraints before diagnosing SNI failures. Do not assume non-Xray clients encode REALITY client-version fields identically.

### sing-box

Server conceptually pairs:

```text
tls.server_name: <DOMAIN>
reality.handshake.server: <DOMAIN>
reality.handshake.server_port: 443
```

Client uses the same intended `tls.server_name` plus the configured REALITY key/short ID and uTLS fingerprint.

### mihomo / ShellCrash

Treat mihomo as the REALITY **client implementation** in the profile. Verify its version and client fingerprint. If authentication fails against every target, investigate server/client interoperability before reselecting SNI.
