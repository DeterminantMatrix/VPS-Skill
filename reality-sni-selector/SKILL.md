---
name: reality-sni-selector
description: Compare, validate, grade, and optionally roll out REALITY target/SNI profiles for VPS nodes using Xray, sing-box, mihomo, x-ui/3x-ui, or ShellCrash. Use when selecting or replacing REALITY serverName/target/dest/handshake.server, comparing candidate domains, checking REALITY compatibility, investigating target-specific handshake failures, or reducing known GFW-blocking risks for a production REALITY node.
---

# REALITY SNI Selector

## Goal

Choose a stable REALITY target/SNI for the user's actual server, client, and network path while minimizing known deployment risks. Keep the workflow short and fail fast.

A grade estimates production suitability for the tested profile. It does not guarantee that a VPS will never be detected or blocked.

Treat each candidate as a profile:

```text
(target host:port, SNI, server core/version, client core/version, fingerprint, address family, client network path)
```

## Hard rules

- Keep the working incumbent as the control.
- Preserve exact hostnames. Do not silently add or remove `www`.
- Keep server target/dest/handshake.server and allowed/client serverName consistent unless the implementation intentionally separates them.
- Require TLS 1.3, ALPN h2, normal certificate/SNI verification, and X25519 compatibility.
- Confirm the target is direct/non-CDN before it can become a finalist.
- Reject confirmed shared CDN or platform front doors, including Cloudflare, CloudFront/AWS shared fronts, Akamai, Fastly, Azure Front Door/CDN, and comparable shared edge services.
- Treat unknown CDN/front-door status as unverified. It cannot be Primary or receive S/A.
- In strict GFW-risk mode, require the production REALITY listener to use TCP/443 before any candidate can receive S/A/B. A non-443 production listener makes the current deployment grade C until corrected.
- Reject targets explicitly matching current Xray high-risk warning patterns: `.cn`, `.ru`, `.ir`, or hostnames containing `apple`, `icloud`, or `microsoft`.
- Reject unrelated cross-host redirects. Allow only the ordinary apex-to-`www` form for the same registrable site, and cap that candidate at A.
- Never perform broad discovery scans from the production VPS. Use a local machine or a separate non-production host for broad scanning. The production VPS may probe only the small shortlist.
- Do not lower or weaken REALITY client-version constraints merely to make a client connect. If all targets fail similarly, diagnose core/version/fingerprint/config interoperability first.
- Do not expose UUIDs, private keys, short IDs, passwords, panel credentials, tokens, or full secret-bearing configs.
- Make production changes only when explicitly requested or authorized.

## Skip by default

Do not perform these unless troubleshooting specifically requires them:

- browser inspection;
- website content-size or organization-type scoring;
- target traffic-volume estimation;
- fixed 100-point scoring;
- mandatory same-ASN/provider requirements (same ASN is a preference, never a hard gate);
- mandatory multi-window convergence;
- large web-research sweeps after a clear winner exists.

## Inputs

Infer what is already available. Gather only facts that change the result:

- production REALITY listener port;
- VPS region, production address family, and VPS public ASN (or public IP so the ASN can be resolved);
- server core/version;
- client core/version;
- current target/SNI and whether it works;
- client fingerprint;
- candidate list or scanner output if available;
- whether a real mainland-China client path is available for validation;
- whether this is comparison-only or an authorized live change.

## Workflow

### 0. Server posture gate

Before selecting a new SNI:

1. Confirm the production REALITY listener uses TCP/443.
2. Record server core/version and client core/version.
3. Confirm clocks are sane and the incumbent is known.
4. Record the VPS ASN when available; use it only as a post-gate ranking preference.
5. If every candidate fails in the same way, stop SNI ranking and diagnose implementation interoperability.

For Xray, do not automatically relax `minClientVer` or equivalent version checks to work around a client mismatch.

### 1. Build a small candidate pool

Use the incumbent plus existing scan results or focused discovery. Read [references/discovery.md](references/discovery.md) only when candidates must be discovered.

Keep about 5-12 plausible candidates for the cheap probe. Broad scans must run away from the production VPS.

### 2. Run the target gate

Use the bundled probe from the production VPS against only the shortlist:

```bash
python3 scripts/probe_target.py --family ipv4 --vps-asn <VPS_ASN> <DOMAIN...>
```

Use the production address family.

Record:

- TLS 1.3;
- ALPN h2;
- certificate/SNI verification;
- X25519;
- remote IP;
- CNAME chain and ASN/provider evidence;
- whether all observed target addresses are in the same ASN as the VPS;
- CDN/shared-front-door status;
- redirect status;
- high-risk target warning.

Reject a candidate if any hard gate fails. Keep at most 2-3 verified-direct finalists.

### 3. Test actual REALITY from the real client path

For each finalist, test the actual server/client core pair and fingerprint from the real production client path. For the strict GFW-oriented grade, use a mainland-China network path.

Make 5 fresh REALITY connection attempts when practical. Record only:

```text
server_core/version
client_core/version
fingerprint
candidate
china_path_successes/attempts
error class
```

Rules:

- No mainland-China path evidence means the candidate grade is capped at B.
- 5/5 is required for S.
- 4/5 can qualify for A if all other hard gates pass.
- Repeated target-specific failures make the candidate C.
- If every candidate fails similarly, classify it as implementation/environment failure instead of blaming the SNI.

### 4. Run the small TLS stability benchmark

Benchmark only the incumbent and finalists:

```bash
python3 scripts/benchmark_tls.py --rounds 8 --family ipv4 <INCUMBENT> <FINALIST...>
```

Measure fresh TCP plus TLS handshakes only. Do not download pages.

Compare:

- success rate;
- TCP p50 and worst;
- TLS p50 and worst;
- observed target IP set.

Do not calculate or report p95 from this small sample. Prefer reliability over tiny median differences.

### 5. Assign S/A/B/C

Grade the tested profile, not the domain in isolation.

#### S - Preferred Primary

Require all of the following:

- production REALITY listener is TCP/443;
- direct/non-CDN status is verified;
- TLS 1.3, h2, certificate verification, and X25519 all pass;
- no high-risk target warning;
- no redirect;
- actual mainland-China REALITY path succeeds 5/5 with the real core pair/fingerprint;
- TLS stability benchmark succeeds 100%;
- no material implementation or network risk remains.

S should be rare.

#### A - Production acceptable

Require all hard gates to pass and real mainland-China path evidence. Use A when the profile is production-suitable but has a minor imperfection, such as:

- China path succeeds 4/5 rather than 5/5;
- wildcard certificate with valid normal hostname verification;
- allowed apex-to-`www` redirect;
- slightly worse but still stable latency/network fit.

A may be Primary when no S candidate exists.

#### B - Backup or incomplete evidence

Use B when the target gate passes but production confidence is incomplete, for example:

- no real mainland-China path test yet;
- actual REALITY interoperability not yet verified;
- directness or implementation evidence needs one more manual confirmation;
- stability is acceptable but materially weaker than the incumbent.

B is Backup only, never Primary in strict mode.

#### C - Reject for this deployment

Use C for any hard rejection or current-environment incompatibility, including:

- confirmed CDN/shared front door;
- CDN/front-door status unknown after reasonable checks;
- non-443 production REALITY listener;
- TLS 1.3/h2/certificate/X25519 failure;
- Xray high-risk target warning pattern;
- unrelated cross-host redirect;
- repeated target-specific REALITY failures;
- unresolved server/client incompatibility that prevents production use.

When C is caused by implementation incompatibility, state that it is not evidence that the SNI itself is intrinsically bad.

### 6. Apply preference fit within the same grade

After assigning S/A/B/C, calculate a simple **Preference fit** score only for ordering candidates inside the same grade:

- `+2 same-ASN` — all observed target IPs with known ASN are in the same ASN as the VPS;
- `+1 preferred-institution` — the hostname belongs to a verified university, research institute, library, museum, nonprofit, NGO, public research body, or public cultural institution;
- `0` otherwise.

Rules:

- Preference fit never changes S/A/B/C.
- Preference fit never rescues a CDN/shared-front-door or other C candidate.
- Same ASN is stronger than institution type because it directly improves network topology plausibility, but it remains only a tie-breaker.
- Do not infer institution type from `.edu`, `.org`, or a brand-like name alone. Use verified organization identity.
- If candidates have the same grade and Preference fit, prefer higher REALITY success, then lower TLS worst-case latency, then the working incumbent.

Examples:

```text
3/3 = same ASN + preferred institution
2/3 = same ASN only
1/3 = preferred institution only
0/3 = neither
```

### 7. Roll out only when authorized

Read [references/live-rollout.md](references/live-rollout.md) only for an authorized live change.

## Fixed comparison table

Whenever comparing two or more candidates, always use this exact column order:

| Rank | Grade | Domain | CDN/shared | TLS profile | REALITY / CN path | TLS stability | Target IP / network | Preference fit | Pros | Cons | Verdict |
|---:|:---:|---|---|---|---|---|---|---|---|---|---|

Formatting rules:

- `Grade`: only `S`, `A`, `B`, or `C`.
- `CDN/shared`: only `direct`, `<provider> REJECT`, or `unknown`.
- `TLS profile`: compact form such as `1.3 ok / h2 ok / X25519 ok / cert ok`.
- `REALITY / CN path`: include tested core pair and result, e.g. `Xray->mihomo / CN 5/5`.
- `TLS stability`: `success rate / TLS p50 / worst`, e.g. `100% / 31 ms / 45 ms`.
- `Target IP / network`: show observed IPs, target ASN, VPS ASN, and whether the ASN matches when verified.
- `Preference fit`: show `0/3` to `3/3` plus short evidence, e.g. `3/3 same-ASN + university`.
- `Pros` and `Cons`: concise, evidence-based.
- `Verdict`: only `Primary`, `Backup`, or `Reject`.

Before the table print only:

```text
Primary: <DOMAIN> (<GRADE>)
Reason: <one concise sentence>
```

If no S/A candidate exists, print:

```text
Primary: none
Reason: no candidate has enough verified production evidence.
```

After the table, if config mapping is relevant, print only:

```text
target/dest/handshake.server: <DOMAIN>:443
serverName/SNI: <DOMAIN>
Production: verified | not tested | rollback required
```

Do not bury the result in a long narrative unless the user asks for analysis.

## Stack notes

### Xray / x-ui / 3x-ui

Typical paired fields:

```text
target/dest: <DOMAIN>:443
serverNames: <DOMAIN>
client serverName/SNI: <DOMAIN>
```

Inspect the installed Xray version and REALITY version constraints before diagnosing SNI failures. Do not assume other clients encode REALITY client-version fields identically. Do not automatically reduce the server's client-version floor as a compatibility workaround.

### sing-box

Server conceptually pairs:

```text
tls.server_name: <DOMAIN>
reality.handshake.server: <DOMAIN>
reality.handshake.server_port: 443
```

Client uses the same intended `tls.server_name` plus the configured REALITY key/short ID and uTLS fingerprint.

### mihomo / ShellCrash

Treat mihomo as part of the tested REALITY profile. Verify its version and fingerprint. If authentication fails against every candidate, investigate server/client interoperability before reselecting SNI.
