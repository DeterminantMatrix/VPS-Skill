# Managed worker lifecycle v4.3.5

The user selects a VPS; the Skill owns readiness of its own fixed target worker. Worker readiness is a **pre-freeze control-plane step**, not candidate measurement.

## Readiness sequence

1. Resolve the inventory target and existing SSH alias.
2. Run the fixed read-only identity probe:

```text
/usr/local/bin/reality-sni-target-worker identity
```

3. Require protocol 4, implementation 4.3.5, the exact six-file worker manifest, and the exact reviewed wrapper hash.
4. If exact, continue without writes.
5. If absent/stale/legacy and `--worker-bootstrap auto` is enabled, bootstrap or upgrade only the managed worker paths.
6. Probe identity again. Freeze the SNI job only after exact readiness.

`--worker-bootstrap never` disables automatic worker writes and fails closed when readiness is not exact.

`--worker-ready-only` performs the lifecycle check/bootstrap and exits before creating a frozen SNI job or generating candidate traffic.

## Fixed managed paths

Automatic lifecycle management may write only:

```text
/opt/reality-sni-selector/
  common.py
  target_discovery.py
  target_probe.py
  benchmark.py
  reality_selftest.py
  target_worker.py
  .managed.json

/usr/local/bin/reality-sni-target-worker
```

Temporary transfer files are restricted to manifest-derived names under `/tmp/reality-sni-bootstrap-*.{py,tar.gz}` and are removed best-effort.

The bootstrap never modifies production sing-box config, services, firewall, routing, SSH config, network settings, or system packages.

## Ownership and conflict policy

Automatic installation is allowed when both managed paths are absent.

Automatic upgrade is allowed when either:

- `.managed.json` identifies `managed_by: reality-sni-selector`; or
- the six-file manifest/wrapper hash exactly matches a reviewed pre-marker v4/v4.1 install.

If files already occupy the fixed paths but cannot be proven to be a managed/known-legacy installation, return:

```text
WORKER_PATH_CONFLICT
```

Never overwrite unknown content.

## Atomic install and rollback

The target-side bootstrap:

- accepts only the fixed payload member set;
- rejects symlinks, nested paths, extra files, oversized files, or hash mismatch;
- stages the worker under `/opt` and the wrapper under `/usr/local/bin`;
- verifies the staged six-file manifest and wrapper SHA-256;
- backs up an existing managed worker before replacement;
- atomically activates staged paths;
- verifies hashes again after activation;
- attempts rollback if activation verification fails.

A successful lifecycle result records `INSTALLED`, `UPGRADED`, or `ALREADY_READY` plus manifest and backup metadata in `worker-lifecycle.json`.

## Privilege requirement

The existing SSH alias must have permission to manage the fixed paths. The default deployment expects a root SSH session. If the alias cannot write those paths, fail closed with `BOOTSTRAP_PERMISSION_DENIED` or the relevant transfer/SSH error. Do not introduce sudo prompts or modify SSH credentials automatically.
