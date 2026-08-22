# Final reporting contract v4.5

The user-facing answer is a decision aid, not a compressed benchmark log. Read `report.md`, `decision-summary.json`, `top5.json`, and `incumbent-assessment.json` before answering.

## Mandatory modules

Use this order:

1. **一句话结论** — run status, incumbent verdict, best alternative, independent selectable-family count, quality-target state, Candidate / Run Coverage / Global Optimality / Overall confidence.
2. **当前 SNI 健康卡** — protocol, TLS/ALPN, observed certificate validity/remaining time, policy, Reality control, TLS transport reliability, performance and Network Affinity.
3. **Top 5 核心决策表** — one slot per registrable-domain family by default; display all five independent families when available, including observed certificate validity/remaining time.
4. **候选详细卡** — family, same-family alternatives, Protocol, certificate validity/remaining time, Policy, Reality, TLS reliability, P50/P95/MAD, latency consistency, Network Affinity, operational-risk heuristic, confidence and ranking rationale.
5. **怎么选** — default choice, backup, best P95, best affinity, and explicit portfolio/quality limitations.
6. **搜索质量与 Network Affinity** — breadth, effective survivor quality, lane/source reserves, saturation, source errors, target ASN/prefix and hostname/family/endpoint affinity funnel.
7. **自适应流水线统计** — baseline-only, initial Deep, quality extension, refill, total Deep, Reality tested/passed, stop reason, family count and quality-target state.
8. **全部比较证据** — audit table including observed certificate validity/remaining time; non-SELECTABLE rows are never recommendations.

## Independent family rule

`example.com` and `www.example.com` are two measurable hostnames but normally one decision family. Keep the stronger hostname in the main Top-5 slot and retain measured same-family alternatives in detail/audit evidence. Do not claim five independent choices when only five hostnames from fewer root domains passed.

## Confidence terminology

Keep these separate:

- **Candidate Confidence** — how complete/reliable this candidate's own measurements are.
- **Run Coverage Confidence** — whether the configured bounded search executed with enough breadth/eligible yield/lane diversity.
- **Global Optimality Confidence** — how much evidence supports being near the best candidate available in the broader search space. Hard-cap saturation, source failures, missing lanes, or an unmet quality goal downgrade this dimension.
- **Overall Recommendation Confidence** — conservative synthesis used for the recommendation.

Do not use `HIGH` Run Coverage as a synonym for exhaustive or global-optimum search.

## Reliability and consistency terminology

Do not call one-run latency dispersion generic "runtime stability". Display separately:

- TLS transport reliability;
- Reality reliability (5/5 when selectable);
- observed **Latency Consistency** from MAD/tail spread.

Operational/durability risk must not be increased solely because P95-P50 or MAD was large in one run. Keep that latency evidence in performance/consistency.

## Evidence-bound model commentary

The rule engine decides eligibility/ranking. The language model only explains structured facts. Never invent historical uptime, organizational reputation, future DNS/hosting stability, unseen ASN/CDN relationships, or client-to-VPS performance.

Within the frozen 2 ms P50 near-tie window, explain ordering via P95, MAD/Latency Consistency, Network Affinity, front-door evidence, certificate validity/remaining time and operational-risk signals rather than tiny median differences.

Institutional provenance remains a discovery preference, never a REALITY eligibility requirement. If no SAME_ASN family is selectable, explain whether none was discovered or discovered candidates were eliminated later.
