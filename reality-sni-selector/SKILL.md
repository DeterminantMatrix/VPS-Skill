---
name: reality-sni-selector
description: Select and verify VLESS Reality SNI / handshake targets for one owned VPS. Use when the user asks for 优选 SNI, Reality SNI selection, VLESS Reality camouflage/handshake target selection, current-SNI health evaluation, or comparison of serverName/dest/handshake candidates. Resolve the VPS from the local inventory and existing SSH alias, automatically ensure the Skill's fixed target worker is safely installed/current, perform all candidate discovery/network measurements on the target VPS, reject confirmed public-CDN/shared-platform front doors, compare against the incumbent, validate finalists with isolated sing-box Reality tests, and produce a ranked multi-dimensional comparison of at least five measured domains when available.
---

# 优选 SNI

Use the controller as the control plane and the selected VPS as the measurement plane.

## Non-negotiable rules

- Handle one explicit owned VPS per run.
- Treat the local workspace inventory as source of truth. Accept a public IPv4, exact inventory identifier/SSH alias/name, or a uniquely high-confidence fuzzy name. Never silently choose an ambiguous fuzzy match. Resolve through `inventory/hosts.yaml` first, with `/opt/vps-control/inventory/hosts.yaml` only as a legacy fallback. Follow `references/inventory-contract.md`.
- Use the declared existing SSH alias only. Never construct `root@IP`, derive SSH from monitoring/Komari data, or rebuild user/port/key arguments from inventory facts.
- Run candidate discovery and every candidate-related DNS, TCP, TLS, HTTP-header, ASN/platform/CDN, latency, and Reality measurement on the target VPS.
- Use IPv4 and TCP/443 only. Never scan ports, CIDRs, arbitrary addresses, or alternate ports.
- Do not download webpage bodies. HTTP evidence is bounded HEAD/header-only traffic.
- Do not run MTR, traceroute, iperf3, streaming, throughput, or unrelated quality tests.
- Do not modify production sing-box configuration, services, firewall, routes, SSH configuration, or networking during selection.
- Before freezing a selection job, ensure the exact reviewed worker is ready. Normal v4.3.5 selection may install/upgrade only the Skill's fixed managed worker paths; never overwrite unknown content or install system packages. Read `references/worker-lifecycle.md`.
- Freeze the profile, worker manifest, target identity, region, incumbent mode, seed set, limits, and timestamps **only after worker readiness succeeds**.
- Never treat missing evidence as proof of a direct origin.
- Never let low latency or Reality compatibility rescue a public-CDN/shared-platform policy rejection.
- Never print or persist passwords, private keys, UUIDs, Reality private keys, short IDs, tokens, cookies, or full secret-bearing proxy configs.

Read `references/safety-boundaries.md` before changing an execution boundary.

## Normal input

Prefer the target inventory IPv4, but also accept an exact inventory identifier/SSH alias/name or one uniquely high-confidence fuzzy name:

```text
python3 scripts/controller_run.py <inventory-target>
```

Examples: `23.19.228.207`, `lax-hostdzire`, or a unique typo-like selector such as `hostzdire`. A fuzzy match is recorded as `TARGET_SELECTOR_FUZZY_MATCH`; ambiguous matches fail closed.

Optional explicit inventory path:

```text
python3 scripts/controller_run.py <inventory-target> --inventory <inventory/hosts.yaml>
```

The target worker auto-resolves the current production Reality handshake/SNI read-only. If it is unavailable or ambiguous, rerun with:

```text
python3 scripts/controller_run.py <inventory-target> --incumbent <hostname>
```

Optional region seed file:

```text
python3 scripts/controller_run.py <inventory-target> --seed-file <fixed-region-seed-file>
```

Default to the adaptive QUICK profile. Use AUDIT only when the user explicitly asks for broader coverage/deeper discovery:

```text
python3 scripts/controller_run.py <inventory-target> --profile audit
```

Worker lifecycle controls:

```text
python3 scripts/controller_run.py <inventory-target> --worker-bootstrap never
python3 scripts/controller_run.py <inventory-target> --worker-ready-only
```

Use `--worker-bootstrap never` only when the user explicitly wants no worker-file writes. `--worker-ready-only` prepares/verifies the worker and exits before freeze or candidate traffic.

Never substitute Apple or another universal default incumbent.

## Workflow

1. **Inventory guard**
   - Require the local `hosts.<canonical>` schema.
   - Resolve exact public IPv4 or exact identifiers first. Allow fuzzy name resolution only when one candidate exceeds the confidence threshold with a clear margin over the runner-up; otherwise fail ambiguous.
   - Record selector input, match mode, matched identifier, score, and `TARGET_SELECTOR_FUZZY_MATCH` when fuzzy resolution is used.
   - Resolve the selected host public IPv4 only from `access.address`/`access.hostname` facts.
   - Require explicit `alias`, `region`, `access.method: ssh`, `capabilities.ssh: true`, and non-retired/non-forbidden state.
   - Preserve `inventory_id` and SSH alias as separate identities.

2. **Managed worker readiness before freeze**
   - Compute the expected SHA-256 manifest of the six fixed worker Python files and the reviewed wrapper SHA-256.
   - Probe exactly `/usr/local/bin/reality-sni-target-worker identity` through the declared alias. This operation is read-only and generates no candidate traffic.
   - If protocol 4, implementation 4.3.5, worker manifest, and wrapper hash are exact, continue without writes.
   - If both managed paths are absent, automatically bootstrap the reviewed worker when `--worker-bootstrap auto` is active.
   - If `.managed.json` proves the existing worker is managed by this Skill, safely upgrade it when stale.
   - Recognize reviewed legacy v4/v4.1 installs only by exact known manifest/wrapper hashes, then upgrade them safely.
   - If unknown content occupies the fixed paths, return `WORKER_PATH_CONFLICT`; never overwrite it.
   - Stage, hash-verify, back up managed old content, atomically activate, verify again, and probe identity again before proceeding.
   - Read `references/worker-lifecycle.md` and `references/target-worker-install.md`.

3. **Freeze v4.3.5 worker contract**
   - Freeze `schema_version: 4`, `worker_protocol: 4`, `implementation_version: 4.3.5`, and `expected_worker_manifest` only after exact readiness.
   - A readiness failure creates no frozen SNI job. Start candidate selection only after worker readiness is `READY`.

4. **One fixed measurement SSH process**
   - Invoke exactly `/usr/local/bin/reality-sni-target-worker run` through the existing alias.
   - Send the frozen JSON job on stdin.
   - Do not pass arbitrary shell fragments, remote paths, ports, or commands into the measurement job.
   - Persist only a bounded secret-redacted stderr summary for measurement failures.
   - Write every invocation into a dedicated run directory. The controller creates a unique child directory by default; use `--run-dir <empty-dir>` to choose it explicitly.
   - Worker identity/bootstrap may use bounded pre-freeze SSH/SCP operations; the actual SNI measurement still uses one fixed worker `run` process.

5. **Target preflight and incumbent**
   - Observe target egress IPv4, location/ASN evidence, and approved tool paths.
   - Prefer fixed reviewed sing-box ELF paths; use PATH only as a fallback after ELF validation.
   - Resolve incumbent from the running sing-box process `-c/--config` and `-C/--config-directory` arguments when possible; fall back to fixed read-only config locations only when no live config can be read.
   - Fail closed on zero or multiple distinct Reality targets.
   - Read `references/incumbent.md`.

6. **Target-local discovery**
   - Default QUICK mode aims for about 200 validated public-IPv4 hostnames, using primary regional institutional sources first and CT only as backfill when source diversity is insufficient.
   - AUDIT mode restores the broader 400-hostname coverage goal and full CT pass.
   - Query independent regional metadata sources concurrently when practical; do not scan raw address space.
   - Record source failures and coverage as `GOOD`, `LIMITED`, or `SPARSE`; never claim QUICK coverage is exhaustive.
   - Read `references/candidate-discovery.md`.

7. **Diversity-aware eligibility pool**
   - Keep the incumbent.
   - QUICK: select at most 80 candidates. AUDIT: at most 120.
   - Favor diversity across registrable domains, initial IPv4 sets, organizations, source buckets, and locality.
   - Mark unprobed candidates `DEFERRED:PROBE_BUDGET` or `DEFERRED:DIVERSITY_BUDGET`; never call them failures.

8. **Eligibility gate**
   - Measure DNS and all current common IPv4s from the target.
   - QUICK: start with one cheap TLS attempt per current IP; only candidates that would be rejected solely for a transport failure get the second gate sample. AUDIT keeps two gate samples per IP.
   - Verify SNI TLS and certificate validity/identity.
   - Enforce the REALITY target protocol minimum before performance ranking: every current usable IPv4 must negotiate TLS 1.3 and ALPN `h2`; otherwise hard reject as `HARD:REALITY_MIN_TLS13` or `HARD:REALITY_MIN_H2`.
   - Hard reject a confirmed cross-site HTTP redirect as `HARD:REALITY_CROSS_SITE_REDIRECT`; same-site/root-to-www redirects remain acceptable. If redirect evidence is unavailable, preserve review/unknown state rather than inventing a pass.
   - Collect bounded CNAME, HEAD headers, and cached network-organization evidence.
   - Hard reject confirmed public CDN (`HARD:KNOWN_PUBLIC_CDN`) and confirmed shared platform (`HARD:KNOWN_SHARED_PLATFORM`).
   - Treat Pantheon as a shared-platform risk when high-confidence Pantheon hostname/CNAME/header/network-organization evidence is present.
   - Treat HEAD failure, unknown edge evidence, bounded HTTP status errors, and insufficient metadata as warnings/review rather than false proof of directness. TLS 1.2-only, no-h2, invalid identity/certificate, and confirmed cross-site redirect are protocol hard failures.
   - Read `references/evaluation-model.md`, `references/gates.md`, and `references/rejection-codes.md`.

9. **Fast and deep benchmark**
   - QUICK Fast: up to 36 candidates, 3 interleaved TCP+TLS samples each.
   - AUDIT Fast: up to 50 candidates, 5 interleaved samples each.
   - Deep starts with 10 candidates and **20 total samples per candidate**, reusing same-run Fast samples and only measuring the missing samples.
   - If Reality has not produced five `SELECTABLE` candidates, refill Deep from already-Fast-measured `ELIGIBLE` survivors in deterministic batches of four. QUICK may grow Deep to 18 total rows including the incumbent; AUDIT may grow to 20. Never remeasure candidates already in Deep.
   - Deep reliability gates remain unchanged: overall TLS success >=95%; per-IP >=90% when sufficiently sampled.
   - Treat P50 <=60 ms as an advisory target, not a hard cutoff.
   - Rank policy state before reliability/latency: `ELIGIBLE` before `REVIEW_REQUIRED`, then success rate, a frozen 2 ms P50 near-tie band, P95, MAD, network affinity, exact P50, IP consistency, edge confidence, and source evidence.
   - Record `Network Affinity` from observed facts only: `SAME_ASN` is strongest, then same observed organization or IPv4 /16 prefix, then same country; unknown topology remains unknown. Use affinity as a near-tie preference, never as a replacement for protocol/reliability gates or a large latency gap.
   - Read `references/benchmark.md`.

10. **LOCAL_REALITY_INTEGRATION_TEST**
   - Test the incumbent control first. If the first control attempt succeeds, continue immediately. If it fails cleanly, run two diagnostic retries and require at least 2/3 total successes; cleanup failure invalidates the batch immediately.
   - Test only Deep survivors whose policy state is `ELIGIBLE`; do not spend Reality budget on `REVIEW_REQUIRED` rows that cannot become `SELECTABLE`.
   - QUICK: start with the initial Deep set, then trigger Deep refill whenever the current tested set still yields fewer than five `SELECTABLE`. Stop immediately when five are found, when the Fast survivor pool/Deep cap is exhausted, or after 16 candidate Reality tests. AUDIT uses the same adaptive rule with a 20-row Deep cap and 18 candidate Reality tests.
   - Require 5/5 candidate success. Because one clean transport failure makes 5/5 impossible, stop that candidate immediately and move to the next ranked candidate.
   - Use fresh temporary keys/UUID/short ID, loopback-only listeners, ephemeral/high ports, `sing-box check`, one short HEAD through loopback SOCKS, and verified cleanup.
   - Record sanitized failure stages such as config check, server start, client start, proxy HEAD transport, timeout, or cleanup.
   - Call this a local integration test; never claim it validates a real client-to-VPS path.
   - Read `references/reality.md`.

11. **Incumbent assessment and final reporting**
   - Evaluate the currently configured SNI using the same policy, deep reliability, Reality-control, and performance evidence. Emit one of: `继续使用`, `可继续使用，但有优化空间`, `暂可继续使用，建议复核`, `建议更换`, `需要更换`, or `暂无法评估`.
   - Hard policy failure, deep reliability failure, or a clean failed Reality control produces `需要更换`; a materially faster fully selectable alternative can produce `建议更换` even when the incumbent is otherwise healthy.
   - Read `references/incumbent-assessment.md` for thresholds and precedence.
   - Keep `policy_eligibility`, `benchmark_eligibility`, `reality_compatibility`, and `final_state` independent.
   - `SELECTABLE` requires policy eligibility, benchmark reliability, Reality PASS, and clean cleanup.
   - Reality PASS never overrides a policy rejection.
   - Keep REALITY protocol compliance separate from TLS transport reliability. A 100% TLS success rate does not compensate for TLS <1.3, missing h2, certificate/identity failure, or a confirmed cross-site redirect.
   - Produce `report.md` as fixed modules: (A) one-line conclusion, (B) incumbent health card, (C) complete Top-5 decision table, (D) per-candidate detail cards and model-commentary facts, (E) how-to-choose guidance, (F) search quality, (G) adaptive pipeline statistics, and (H) full audit comparison.
   - Produce `decision-summary.json` and a recommendation-sorted, multi-dimensional comparison containing at least five distinct measured domains when at least five exist. Include the incumbent baseline even if this makes the detailed comparison longer than five rows.
   - The visible Top-5 decision table must show all five `SELECTABLE` domains when five exist. Never silently compress five results to three.
   - For every Top-5 candidate expose recommendation grade, REALITY Protocol state, observed TLS version/ALPN, Policy and Final state, Reality result, TLS reliability, P50/P95/MAD, performance grade, runtime-stability grade, Network Affinity, evidence-bounded long-term-risk estimate, front-door/platform, ASN/organization when known, P50 delta vs incumbent, candidate confidence, search confidence, overall recommendation confidence, and ranking rationale.
   - Treat P50 differences inside the frozen `p50_equivalence_ms` window (default 2 ms) as near-ties; explain the order using P95, MAD, runtime stability and long-term-risk signals rather than tiny P50 differences.
   - Separate candidate confidence from search coverage confidence. A SPARSE search may still produce HIGH-confidence individual candidates, but must not be described as exhaustive.
   - The calling model must read `report.md`, `decision-summary.json`, `top5.json`, and `incumbent-assessment.json`, then write evidence-bound Chinese commentary for each displayed Top-5 candidate and a concise “how to choose” recommendation. Never invent historical uptime, future stability, unseen CDN/ASN relationships, or client-to-VPS performance.
   - If fewer than five measured domains exist, report all and emit `INSUFFICIENT_COMPARISON_DOMAINS`; never fabricate rows.
   - Read `references/result-schema.md` and `references/reporting.md`.

## Default QUICK profile and AUDIT override

Default QUICK:

- source pool cap: 520
- validated hostname cap: 240
- coverage goal: 200
- source stop target before CT backfill: 300 records
- eligibility pool: 80
- fast pool: 36
- fast samples: 3
- initial deep pool: 10
- deep pool cap after adaptive refill: 18
- deep refill batch: 4
- deep total samples: 20, including reused Fast samples
- target selectable SNI count: 5
- Reality candidate cap: 16
- candidate Reality requirement: 5/5, fail-fast after the first clean failure
- comparison minimum: 5 distinct measured domains when available
- IP metadata budget: 128 unique IPv4s
- target latency goal: P50 <=60 ms, advisory only
- passive CT failure budget: 3 consecutive base-query failures
- fixed candidate port: 443

AUDIT (`--profile audit`) restores the broad discovery/eligibility profile: source cap 1,200, validated cap 600, coverage goal 400, eligibility 120, Fast 50 x 5, initial Deep 10 x 20 total (still reusing Fast samples), adaptive Deep cap 20, refill batch 4, and up to 18 Reality candidates while targeting five selectable results.

## Required artifacts

A normal controller invocation writes lifecycle evidence first and, after freeze, the selection artifacts into its dedicated run directory:

```text
worker-lifecycle.json
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
decision-summary.json
incumbent-assessment.json
top5.json
rejections.csv
run-metadata.json
stage-status.tsv
report.md
```

If worker readiness fails, `worker-lifecycle.json`, `run-metadata.json`, `stage-status.tsv`, and blocked result files may exist **without** `frozen-run.json`; this is intentional.

## Selection vs maintenance

Normal `SELECTION MODE` may manage only the Skill's fixed worker runtime. Unknown path conflicts, privilege/SSH repair, dependency installation, source edits, production changes, and Git/project edits remain `MAINTENANCE / REPAIR MODE`. Read `references/maintenance.md`.

## Bundled scripts

- `scripts/controller_run.py`: compact v4.3.5 entrypoint around the stable controller runtime plus deterministic decision postprocessing.
- `scripts/controller_runtime.py`: stable local inventory resolution, pre-freeze worker readiness, frozen QUICK/AUDIT job, fixed measurement orchestration, and base artifacts.
- `scripts/controller_core.py`: compact pure profile/seed/frozen-job helpers.
- `scripts/decision_postprocess.py`: creates `decision-summary.json`, enriches `top5.json`, and normalizes the final v4.3.5 report after target measurement.
- `scripts/worker_lifecycle.py`: controller-side identity probe, fixed payload creation, bounded SCP/SSH bootstrap orchestration.
- `scripts/worker_bootstrap.py`: target-side fixed-path atomic installer/upgrade with legacy recognition, backups, hash verification, and rollback.
- `scripts/target_worker.py`: fixed target-side adaptive orchestrator and incumbent assessment.
- `scripts/target_discovery.py`: bounded target-side regional/passive discovery.
- `scripts/target_probe.py`: TLS/HEAD/network evidence and public-CDN/shared-platform classification.
- `scripts/benchmark.py`: interleaved fast/deep benchmarking and policy-first ranking.
- `scripts/reality_selftest.py`: isolated local Reality integration and sanitized failure evidence.
- `scripts/report.py`: small decision/report facade.
- `scripts/decision_grades.py` and `scripts/decision_view.py`: deterministic evidence-bound grading, confidence, tradeoff, and ranking rationale.
- `scripts/report_format.py` and `scripts/report_render.py`: normalized Chinese decision report and complete Top-5 display.
- `scripts/common.py`: validation, stats, v4 contract constants, worker manifest, safe JSON helpers.
- `scripts/reality-sni-target-worker`: fixed `identity`/`run` deployment wrapper.

For migration semantics, read `references/migration-v4.3-to-v4.3.5.md`.

Read `references/dependencies.md` before any dependency installation. Normal selection never installs system packages.
