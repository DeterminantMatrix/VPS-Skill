---
name: reality-sni-selector
description: Select and verify VLESS Reality SNI / handshake targets for one owned VPS. Use when the user asks for 优选 SNI, Reality SNI selection, VLESS Reality camouflage/handshake target selection, or comparison of serverName/dest/handshake candidates. Resolve the VPS from the local inventory and existing SSH alias, orchestrate from the controller, perform all candidate discovery/network measurements on the target VPS, reject confirmed public-CDN/shared-platform front doors, compare against the incumbent, validate finalists with isolated sing-box Reality tests, and produce a ranked multi-dimensional comparison of at least five measured domains when available.
---

# 优选 SNI

Use the controller as the control plane and the selected VPS as the measurement plane.

## Non-negotiable rules

- Handle one explicit owned VPS per run.
- Treat the local workspace inventory as source of truth. Resolve the target IPv4 through `inventory/hosts.yaml` first, with `/opt/vps-control/inventory/hosts.yaml` only as a legacy fallback. Follow `references/inventory-contract.md`.
- Use the declared existing SSH alias only. Never construct `root@IP`, derive SSH from monitoring/Komari data, or rebuild user/port/key arguments from inventory facts.
- Run candidate discovery and every candidate-related DNS, TCP, TLS, HTTP-header, ASN/platform/CDN, latency, and Reality measurement on the target VPS.
- Use IPv4 and TCP/443 only. Never scan ports, CIDRs, arbitrary addresses, or alternate ports.
- Do not download webpage bodies. HTTP evidence is bounded HEAD/header-only traffic.
- Do not run MTR, traceroute, iperf3, streaming, throughput, or unrelated quality tests.
- Do not modify production sing-box configuration, services, firewall, routes, SSH, or networking during selection.
- A normal selection run must not upload code or deploy/update the worker. The target must already expose `/usr/local/bin/reality-sni-target-worker run`.
- Freeze the profile, worker manifest, target identity, region, incumbent mode, seed set, limits, and timestamps before candidate evaluation.
- Never treat missing evidence as proof of a direct origin.
- Never let low latency or Reality compatibility rescue a public-CDN/shared-platform policy rejection.
- Never print or persist passwords, private keys, UUIDs, Reality private keys, short IDs, tokens, cookies, or full secret-bearing proxy configs.

Read `references/safety-boundaries.md` before changing an execution boundary.

## Normal input

Prefer the target inventory IPv4 as the only required user input:

```text
python3 scripts/controller_run.py <inventory-ipv4>
```

Optional explicit inventory path:

```text
python3 scripts/controller_run.py <inventory-ipv4> --inventory <inventory/hosts.yaml>
```

The target worker auto-resolves the current production Reality handshake/SNI read-only. If it is unavailable or ambiguous, rerun with:

```text
python3 scripts/controller_run.py <inventory-ipv4> --incumbent <hostname>
```

Optional region seed file:

```text
python3 scripts/controller_run.py <inventory-ipv4> --seed-file <fixed-region-seed-file>
```

Never substitute Apple or another universal default incumbent.

## Workflow

1. **Inventory guard**
   - Require the local `hosts.<canonical>` schema.
   - Match the target against `access.address`/`access.hostname` facts.
   - Require explicit `alias`, `region`, `access.method: ssh`, `capabilities.ssh: true`, and non-retired/non-forbidden state.
   - Preserve `inventory_id` and SSH alias as separate identities.

2. **Freeze v4 worker contract**
   - Compute the SHA-256 manifest of the fixed target-worker file set.
   - Freeze `schema_version: 4`, `worker_protocol: 4`, and `expected_worker_manifest` before SSH.
   - Fail closed with `TARGET_WORKER_VERSION_MISMATCH` or `TARGET_WORKER_BUILD_MISMATCH` before candidate traffic if the deployed worker differs.

3. **One fixed SSH process**
   - Invoke exactly `/usr/local/bin/reality-sni-target-worker run` through the existing alias.
   - Send the frozen JSON job on stdin.
   - Do not pass arbitrary shell fragments, remote paths, ports, or commands.

4. **Target preflight and incumbent**
   - Observe target egress IPv4, location/ASN evidence, and approved tool paths.
   - Prefer fixed reviewed sing-box ELF paths; use PATH only as a fallback after ELF validation.
   - Resolve incumbent from the running sing-box process `-c/--config` and `-C/--config-directory` arguments when possible; fall back to fixed read-only config locations only when no live config can be read.
   - Fail closed on zero or multiple distinct Reality targets.
   - Read `references/incumbent.md`.

5. **Target-local discovery**
   - Collect target-region institutional domains from fixed seeds, bounded Wikidata/OSM/OpenAlex metadata, passive CT, and DNS validation.
   - Do not scan raw address space.
   - Record source failures and coverage as `GOOD`, `LIMITED`, or `SPARSE`.
   - Mark non-GOOD runs `PROVISIONAL`; do not claim the search is exhaustive.
   - Read `references/candidate-discovery.md`.

6. **Diversity-aware eligibility pool**
   - Keep the incumbent.
   - Select at most 120 candidates deterministically while favoring diversity across registrable domains, initial IPv4 sets, organizations, source buckets, and locality.
   - Mark unprobed candidates `DEFERRED:PROBE_BUDGET` or `DEFERRED:DIVERSITY_BUDGET`; never call them failures.

7. **Eligibility gate**
   - Measure DNS and all current common IPv4s from the target.
   - Verify SNI TLS and certificate validity/identity.
   - Collect bounded CNAME, HEAD headers, and cached network-organization evidence.
   - Hard reject confirmed public CDN (`HARD:KNOWN_PUBLIC_CDN`) and confirmed shared platform (`HARD:KNOWN_SHARED_PLATFORM`).
   - Treat Pantheon as a shared-platform risk when high-confidence Pantheon hostname/CNAME/header/network-organization evidence is present.
   - Treat HEAD failure, unknown edge evidence, TLS 1.2, no h2, redirects, and HTTP status as warnings/review rather than false proof of directness.
   - Read `references/gates.md` and `references/rejection-codes.md`.

8. **Fast and deep benchmark**
   - Fast: up to 50 candidates, 5 interleaved TCP+TLS samples each.
   - Deep: up to 10 candidates, 20 interleaved samples each.
   - Deep reliability gates: overall TLS success >=95%; per-IP >=90% when sufficiently sampled.
   - Treat P50 <=60 ms as an advisory target, not a hard cutoff.
   - Rank policy state before reliability/latency: `ELIGIBLE` before `REVIEW_REQUIRED`, then success rate, P50, P95, MAD, IP consistency, edge confidence, ASN/locality/source evidence.
   - Read `references/benchmark.md`.

9. **LOCAL_REALITY_INTEGRATION_TEST**
   - Test the incumbent control first. If the first control attempt succeeds, continue immediately. If it fails cleanly, run two diagnostic retries and require at least 2/3 total successes; cleanup failure invalidates the batch immediately.
   - Test at most the top five finalists.
   - Require exactly 5/5 candidate attempts.
   - Use fresh temporary keys/UUID/short ID, loopback-only listeners, ephemeral/high ports, `sing-box check`, one short HEAD through loopback SOCKS, and verified cleanup.
   - Record sanitized failure stages such as config check, server start, client start, proxy HEAD transport, timeout, or cleanup.
   - Call this a local integration test; never claim it validates a real client-to-VPS path.
   - Read `references/reality.md`.

10. **Final policy and reporting**
   - Keep `policy_eligibility`, `benchmark_eligibility`, `reality_compatibility`, and `final_state` independent.
   - `SELECTABLE` requires policy eligibility, benchmark eligibility, Reality PASS, and clean cleanup.
   - Reality PASS never overrides a policy rejection.
   - Produce `report.md` with hierarchical stage counts and coverage maturity.
   - Produce a recommendation-sorted, multi-dimensional comparison table containing at least five distinct measured domains when at least five exist. Include the incumbent baseline even if this makes the table longer than five rows.
   - Compare recommendation, policy/final state, front door/platform, TLS success, P50, P95, MAD, Reality result, ASN/organization, and P50 improvement vs incumbent.
   - If fewer than five measured domains exist, report all and emit `INSUFFICIENT_COMPARISON_DOMAINS`; never fabricate rows.
   - Read `references/result-schema.md`.

## Fixed default profile

- source pool cap: 1,200
- validated hostname cap: 600
- eligibility pool: 120
- fast pool: 50
- fast samples: 5
- deep pool: 10
- deep samples: 20
- final Reality candidates: 5
- candidate Reality attempts: 5
- comparison minimum: 5 distinct measured domains when available
- IP metadata budget: 128 unique IPv4s
- target latency goal: P50 <=60 ms, advisory only
- passive CT failure budget: 3 consecutive base-query failures
- fixed candidate port: 443

## Required artifacts

A completed controller run writes at least:

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
comparison.json
top5.json
rejections.csv
run-metadata.json
stage-status.tsv
report.md
```

## Selection vs repair

Normal invocation is `SELECTION MODE`. If a worker/environment defect is discovered, stop selection and report `REPAIR_REQUIRED`. Enter `MAINTENANCE / REPAIR MODE` only after explicit user authorization. Repair may update/test/deploy the fixed worker, but it must not silently continue the old frozen selection run afterward. Read `references/maintenance.md`.

## Bundled scripts

- `scripts/controller_run.py`: strict local inventory guard, v4 frozen job, worker-manifest verification, one fixed SSH orchestration, artifacts.
- `scripts/target_worker.py`: fixed target-side v4 orchestrator.
- `scripts/target_discovery.py`: bounded target-side regional/passive discovery.
- `scripts/target_probe.py`: TLS/HEAD/network evidence and public-CDN/shared-platform classification.
- `scripts/benchmark.py`: interleaved fast/deep benchmarking and policy-first ranking.
- `scripts/reality_selftest.py`: isolated local Reality integration and sanitized failure evidence.
- `scripts/report.py`: hierarchical report plus >=5-domain recommendation comparison when measurable.
- `scripts/common.py`: validation, stats, v4 contract constants, worker manifest, safe JSON helpers.
- `scripts/reality-sni-target-worker`: fixed deployment wrapper.

Read `references/dependencies.md` before any separately authorized dependency installation. Normal selection runs never install packages.
