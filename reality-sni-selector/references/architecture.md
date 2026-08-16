# Architecture v4

## Control plane vs measurement plane

The controller may validate the local inventory, freeze parameters, compute the expected worker manifest, open SSH, collect structured output, and render artifacts. It must not use its own DNS/routing/RTT as candidate evidence.

The target VPS performs all candidate discovery, DNS, TLS/certificate checks, HTTP-header/platform evidence, latency benchmarking, and local Reality integration tests.

## Fixed remote contract

```text
controller
  -> resolve inventory_id / alias / region
  -> compute expected worker manifest
  -> one OpenSSH process using existing alias
  -> /usr/local/bin/reality-sni-target-worker run
  -> frozen v4 JSON on stdin
  <- one structured v4 JSON result on stdout
```

The controller never sends an arbitrary remote command, arbitrary port, uploaded script, or user shell fragment.

## Version/build handshake

The job freezes:

- `schema_version: 4`
- `worker_protocol: 4`
- `expected_worker_manifest`

The worker computes the SHA-256 manifest of the fixed file set before candidate network traffic. A protocol mismatch returns `TARGET_WORKER_VERSION_MISMATCH`; a file-set mismatch returns `TARGET_WORKER_BUILD_MISMATCH`.

## Stage ownership

| Stage | Controller | Target VPS |
|---|---:|---:|
| inventory guard | yes | no |
| freeze job/manifest | yes | no |
| egress/location | no | yes |
| incumbent config discovery | no | yes |
| regional/source discovery | no | yes |
| candidate DNS/TLS/HEAD/platform | no | yes |
| fast/deep benchmark | no | yes |
| local Reality integration | no | yes |
| final artifact rendering | yes | no |
