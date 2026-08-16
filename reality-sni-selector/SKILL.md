---
name: reality-sni-selector
description: Select and verify VLESS Reality SNI / handshake targets for one owned VPS. Use when the user asks for 优选 SNI, Reality SNI selection, VLESS Reality camouflage/handshake target selection, or comparison of serverName/dest/handshake candidates. Orchestrate from the controller but perform candidate discovery, DNS, TLS/CDN eligibility checks, latency benchmarking, and final sing-box Reality integration tests on the target VPS. Enforce bounded IPv4/TCP-443 probing, strict confirmed-public-CDN rejection, inventory/SSH guards, incumbent baseline comparison, structured evidence, and no production proxy/network changes.
---

# 优选 SNI

Use the controller only as the control plane. Treat the selected VPS as the measurement plane.

## Non-negotiable rules

- Handle one explicit VPS per run.
- Resolve the target from its inventory IPv4 through `/opt/vps-control/inventory/hosts.yaml`; derive and use the existing SSH alias and declared region. Never construct `root@IP`, guess aliases, or use an unrelated monitoring address as the SSH target.
- Run candidate discovery and every candidate-related DNS, TCP, TLS, HTTP-header, ASN/CDN, latency, and Reality measurement on the target VPS. Controller-side candidate measurements are not final evidence.
- Use IPv4 and TCP/443 only. Do not scan ports, CIDRs, arbitrary addresses, or arbitrary ports.
- Do not download page bodies. HTTP probes are bounded HEAD requests and header-only evidence.
- Do not run MTR, traceroute, iperf3, streaming tests, throughput tests, or unrelated quality probes.
- Do not modify production sing-box configuration, proxy services, firewall, routes, SSH, or networking.
- Normal runs must not upload scripts or construct arbitrary remote shell. The target must already expose the fixed `reality-sni-target-worker run` command. If it is absent, fail closed with `TARGET_WORKER_UNAVAILABLE`.
- Do not print or persist passwords, private keys, UUIDs, Reality private keys, short IDs, tokens, cookies, or complete secret-bearing proxy configs.
- Freeze the run profile, thresholds, counts, region, incumbent, seed set, and timestamps before the first candidate evaluation. Never change them mid-run to rescue a favored candidate.

Read `references/safety-boundaries.md` before changing any execution boundary.

## Inputs

Use the normal controller invocation:

```text
python3 scripts/controller_run.py <inventory-ipv4>
```

The controller resolves the existing SSH alias and declared region from inventory. The target worker resolves the current production Reality handshake/SNI read-only from fixed sing-box configuration locations before candidate evaluation. If automatic incumbent discovery is unavailable or ambiguous, fail closed and rerun with:

```text
python3 scripts/controller_run.py <inventory-ipv4> --incumbent <hostname>
```

A region seed file is optional:

```text
python3 scripts/controller_run.py <inventory-ipv4> --seed-file <fixed-region-seed-file>
```

Never substitute a universal Apple or other default incumbent.

## Workflow

1. **Inventory guard**
   - Accept the target inventory IPv4 as the normal user input.
   - Resolve exactly one active, allowed SSH-capable inventory entry and derive its existing alias/region.
   - Reject retired, forbidden, inactive, non-SSH, missing, or ambiguous targets.

2. **Freeze the run**
   - Load an optional fixed region seed list; absence is allowed because target-side regional metadata discovery remains available.
   - Freeze limits, target identity, region, seed set, and incumbent mode to `frozen-run.json` before SSH starts.
   - If incumbent mode is `auto`, the target worker resolves exactly one production Reality handshake hostname from fixed read-only sing-box paths and records it in `target-frozen-run.json` before candidate evaluation. Ambiguous or unavailable auto-discovery fails closed.
   - Read `references/incumbent.md` for the fixed read-only extraction boundary.

3. **One fixed SSH process**
   - Start exactly one remote process using the existing alias and fixed command `reality-sni-target-worker run`.
   - Send the frozen JSON job on stdin.
   - Do not pass user shell fragments or a user-controlled remote command.
   - Read `references/target-worker-install.md` only for a separately authorized one-time worker deployment; never deploy during selection.

4. **Target preflight and regional discovery**
   - Observe target egress IPv4 and target tool availability.
   - Resolve target-local location evidence from the target itself.
   - Build the bounded regional/institutional candidate pool on the target using fixed seeds plus bounded public metadata sources and passive CT.
   - If precise coordinates are unavailable, continue in region/seed mode with `LOCATION_DEGRADED`; do not silently fall back to the controller location.
   - Read `references/candidate-discovery.md`.

5. **Target eligibility gate**
   - Measure DNS and every current common IPv4 from the target.
   - Verify SNI TLS and hostname certificate validity.
   - Gather bounded CNAME/HTTP-header evidence for front-door classification.
   - Hard reject only correctness/safety failures such as no public IPv4, unreachable TLS, invalid/identity-mismatched certificate, or confirmed shared public CDN.
   - Treat TLS 1.3, h2, HTTP status, redirects, and unknown edge evidence as signals/review states rather than automatic hard rejection.
   - Read `references/gates.md` and `references/rejection-codes.md`.

6. **Target fast benchmark**
   - Retain at most 50 policy-eligible candidates, plus the incumbent baseline when needed.
   - Run 5 interleaved TCP+TLS samples per candidate from the target, balanced across common IPv4 addresses.
   - Use P50/MAD/max and success rate for coarse ranking. Do not use a 5-sample P95 as a decisive statistic.

7. **Target deep benchmark**
   - Retain at most 8-10 candidates.
   - Run 20 interleaved TCP+TLS samples per candidate by default.
   - Compute success rate, P50, P90, P95, max, MAD, and per-IP consistency.
   - Treat 60 ms as a target (`latency_target_ms`), not a universal hard rejection threshold.
   - Rank lexicographically: eligibility, reliability, P50, P95, MAD/jitter, IP consistency, edge confidence, institution/locality evidence.
   - Read `references/benchmark.md`.

8. **Local Reality integration test**
   - Run the incumbent control once before candidate Reality tests. A failed incumbent control invalidates the Reality batch.
   - Test at most the top 5 candidates.
   - Run exactly 5 sequential local sing-box Reality integration attempts per candidate.
   - Bind temporary listeners to `127.0.0.1` on ephemeral/high ports, use fresh test-only credentials, validate configs, perform one short HEAD through the loopback SOCKS path, and remove every temporary process/file.
   - Cleanup failure is a run-level safety failure (`TARGET_DIRTY_STATE`), not merely a candidate score.
   - Call this stage `LOCAL_REALITY_INTEGRATION_TEST`; do not claim it validates a real remote client path to the VPS.
   - Read `references/reality.md`.

9. **Report**
   - Separate `HARD_REJECTED`, `REVIEW_REQUIRED`, `DEFERRED_BUDGET`, temporary/source errors, and ranked-out candidates.
   - Preserve the incumbent as a baseline even if it is not policy-selectable.
   - Report Top 5 only from candidates that pass the required final Reality test when that stage is available and valid.
   - Compare finalists against the incumbent, including relative P50 improvement when measurable.
   - Never describe unprobed/deferred candidates as failures.
   - Read `references/result-schema.md`.

## Fixed default profile

Use these defaults unless the user explicitly requests a separately designed profile before the run begins:

- source pool cap: 1,200 hostnames
- discovered validated IPv4 hostname cap: 600
- target eligibility pool: 120
- fast benchmark pool: 50
- fast samples: 5 per candidate
- deep benchmark pool: 10
- deep samples: 20 per candidate
- final Reality candidates: 5
- Reality attempts: 5 per candidate
- target latency goal: P50 <= 60 ms, advisory only
- passive CT failure budget: 3 consecutive base-query failures
- fixed candidate port: 443

## Required artifacts

A successful controller run writes at least:

```text
frozen-run.json
target-frozen-run.json
target-result.json
target-preflight.json
regional-candidates.json
candidates.json
probe-pool.json
eligibility.json
fast-benchmark.json
deep-benchmark.json
reality-results.json
top5.json
rejections.csv
run-metadata.json
stage-status.tsv
report.md
```

If a stage cannot run, still emit structured status/evidence and do not fabricate missing measurements.

## Bundled scripts

- `scripts/controller_run.py`: inventory guard, frozen job construction, single fixed SSH orchestration, artifact extraction.
- `scripts/target_worker.py`: fixed target-side orchestrator. Intended to be preinstalled as `reality-sni-target-worker` on owned target VPSes.
- `scripts/target_discovery.py`: target-side regional/passive candidate discovery and bounded DNS validation.
- `scripts/target_probe.py`: target-side DNS/TLS/HEAD evidence and front-door classification.
- `scripts/benchmark.py`: interleaved target-side fast/deep TLS benchmarking and statistics.
- `scripts/reality_selftest.py`: isolated local sing-box Reality integration test.
- `scripts/report.py`: deterministic report/rejection artifact rendering.
- `scripts/common.py`: validation, statistics, safe JSON, and shared helpers.

Read `references/dependencies.md` before installing any missing dependency. Normal selection runs never install packages automatically.
