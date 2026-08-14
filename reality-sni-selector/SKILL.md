---
name: reality-sni-selector
description: Choose, compare, validate, grade, and safely roll out TLS SNI/target domains for VPS nodes using Xray REALITY, VLESS Reality, sing-box Reality, 3x-ui/x-ui, or raw Xray. Use when Codex needs to discover or replace serverName/dest/handshake.server candidates, interpret RealiTLScanner or RealityChecker, reject parked or implausibly small targets, inspect certificates/CDN/ASN/latency and website traffic plausibility, run paced incumbent-versus-challenger tests, judge convergence, verify real user paths, or perform reversible SNI changes.
---

# 优选 SNI

## Goal

Select a practical REALITY target for one VPS and keep these conclusions separate:

- **Compatibility**: TLS/X25519 and ordinary HTTPS work.
- **Production qualification**: every A-grade hard gate passes on the real path.
- **Search convergence**: mandatory coverage and fair multi-window comparison show that further searching has low expected value.
- **Durability**: a later window, at least six hours after qualification, still passes.

Never translate one conclusion into another. An A grade is not proof of optimality, convergence, or long-term stability.

## Non-negotiable rules

- Work from the actual VPS, stack, incumbent SNI, and user path.
- Keep exact hostnames. Do not add or remove `www`.
- Pair server `dest`/`handshake.server` with server and client `serverName`.
- Use a staged fail-fast pipeline: cheap DNS/TLS/front-door gates first, browser and 5-sample HTTPS second, 20-round tournament only for finalists, and real REALITY testing last.
- When the request says no CDN, use `selection_mode: strict_no_cdn`: a known CDN, platform front door, or shared CDN CNAME cannot be a Primary candidate. Do not spend browser or benchmark budget on it.
- For a Primary candidate, explicitly verify TLS 1.3 and ALPN `h2`; `compatibility_pass: true` alone is insufficient evidence.
- Prefer a stable exact-SAN website operated by a university, library, museum, research institute, research center, think tank, nonprofit, or public organization; prefer the same ASN when the organization and website gates also pass. This is a tie-breaker, not a substitute for protocol or certificate gates.
- Treat RealityChecker as a first-pass filter, not final proof.
- Keep the incumbent in every serious comparison.
- Treat the target website as an operational dependency. REALITY can create target-side TLS handshakes and forward invalid connections; proxy payload volume is not the same as target traffic.
- Reject parked, blank, default, abandoned, for-sale, maintenance-only, and one-logo holding pages as primaries even when latency is excellent.
- Treat static technology as neutral. Judge meaningful content, ongoing operation, and plausible traffic scale.
- Filter weak sites before high-sample tests. Pace requests, never parallel-flood one target, and stop on `429`, `Retry-After`, repeated `403/5xx`, resets, or distress signals.
- Scan only the VPS `/24` or another explicitly authorized range.
- Make live changes only when the user explicitly requests or authorizes them.
- Never expose UUIDs, private keys, short IDs, proxy passwords, panel credentials, tokens, or complete secret-bearing configs.

## Inputs

Collect or infer:

- VPS alias/IP, provider, ASN, region, OS/architecture, and SSH method.
- Stack: sing-box, Xray, x-ui/3x-ui, or unknown.
- Incumbent SNI and whether it currently works.
- Existing scan results or candidate lists.
- Actual path: client/router, relay, landing/exit, policy groups, tunnels, and dependent configs.
- Requested scope: quick selection, serious reselection, isolated test, or live rollout.
- Selection mode: `balanced`, `strict_no_cdn`, or `production`; default to `strict_no_cdn` when the user asks for a non-CDN target.
- Organization preference: same-ASN preferred institution first, then same-ASN other organization, then same-region preferred institution, then other suitable direct sites.

Ask only for information that blocks safe progress. Prefer known inventory aliases and key paths; never ask the user to paste secrets already available locally.

## Workflow

### 1. Inspect the incumbent and path

Read current server and client SNI fields, service/listener state, selected policy groups, and dependency locations. Record only safe fields. Use the incumbent as the control.

### 2. Discover a closed candidate pool

For serious selection or a request to find something better, read [references/discovery.md](references/discovery.md). Complete the authorized `/24`, same-provider evidence, regional organizations, universities/research, B2B/service providers, and community/institutional categories. Do not stop at the first attractive candidate.

Clean scan artifacts with:

```powershell
python "<SKILL_DIR>\scripts\clean_reality_candidates.py" "<INPUT>" --out "<OUTPUT>" --strict --show-rejects
```

Before any browser or high-sample test, apply the cheap gate in this order:

1. exact SAN and certificate validity;
2. TLS 1.3 and ALPN `h2`;
3. DNS/CNAME/front-door/CDN evidence;
4. distress status, WAF, redirect count, and final-host relationship;
5. stable A/AAAA and rough ASN/region fit.

Drop candidates that fail a hard gate. Keep no more than 3–5 candidates per node for the browser pass, and no more than 2–3 challengers for the first 20-round tournament.

### 3. Run compatibility filtering

Use RealityChecker or manual TLS checks from the VPS to reduce the pool. Preserve the requested hostname, certificate hostname, redirect destination, and checker-reported final domain as distinct values.

Scanner success is only compatibility evidence. A working real REALITY path overrides a conflicting scanner result.

For every finalist, record `tls_version`, `alpn`, `certificate_identity`, `redirect_count`, `final_host_relation`, and `front_door`. A missing TLS version or ALPN result prevents a candidate from being Primary.

### 4. Apply certificate, network, website, organization, and traffic gates

For every serious finalist, read [references/site-traffic-gate.md](references/site-traffic-gate.md).

- Inspect the exact SAN list and require an explicit exact hostname for A.
- Resolve current addresses and document ASN, region, hosting, CDN/Anycast, and mismatches.
- Classify the organization: `preferred-institution`, `same-asn-preferred-institution`, `same-asn-other`, `commercial`, or `unknown`. Prefer universities, libraries, museums, research institutes/centers, think tanks, nonprofits, charities, and public organizations; never let this preference override a hard protocol, certificate, WAF, or front-door failure.
- Open the exact hostname in a real browser once and inspect rendered content.
- Estimate current REALITY connection activity when a production node exists.
- Reject or downgrade candidates whose site scale cannot plausibly absorb the expected handshake pattern.

Use the deterministic first-pass helpers:

```bash
python "<SKILL_DIR>/scripts/inspect_site_footprint.py" <DOMAIN...>
python "<SKILL_DIR>/scripts/inspect_tls_profile.py" <DOMAIN...>
python3 "<SKILL_DIR>/scripts/observe_connection_rate.py" --port 443 --seconds 20
```

The footprint script does not replace browser inspection.

### 5. Predeclare finalists and run a fair tournament

Read [references/benchmark-convergence.md](references/benchmark-convergence.md). Fix the incumbent, two to three challengers after the strict cheap gate, address family, redirect policy, request count, pacing, endpoints, timeouts, and rejection thresholds before testing.

Run the on-box benchmark from the target VPS:

```bash
python3 benchmark_https.py --rounds 20 --pace 0.5 <INCUMBENT> <CHALLENGER...>
```

Do not add a preference after seeing results. Rerun the same pool if the finalists change materially.

To save request and token budget, use the first window to rank the fixed pool, then use a second comparable window only for the incumbent, winner, and runner-up. Do not claim convergence unless the required windows and expansion coverage are complete.

### 6. Grade with fixed evidence

Create one JSON evidence object per finalist and run:

```bash
python "<SKILL_DIR>\scripts\score_candidate.py" evidence.json
```

The script enforces fixed weights and hard gates. Do not manually promote a candidate above its computed hard-gate ceiling. Add human explanations for each input; never submit unsupported guesses as evidence.

### 7. Test REALITY

Test in this order:

1. Direct target TLS/HTTPS from the VPS.
2. Isolated temporary REALITY listener and client.
3. Actual client/router path to at least two independent external endpoints.
4. Five consecutive successes through the real selected policy path.

Selection-only work normally stops at B. A requires the synchronized production path, active services, and rollback evidence.

### 8. Roll out only when authorized

For a live change, read [references/live-rollout.md](references/live-rollout.md). Back up all affected server and client configs, validate staged configs before applying, update paired fields as one coordinated change, preserve policy selections, verify listeners/logs, and roll back every affected node if any hard gate fails.

## Grades

- **A — production-qualified**: exact certificate, acceptable network/site/traffic evidence, stable HTTPS, real path to two endpoints, five consecutive successes, synchronized dependencies, active services, and rollback all pass.
- **B — validated candidate**: manual gates pass, but production synchronization or actual user-path evidence is incomplete.
- **C — compatibility backup**: connects but has a documented compromise such as wildcard/shared identity, placeholder or implausible site footprint, region/front-door mismatch, or unstable behavior.
- **D — rejected**: certificate, TLS, HTTP, reachability, or real proxy path fails.

Report evidence maturity separately:

- `single-window`
- `cross-window` for two comparable windows at least 30 minutes apart
- `durable` only after another successful window at least six hours later

## Stop conditions

Mark search convergence only when:

1. At least one A-grade candidate exists.
2. Mandatory discovery coverage is complete.
3. The incumbent and finalists completed identical head-to-head tests.
4. Two timing windows agree on the winner or show no material difference.
5. Two consecutive expansion rounds found no materially better challenger.
6. The winner passed the website and target-traffic plausibility gate.

Otherwise report `not assessed` or `provisional`. If exhaustive discovery produces no A, preserve the incumbent and report the failed gates without lowering the standard.

## Selection policy

### Hard gates before expensive work

Do not open a browser or run a 20-round benchmark for a candidate that lacks any of the following:

- explicit exact SAN for the requested hostname;
- currently valid certificate;
- TLS 1.3 and ALPN `h2` evidence;
- no known CDN/shared platform front door when `selection_mode: strict_no_cdn`;
- no repeated `403`, `429`, `5xx`, resets, or WAF challenge;
- no unrelated or multi-hop redirect;
- stable DNS/IP evidence.

### Organization preference

Use organization and ASN as a preference after hard gates:

1. same-ASN preferred institution;
2. same-region preferred institution;
3. same-ASN other suitable organization;
4. same-region direct suitable organization;
5. other direct candidates.

Preferred institutions include universities, libraries, museums, research institutes, research centers, think tanks, nonprofits, charities, and public organizations. The preference is a tie-breaker only; an institution with a bad certificate, CDN front door, unstable TLS, WAF, placeholder page, or implausible traffic remains rejected.

### Cost-control rule

Be strict about identity, TLS, ALPN, front-door risk, and distress signals. Use graded evidence for latency, site size, ordinary hosting technology, and a single same-organization redirect. This avoids false negatives while reserving browser, benchmark, and REALITY-path resources for candidates that can actually qualify.

## Stack mappings

### sing-box

Server:

```json
"tls": {
  "enabled": true,
  "server_name": "<DOMAIN>",
  "reality": {
    "enabled": true,
    "handshake": {"server": "<DOMAIN>", "server_port": 443},
    "private_key": "<PRIVATE_KEY>",
    "short_id": ["<SHORT_ID>"]
  }
}
```

Client:

```json
"tls": {
  "enabled": true,
  "server_name": "<DOMAIN>",
  "utls": {"enabled": true, "fingerprint": "chrome"},
  "reality": {"enabled": true, "public_key": "<PUBLIC_KEY>", "short_id": "<SHORT_ID>"}
}
```

### Xray / x-ui / 3x-ui

```text
dest: <DOMAIN>:443
serverNames: <DOMAIN>
client sni/serverName: <DOMAIN>
```

Do not confuse the REALITY public key with an SSH key or the target website certificate key.

## Output contract

Lead with:

```text
Primary: <DOMAIN>
Grade: A | B | C | D
dest/handshake.server: <DOMAIN>:443
serverName: <DOMAIN>
Validation: <exact missing or passed gate>
```

For serious work also report:

- coverage by candidate category;
- certificate and remaining validity;
- IP/ASN/region/CDN evidence;
- TLS version, ALPN, redirect relationship, front-door type, organization category, and same-ASN preference evidence;
- website footprint and traffic plausibility;
- HTTPS count, pacing, statuses, TLS p50/p95/max;
- isolated and production REALITY results;
- dependencies, service state, and rollback;
- evidence maturity and convergence state;
- exact validation request budget.

## Saved inventory and troubleshooting

Obtain the target's safe inventory, SSH alias, path, and dependent configs through `$vps-manager` preflight. If direct inventory access is still necessary, read only the target entry from:

```text
D:\WPS SyncDisk\2.Tool\0.March\5.VPS\KV.yaml
```

Prefer aliases and key paths. If a stack or path changes, remap the chosen hostname without silently re-ranking. If RealityChecker and the real path disagree, preserve the working production target while investigating exact SNI pairing, DNS family, routing, clock, flow, fingerprint, and implementation/version differences.
