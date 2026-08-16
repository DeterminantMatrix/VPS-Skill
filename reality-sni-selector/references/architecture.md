# Architecture v4.2

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
- `implementation_version: 4.2`
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
| regional/source discovery | no | yes |
| candidate DNS/TLS/HEAD/platform | no | yes |
| fast/deep benchmark | no | yes |
| local Reality integration | no | yes |
| final artifact rendering | yes | no |
