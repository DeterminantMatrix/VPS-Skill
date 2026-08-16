# Dependencies

Normal runs never install system packages automatically.

## Controller

Required:

- Python 3.10+
- OpenSSH `ssh` client
- PyYAML for inventory parsing

Required only when automatic worker bootstrap/upgrade is needed:

- OpenSSH `scp` client

If the exact v4.2 worker is already ready, no transfer is performed.

## Target worker

Required:

- Python 3.10+ at `/usr/bin/python3` for the fixed wrapper/bootstrap contract
- permission to manage `/opt/reality-sni-selector` and `/usr/local/bin/reality-sni-target-worker` when bootstrap/upgrade is needed (normally a root SSH alias)
- system CA trust store
- `curl` for the loopback Reality HEAD integration test
- `sing-box` for final Reality integration

Optional but recommended:

- `dig` for CNAME evidence

If `dig` is absent, edge evidence may become `REVIEW:EDGE_UNKNOWN`; missing tooling is not proof of DIRECT and is not automatically proof of public CDN.

## Installation boundary

v4.2 may bootstrap or upgrade only its own fixed worker files; this is not a system-package installation. Installing missing Python/curl/sing-box/dig packages, changing sudo/SSH privileges, or repairing unrelated system state remains a separate maintenance action.
