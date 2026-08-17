# Migration v4.4 to v4.5

v4.5 keeps `schema_version: 4` and `worker_protocol: 4`, changes `implementation_version` to `4.5`, and changes the reviewed worker manifest. Existing managed v4.4 workers are upgraded by the normal managed-worker lifecycle before freeze.

Key behavioral changes:

- define the visible Top-5 as five independent registrable-domain families when available; apex/`www` variants remain measured family alternatives instead of consuming duplicate main slots;
- stop adaptive selection only when both the portfolio goal and the quality goal are met, or when bounded search is exhausted; five valid families with no quality-target candidate return `SUCCESS_QUALITY_BELOW_TARGET`;
- reserve source-pool and validated-pool opportunity for Network Affinity, Institutional, General Regional, and Passive Expansion lanes before global hard caps, with unused reserve flowing back to common fill;
- filter common third-party social/profile/aggregator hostnames from regional/institutional metadata lanes without turning those domains into protocol hard rejects;
- separate Candidate Confidence, Run Coverage Confidence, Global Optimality Confidence, and Overall Recommendation Confidence; hard-cap saturation or source failures prevent unjustified HIGH global-optimality claims;
- separate TLS transport reliability, Reality reliability, and observed latency consistency; single-run latency dispersion no longer raises durability/operational risk by itself;
- report baseline-only counts, hostname/family/endpoint affinity funnels, lane-cap saturation, family alternatives, and safer source-error subtypes.
- keep the six-file manifest contract while publishing the large `target_worker.py` auxiliary source as five fixed base64 chunks; bootstrap verifies each chunk and the entrypoint verifies the reconstructed gzip/source hashes before execution.

The bounded passive Network Affinity safety boundary is unchanged: no raw CIDR/ASN sweep and no active TCP scan of BGP-derived IP samples.

Do not resume a frozen v4.4 job after upgrading the worker. Start a new v4.5 run so the discovery reserves, portfolio/quality goals, caps, and worker manifest are frozen consistently.
