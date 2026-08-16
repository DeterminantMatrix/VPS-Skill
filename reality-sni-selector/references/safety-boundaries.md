# Safety boundaries

## Allowed network activity

- One explicitly selected owned VPS per run.
- Candidate traffic originates from that VPS.
- IPv4 only for candidate qualification.
- TCP/443 only.
- DNS lookups, short TLS handshakes, bounded metadata API requests, passive CT queries, and short HTTPS HEAD requests.
- Local Reality listeners only on `127.0.0.1` with ephemeral/high ports.

## Forbidden activity

- Raw CIDR scanning.
- Port scanning or trying alternate candidate ports.
- Arbitrary user-provided destination IP/port execution.
- Arbitrary remote shell.
- Uploading code during a normal run.
- Production sing-box edits/restarts.
- Firewall, route, SSH, kernel, or network changes.
- Webpage body downloads, large files, streaming, throughput tests, MTR/traceroute/iperf3.
- Persisting secrets or raw secret-bearing temporary configs.

## Probe budgets

All limits are frozen before probing. A candidate excluded because a cap is reached receives `DEFERRED:PROBE_BUDGET` or `NOT_SELECTED`; it is not a rejection.

## Cleanup invariant

Reality temporary processes and files are a safety invariant. If cleanup cannot be proven, stop the remaining Reality batch with `TARGET_DIRTY_STATE`.
