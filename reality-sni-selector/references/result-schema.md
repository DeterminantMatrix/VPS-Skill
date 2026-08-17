# Result schema v4 / implementation 4.4

The worker returns one JSON object containing at least:

```text
schema_version
worker
status
frozen_run
preflight
coverage
candidate_discovery
network_affinity_search
regional_candidates  # compatibility alias
candidates
probe_pool
eligibility
fast_benchmark
deep_benchmark
reality
preliminary_top5
top5
comparison
incumbent_assessment
rejections
warnings
errors
counts
```

## Independent candidate dimensions

Keep these dimensions separate:

- `protocol_compliance` / controller-derived `protocol_compliance_grade`;
- `policy_eligibility` / `policy_grade` for safety/front-door policy; protocol hard failures are reported separately;
- benchmark reliability;
- `reality_compatibility` / `reality_grade`;
- `final_state`.

`SELECTABLE` requires protocol minimum PASS, clean safety/policy state, benchmark reliability pass, Reality 5/5 PASS, and clean cleanup. Protocol, safety-policy, and reliability hard-rejection code sets remain separately exposed so a TLS 1.2 failure is never mislabeled as a CDN/policy failure. Reality PASS never clears a protocol or policy rejection.

The controller derives these final-decision fields:

- `protocol_compliance_grade`;
- `tls_reliability_grade` (`tls_grade` remains a compatibility alias only);
- `policy_grade`;
- `reality_grade`;
- `performance_grade`;
- `runtime_stability_grade` and reason codes;
- `network_affinity_grade` / `network_affinity_code`;
- `durability_risk` and reason codes;
- `candidate_confidence`;
- `search_confidence`;
- `overall_recommendation_confidence`;
- `recommendation_grade` / `recommendation_label` / `recommendation_tier`;
- `decision_reasons`;
- `ranking_rationale_code` / `ranking_rationale`;
- `model_commentary_facts`.

`protocol_compliance` records TLS1.3, h2, certificate/identity and redirect-policy evidence. `network_affinity` records only directly observed facts such as SAME_ASN, same organization, IPv4 /16 prefix, or same country; it is not a hidden-route inference.

Durability/operational risk is an estimate from current observable signals only, not a future guarantee.

## Current SNI assessment

`incumbent_assessment` contains hostname, verdict/code, confidence, reason codes, current protocol/policy/reliability/P50/P95/MAD/Reality-control metrics, observed TLS version/ALPN, Network Affinity, best selectable alternative, relative improvements, and explicit `tradeoff_code` / `tradeoff_text`.

## Coverage and confidence

Keep search confidence distinct from each candidate's measurement confidence. SPARSE coverage can coexist with HIGH candidate confidence for a fully measured SNI.

`coverage` now contains both breadth and quality evidence:

- `breadth_status`, validated count and nominal goal;
- `quality_status`, effective `ELIGIBLE` count and survivor goal;
- `active_discovery_lanes`;
- `lane_counts` / `source_counts`;
- combined `status`.

`candidate_discovery` is the canonical multi-lane discovery artifact. `regional_candidates` remains only as a compatibility alias.

`network_affinity_search` records target ingress ASN/prefix, passive lookup method, sampled-IP count, affinity hostnames found, and the SAME_ASN funnel through Gate -> Eligible -> Fast -> Deep -> Reality -> SELECTABLE. It must explicitly report `active_scan: false` for the built-in passive method.

## Adaptive refill evidence

`reality.adaptive_refill` and `counts` include:

- initial Deep count;
- refill batch/deep cap/reality cap;
- refill rounds and added Deep candidates;
- total Reality candidates tested/passed;
- adaptive stop reason;
- final selectable count/target.

Typical stop reasons: `SELECTABLE_TARGET_MET`, `REALITY_CANDIDATE_CAP_REACHED`, `DEEP_POOL_CAP_REACHED`, `FAST_SURVIVORS_EXHAUSTED`, `REALITY_CONTROL_FAILED`, `REALITY_ENVIRONMENT_UNAVAILABLE`, or `TARGET_DIRTY_STATE`.

## Decision summary and reporting

`decision-summary.json` uses reporting contract `v4.4` and contains the recommended SNI/grade, candidate/search/overall confidence, P50 equivalence window, selectable count/target, coverage, and incumbent tradeoff.

`report.md` must follow the modular contract in `reporting.md` and never fabricate missing Top-5 rows.
