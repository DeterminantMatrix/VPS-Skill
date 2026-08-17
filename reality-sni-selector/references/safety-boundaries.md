# Safety boundaries

## Allowed selection activity

- one explicitly selected owned VPS;
- local inventory read and existing SSH alias use;
- fixed worker identity probing;
- automatic install/upgrade of **only** the reviewed managed worker paths described in `worker-lifecycle.md`;
- backup, manifest/wrapper hash verification, and managed marker writes for that worker lifecycle;
- one fixed measurement command after freeze;
- target-originated IPv4 TCP/443 candidate traffic;
- DNS, short TLS handshakes, bounded metadata APIs, passive CT, and HEAD requests;
- loopback-only temporary Reality listeners;
- local run artifacts/report output.

## Forbidden selection activity

- raw CIDR or port scanning;
- arbitrary user destination/port execution;
- arbitrary remote shell or user-provided remote commands;
- writing outside the fixed managed worker paths and manifest-derived `/tmp` bootstrap files;
- overwriting unknown/unmanaged content at worker paths;
- modifying production sing-box/service/firewall/route/SSH/network state;
- installing or upgrading system packages;
- webpage bodies, large files, streaming, throughput, MTR/traceroute/iperf3;
- persisting secrets or raw secret-bearing configs/stderr;
- silently editing Skill/AGENTS/memory/Git state.

## Worker contract

Freeze only after worker identity matches protocol 4, implementation 4.5, the expected six-file manifest, and reviewed wrapper hash. Unknown existing worker paths fail with `WORKER_PATH_CONFLICT`. The measurement command remains fixed at `/usr/local/bin/reality-sni-target-worker run`.

## Cleanup invariant

If temporary Reality process/file cleanup cannot be proven, stop the remaining Reality batch with `TARGET_DIRTY_STATE`.

## Maintenance boundary

Normal selection may manage the Skill's own fixed worker runtime. MAINTENANCE / REPAIR MODE is still required for source-code edits, unknown path conflicts, permission/SSH remediation, package installation, production service changes, or other environment repair outside the managed runtime.
