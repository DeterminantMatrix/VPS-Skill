# Architecture v4.5

## Control plane vs measurement plane

The controller may validate local inventory, ensure the Skill's fixed target worker is ready, freeze parameters, open the measurement SSH process, collect structured output, and render artifacts. It must not use controller-side DNS/routing/RTT as candidate evidence.

The target VPS performs all candidate discovery, DNS, TLS/certificate checks, HTTP-header/platform evidence, latency benchmarking, and local Reality integration tests.

## Pre-freeze worker lifecycle

```text
controller
  -> resolve inventory_id / alias / region
  -> compute expected six-file manifest + wrapper hash
  -> fixed identity probe
       /usr/local/bin/reality-sni-target-worker identity
  -> if needed: bounded managed bootstrap/upgrade
       fixed payload only, fixed paths only, backup + hash verification
  -> fixed identity probe again
  -> exact worker READY
```

Bootstrap is control-plane preparation. It is not candidate discovery or network measurement. Read `worker-lifecycle.md`.

## Frozen measurement contract

Only after exact worker readiness:

```text
controller
  -> freeze v4 JSON job
  -> one measurement SSH process using the existing alias
  -> /usr/local/bin/reality-sni-target-worker run
  -> frozen JSON on stdin
  <- one structured v4 JSON result on stdout
```

No user shell fragment, arbitrary remote destination, or arbitrary remote path is accepted. Candidate network evidence still originates only from the target worker.

## Version/build handshake

The job freezes:

- `schema_version: 4`
- `worker_protocol: 4`
- `implementation_version: 4.5`
- `expected_worker_manifest`

The readiness probe additionally verifies the reviewed wrapper SHA-256. The measurement worker repeats protocol/version/manifest validation before candidate network traffic.

## Stage ownership

| Stage | Controller | Target VPS |
|---|---:|---:|
| inventory guard | yes | no |
| worker identity/bootstrap | orchestrates | fixed-path install/verify |
| freeze job/manifest | yes | no |
| egress/location | no | yes |
| incumbent config discovery | no | yes |
| multi-lane General Regional / Network Affinity / Institutional / passive discovery | no | yes |
| candidate DNS/TLS/HEAD/platform | no | yes |
| fast/deep benchmark | no | yes |
| local Reality integration | no | yes |
| decision/ranking artifact rendering | yes | evidence produced on target |
| final artifact rendering | yes | no |


## Multi-lane discovery v4.5

The target worker treats institutional websites as one preference lane rather than the candidate universe. General Regional OSM website metadata, Network Affinity routing/passive data, Institutional metadata, and cross-lane CT expansion are combined before DNS validation. Source-level and validated-level lane reserves are applied before global caps so a large General Regional result cannot starve smaller lanes; unused reserve returns to common fill. Common social/profile/aggregator URLs are filtered only from regional/institutional metadata. The built-in affinity lane uses routing metadata plus bounded third-party passive IP lookups only; it never actively sweeps BGP prefixes.

## Adaptive selection and decision layer v4.5

The target worker owns adaptive measurement: initial Deep, optional one-time quality discovery extension, Reality, and bounded Deep refill. Normal early success requires five independent registrable-domain families **and** at least one candidate meeting the frozen quality target. Same-family hostnames remain alternatives rather than duplicate Top-5 slots. If the bounded search finds five families but misses the quality target, it reports `SUCCESS_QUALITY_BELOW_TARGET`. The controller deterministically derives Candidate / Run Coverage / Global Optimality confidence, ranking rationale and modular decision artifacts from target-measured evidence.
