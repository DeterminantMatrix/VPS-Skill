# Final reporting contract v4.3.5

The user-facing answer is a decision aid, not a compressed benchmark log. Read `report.md`, `decision-summary.json`, `top5.json`, and `incumbent-assessment.json` before answering.

## Mandatory modules

Use this order and do not silently omit modules:

1. **一句话结论** — run status, incumbent verdict, best alternative, selectable count, candidate/search/overall confidence.
2. **当前 SNI 健康卡** — REALITY Protocol, observed TLS/ALPN, Policy, Reality control, TLS reliability/performance, Network Affinity, and explicit tradeoff versus best alternative.
3. **Top 5 核心决策表** — show all five when five `SELECTABLE` exist; never compress to three.
4. **候选详细卡与模型评语** — one card per displayed candidate with protocol evidence, safety/policy, Reality 5/5, TLS reliability, P50/P95/MAD, runtime stability, Network Affinity, operational-risk heuristic, confidence, and ranking rationale.
5. **怎么选** — one default choice, best backup, lowest-P95 option, best Network-Affinity option when known, and explicit partial-choice warning when fewer than five exist.
6. **搜索质量** — coverage status/goal, search confidence, source failures, and the distinction between candidate confidence and search confidence.
7. **自适应流水线统计** — initial Deep, refill rounds/candidates, total Deep, Reality tested/passed, adaptive stop reason, final selectable count.
8. **全部比较证据** — audit table; non-SELECTABLE rows must never be presented as recommendations.

## Required Top-5 fields

Include at least:

- rank and SNI;
- recommendation grade/label;
- REALITY Protocol state;
- observed TLS version and ALPN;
- Policy grade and final state;
- Reality result;
- TLS reliability grade and success rate;
- P50, P95, MAD;
- runtime-stability grade;
- Network Affinity grade/code;
- durability/operational-risk estimate;
- front-door/platform and ASN/organization when known;
- P50 difference versus incumbent;
- candidate/search/overall confidence;
- ranking rationale.

## Evidence-bound model commentary

The rule engine decides eligibility and ranking. The language model only explains structured facts. For each displayed candidate write 1-3 concise Chinese sentences covering why it is recommended, its main measured limitation/risk, and any near-tie reason.

Never invent historical uptime, organizational reputation, future DNS/hosting stability, unseen ASN/CDN relationships, or client-to-VPS performance.

## Near-tie rule

Within the frozen `p50_equivalence_ms` window (default 2 ms), do not claim a tiny P50 difference is meaningful. Explain ranking through P95, MAD, Network Affinity, runtime stability, front-door evidence, and operational-risk signals.
