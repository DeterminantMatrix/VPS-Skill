---
name: reality-sni-selector
description: Select and verify VLESS Reality SNI / handshake targets for one owned VPS. Use for 优选 SNI, Reality SNI selection, VLESS Reality camouflage/handshake target selection, current-SNI health evaluation, or comparison of serverName/dest/handshake candidates. Resolve the VPS from the local inventory and existing SSH alias, ensure the reviewed managed target worker is current, perform discovery/network measurements on the target VPS, reject unsafe/incompatible targets, validate finalists with isolated sing-box Reality tests, and return an evidence-rich ranked portfolio.
---

# 优选 SNI

Use the controller as control plane and the selected VPS as measurement plane.

## Non-negotiable rules

- Handle one explicit owned VPS per run. Resolve `inventory/hosts.yaml` first, with `/opt/vps-control/inventory/hosts.yaml` only as legacy fallback. Accept a public IPv4, exact inventory identifier/SSH alias/name, or one uniquely high-confidence fuzzy name; fail ambiguous matches. See `references/inventory-contract.md`.
- Use only the declared existing SSH alias. Never construct `root@IP`, infer management access from Komari/telemetry, or rebuild SSH credentials from inventory facts.
- Run all candidate discovery, DNS, TCP/443, TLS, HTTP-header, ASN/platform/CDN, latency and Reality measurements on the target VPS. IPv4/TCP 443 only; no CIDR/port scan, MTR, traceroute, iperf3, throughput, streaming or webpage-body download.
- Do not change production sing-box/SNI, services, firewall, routes, SSH or networking. Normal selection may install/upgrade only the reviewed managed worker paths after ownership/hash checks. Never overwrite unknown content or install system packages. See `references/safety-boundaries.md` and `references/worker-lifecycle.md`.
- Freeze the profile, worker manifest, target identity, region, incumbent mode, seed set, limits and timestamps only after exact worker readiness.
- Missing evidence never proves a direct origin. Low latency or Reality compatibility never rescues a Protocol/Policy hard rejection.
- Never print/persist passwords, private keys, UUIDs, Reality private keys, short IDs, tokens, cookies or full secret-bearing proxy configs.

## Normal invocation

```text
python3 scripts/controller_run.py <inventory-target>
```

Optional controls:

```text
--inventory <inventory/hosts.yaml>
--incumbent <hostname>
--seed-file <fixed-region-seed-file>
--profile audit
--worker-bootstrap never
--worker-ready-only
```

Default to QUICK. Use AUDIT only when the user explicitly requests broader/deeper coverage. Auto-resolve the incumbent read-only from the live sing-box config; if unavailable/ambiguous, require `--incumbent`. Never substitute a universal default SNI.

## Workflow

1. **Inventory guard** — resolve canonical inventory ID, public IPv4, region and SSH alias; record fuzzy-match evidence; reject retired/forbidden/non-SSH targets.
2. **Worker readiness before freeze** — probe `/usr/local/bin/reality-sni-target-worker identity`. Require protocol 4, implementation 4.5, exact six-file manifest and reviewed wrapper hash. Auto-install/upgrade only absent or proven managed/known-legacy worker paths; unknown content => `WORKER_PATH_CONFLICT`. See `references/worker-lifecycle.md` and `references/target-worker-install.md`.
3. **Freeze and measure** — after READY, freeze the v4.5 job and invoke exactly `/usr/local/bin/reality-sni-target-worker run` through the existing alias, sending JSON on stdin. Candidate measurement uses one fixed worker process.
4. **Preflight/incumbent** — observe target egress/location/ASN/tooling, resolve the current REALITY target from live sing-box config when possible, and fail closed on zero/multiple targets. See `references/incumbent.md`.
5. **Multi-lane discovery** — combine General Regional, Network Affinity, Institutional preference and bounded Passive Expansion. Institution is a preference, not the candidate universe. Network Affinity uses RIPEstat + tiny Shodan InternetDB passive samples only; never sweep ASN/CIDR. Filter common social/profile/aggregator URLs only as Regional/Institutional source hygiene. Apply source/validated lane reserves before global caps so General Regional cannot starve smaller lanes. See `references/candidate-discovery.md`.
6. **Eligibility** — require REALITY Protocol minimum: public IPv4/TCP443, valid certificate/SNI identity, TLS1.3, ALPN h2, and no confirmed cross-site redirect. Keep public CDN/shared platform as this project's stricter safety hard policy. Unknown edge evidence remains REVIEW. See `references/evaluation-model.md` and `references/rejection-codes.md`.
7. **Fast/Deep** — preserve diversity and bounded Network-Affinity opportunity. QUICK Fast 36x3, initial Deep 10, 20 total Deep samples with Fast reuse. Refill in batches of 4, preferring new registrable-domain families. See `references/benchmark.md`.
8. **Reality integration** — test incumbent control first, then only `ELIGIBLE` Deep survivors. A candidate is `SELECTABLE` only with 5/5 transport and 5/5 cleanup. Cleanup uncertainty => `TARGET_DIRTY_STATE`. This is a target-local integration test, not a real client-path test. See `references/reality.md`.
9. **Portfolio + quality stop** — main Top-5 requires five independent registrable-domain families; apex/`www` variants remain `family_alternatives`. Normal early success also requires at least one selectable candidate meeting the frozen quality target. If five valid families exist but bounded search cannot meet quality, return `SUCCESS_QUALITY_BELOW_TARGET` rather than pretending the quality goal was met.
10. **Decision/reporting** — assess incumbent with the same Protocol/Policy/Reliability/Reality evidence. Keep Candidate Confidence, Run Coverage Confidence and Global Optimality Confidence separate. Separate TLS reliability, Reality reliability and Latency Consistency; do not turn one-run latency spread into a durability claim. See `references/incumbent-assessment.md`, `references/result-schema.md`, and `references/reporting.md`.

## QUICK defaults

- discovery: source cap 520, validated cap 240, breadth goal 200, effective `ELIGIBLE` goal 15; bounded source/validated lane reserves; Network Affinity <=24 passive IP lookups across <=4 announced prefixes.
- measurement: eligibility 80, Fast 36x3, initial Deep 10, Deep cap 22, refill 4, 20 total Deep samples with Fast reuse, Reality cap 20, target 5 independent families.
- quality target: P50 <=60 ms, or near-quality P50 <=1.25x target + P95 <=1.60x + MAD <=7.5 ms + TLS success >=95%. It is a search-stop/quality label, not an eligibility hard gate.
- ranking: Protocol/Policy/Reality/Reliability first; treat <=2 ms P50 difference as near-tie and use P95, MAD/Latency Consistency, Network Affinity and operational evidence to break it.

AUDIT keeps the same architecture with source 1,200, validated 600, eligible goal 25, eligibility 120, Fast 50x5, initial Deep 10, Deep cap 24, Reality cap 22 and broader passive-affinity limits.

## Required outputs

Normal runs write structured lifecycle and measurement artifacts plus `report.md`, including `worker-lifecycle.json`, frozen/preflight/result JSON, `candidate-discovery.json`, `network-affinity-search.json`, eligibility/rejections, Fast/Deep, Reality, incumbent assessment, `decision-summary.json`, `top5.json`, comparison, metadata and stage status. If readiness fails, blocked lifecycle artifacts may exist without a frozen run.

The final report must:

- state incumbent verdict and best alternative;
- show five independent SELECTABLE families when available, never duplicate a root-domain family to fill the table;
- include same-family alternatives, Protocol, TLS/ALPN, Policy, Reality, TLS reliability, P50/P95/MAD, Latency Consistency, Network Affinity, operational risk, ASN/org, incumbent delta and all confidence dimensions;
- show source/validated saturation, lane reserves, source errors, baseline-only count and SAME_ASN hostname/family/endpoint funnel;
- distinguish a fully measured candidate from claims of global optimality;
- never invent historical uptime, future stability, unseen CDN/ASN relationships or client-to-VPS performance.

## Bundled implementation

Controller: `controller_run.py`, `controller_runtime.py`, `controller_core.py`, decision/report modules and worker lifecycle/bootstrap modules. Target worker: fixed six-file manifest plus hash-verified auxiliary publication payloads for large modules. See `references/architecture.md`, `references/dependencies.md`, `references/maintenance.md`, and `references/migration-v4.4-to-v4.5.md`.
