# Safety boundaries

## Allowed selection activity

- one explicitly selected owned VPS;
- inventory read;
- one fixed SSH command through an existing alias;
- target-originated IPv4 TCP/443 candidate traffic;
- DNS, short TLS handshakes, bounded metadata APIs, passive CT, and HEAD requests;
- loopback-only temporary Reality listeners;
- local run artifacts/report output.

## Forbidden selection activity

- raw CIDR or port scanning;
- arbitrary user destination/port execution;
- arbitrary remote shell;
- uploading or updating worker code during selection;
- modifying production sing-box/service/firewall/route/SSH/network state;
- installing packages;
- webpage bodies, large files, streaming, throughput, MTR/traceroute/iperf3;
- persisting secrets or raw secret-bearing configs/stderr;
- silently editing Skill/AGENTS/memory/Git state.

## Worker contract

Selection requires the fixed absolute remote command and a matching v4 manifest. Version/build mismatch fails before candidate traffic.

## Cleanup invariant

If temporary Reality process/file cleanup cannot be proven, stop the remaining Reality batch with `TARGET_DIRTY_STATE`.

## Repair boundary

Worker deployment, source edits, package installation, and Git changes belong to separately authorized MAINTENANCE / REPAIR MODE. Start a new selection run after any repair.
