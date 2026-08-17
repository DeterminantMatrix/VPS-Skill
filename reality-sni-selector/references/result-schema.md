# Result schema v4 / implementation 4.5

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

## Candidate correctness dimensions

Keep protocol compliance, safety policy, benchmark reliability, Reality compatibility and final state independent. `SELECTABLE` requires Protocol minimum PASS, clean safety/policy state, benchmark reliability PASS, Reality 5/5 PASS and clean cleanup.

Controller-derived dimensions include:

- `protocol_compliance_grade`;
- `tls_reliability_grade` (`tls_grade` compatibility alias);
- `policy_grade`, `reality_grade`, `performance_grade`;
- `latency_consistency_grade` (`runtime_stability_grade` may remain a compatibility alias in artifacts);
- `network_affinity_grade` / code;
- `durability_risk` based on current non-latency operational evidence;
- `candidate_confidence`;
- `run_coverage_confidence`;
- `global_optimality_confidence`;
- compatibility `search_confidence` = Run Coverage semantics;
- `overall_recommendation_confidence`;
- recommendation grade/label/tier, decision reasons and ranking rationale.

## Portfolio families and quality goal

Every final candidate carries `candidate_family` (registrable domain). Main `top5` is de-duplicated by family. Measured same-family hostnames may appear as `family_alternatives` and in audit artifacts.

`counts` includes at least:

- `selectable_hostnames`;
- `selectable_families`;
- `selectable_target`;
- `quality_target_met`;
- `baseline_only`;
- quality-extension Fast/Deep counts;
- comparison family count.

A five-family portfolio with no candidate meeting the frozen quality target returns `SUCCESS_QUALITY_BELOW_TARGET` after bounded search is exhausted. This is not a Protocol/Reality failure.

## Coverage, saturation and confidence

`coverage` contains:

- breadth status/validated goal;
- effective eligible status/goal;
- active discovery lanes and lane/source counts;
- source/validated selection reserve diagnostics;
- `saturation` cap-hit booleans;
- bounded discovery-extension evidence;
- source errors.

Run Coverage and Global Optimality are separate. Cap saturation/source failure may coexist with HIGH Candidate Confidence but should downgrade Global Optimality.

`candidate_discovery` is canonical multi-lane discovery evidence; `regional_candidates` is compatibility-only.

`network_affinity_search` records target ingress ASN/prefix, passive method (`active_scan:false`), sampled-IP count, and SAME_ASN funnel counts by **hostname and registrable family**, plus final unique endpoint/IP-set count.

## Adaptive evidence

`reality.adaptive_refill` and `counts` record initial Deep, refill, quality extension, Reality tested/passed, stop reason, independent-family count, and quality-target state.

Typical stop reasons include:

- `PORTFOLIO_AND_QUALITY_TARGET_MET`;
- `QUALITY_SEARCH_EXHAUSTED`;
- `REALITY_CANDIDATE_CAP_REACHED`;
- `DEEP_POOL_CAP_REACHED`;
- `FAST_SURVIVORS_EXHAUSTED`;
- `REALITY_CONTROL_FAILED`;
- `REALITY_ENVIRONMENT_UNAVAILABLE`;
- `TARGET_DIRTY_STATE`.

## Decision summary

`decision-summary.json` uses reporting contract `v4.5` and exposes recommended candidate/family, quality-target state, Candidate / Run Coverage / Global Optimality / Overall confidence, selectable family count/target, coverage/saturation and incumbent tradeoff.

`report.md` follows `reporting.md` and never fabricates missing independent families.
