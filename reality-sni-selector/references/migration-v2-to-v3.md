# Migration from controller-first v2

The v3 architecture intentionally breaks several v2 assumptions.

## Removed from the controller measurement path

- controller-side candidate DNS qualification
- controller-side TLS/HTTP hard gate as final evidence
- controller-side P50/P95 benchmark
- `REJECT:P50_GT_60MS`
- hard rejection for TLS 1.3 absence
- hard rejection for h2 absence
- hard rejection for cross-host redirect alone
- hard rejection for unknown edge evidence alone
- treating candidates outside the active budget as failures

## Added

- target-side regional discovery and DNS view
- target-side eligibility gate
- 50-candidate fast target benchmark (5 samples each)
- 10-candidate deep target benchmark (20 samples each by default)
- target-side ASN evidence for deep finalists
- automatic read-only incumbent discovery with explicit fail-closed ambiguity handling
- one fixed SSH worker process
- integrated incumbent Reality control and candidate Reality 5/5 stage
- run-level cleanup invariant
- separate HARD / REVIEW / DEFERRED / ERROR semantics
- explicit `preliminary_top5` when Reality is unavailable or invalid

## Semantic changes

`60 ms` is a goal, not a universal hard gate. A run may legitimately report the best candidate above 60 ms.

`UNKNOWN_EDGE_EVIDENCE` enters review/secondary evaluation instead of being equated with a confirmed public CDN.

`PUBLIC_CDN` remains a hard rejection only when evidence is strong enough to identify a shared public edge.

`LOCAL_REALITY_INTEGRATION_TEST` proves local sing-box Reality compatibility on the target VPS. It does not prove a remote client-to-VPS path.
