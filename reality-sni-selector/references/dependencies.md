# Dependencies

Normal runs never install system packages automatically.

## Controller

Required:

- Python 3.10+
- OpenSSH `ssh` client
- PyYAML for inventory parsing

Required only when automatic worker bootstrap/upgrade is needed:

- OpenSSH `scp` client

If the exact v4.5 worker is already ready, no transfer is performed.

## Target worker

Required:

- Python 3.10+ at `/usr/bin/python3` for the fixed wrapper/bootstrap contract
- permission to manage `/opt/reality-sni-selector` and `/usr/local/bin/reality-sni-target-worker` when bootstrap/upgrade is needed (normally a root SSH alias)
- system CA trust store
- `curl` for the loopback Reality HEAD integration test
- `sing-box` for final Reality integration

Optional but recommended for ordinary runs:

- `dig` for CNAME evidence

If `dig` is absent, edge evidence may become `REVIEW:EDGE_UNKNOWN`; missing tooling is not proof of DIRECT and is not automatically proof of public CDN. On supported apt targets, the controller automatically installs the smallest package that provides `dig` when the command is absent or fails its functional probe. It records the package/command state first, removes packages introduced solely for that run immediately after measurement, and verifies restoration; do not use broad `autoremove` or remove a pre-existing/shared package. Unsupported package managers, an unknown broken binary, failed installation, or uncertain cleanup is a run-level `TARGET_DIRTY_STATE`/blocked condition and must be reported.

## Installation boundary

v4.5 may bootstrap or upgrade only its own fixed worker files; this is not a system-package installation. Installing missing Python/curl/sing-box packages, changing sudo/SSH privileges, or repairing unrelated system state remains a separate maintenance action. The temporary `dig` exception is limited to the requested SNI measurement and must leave no newly installed package behind.
