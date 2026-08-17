# Migration v4.3.5 to v4.4

v4.4 keeps `schema_version: 4` and `worker_protocol: 4`, changes `implementation_version` to `4.4`, and changes the six-file worker manifest. Existing managed v4.3.5 workers are upgraded by the normal managed-worker lifecycle before freeze.

Key behavioral changes:

- replace institution-centric discovery with multi-lane General Regional / Network Affinity / Institutional / Passive Expansion discovery;
- use RIPEstat routing metadata plus bounded Shodan InternetDB passive IP sampling to discover affinity hostnames without raw CIDR scanning;
- treat institution provenance as a preference only, never an eligibility requirement;
- reserve bounded probe/Fast/Deep opportunity for affinity candidates while keeping Protocol/Policy/Reality gates authoritative;
- measure search quality with both validated breadth and effective eligible survivors;
- add a Network Affinity search funnel and discovery-lane evidence to final artifacts/reports;
- remove the old durability heuristic penalty for non-institutional discovery provenance.

Do not resume a frozen v4.3.5 job after upgrading the worker. Start a new v4.4 run so the discovery lanes, caps, and worker manifest are frozen consistently.

## Publication layout

v4.4 keeps the six-file worker manifest contract. Three large target modules are published as tiny manifest-covered Python entry files plus fixed `.py.gz` auxiliary payloads. Both bootstrap-time gzip SHA-256 and entry-time decompressed-source SHA-256 are verified before measurement code runs.
