# Selection vs maintenance v4.2

## SELECTION MODE

Normal SNI selection may:

- read inventory;
- probe the fixed worker identity;
- install/upgrade the Skill's own reviewed worker at its fixed managed paths when absent/stale;
- back up an existing managed/recognized-legacy worker and verify hashes;
- freeze only after exact readiness;
- invoke `/usr/local/bin/reality-sni-target-worker run` for bounded target-side discovery/probes;
- write local run artifacts and reports.

It must not:

- overwrite unknown files at the worker paths;
- edit the Skill source, AGENTS/memory/project documentation, or Git history;
- install system packages;
- alter production sing-box, services, firewall, routing, SSH, or networking.

`--worker-bootstrap never` keeps selection read-only with respect to worker files and fails if the exact worker is not ready.

## MAINTENANCE / REPAIR MODE

Use maintenance for conditions outside the managed worker lifecycle, including:

- `WORKER_PATH_CONFLICT`;
- missing permissions or SSH policy changes;
- unavailable `/usr/bin/python3`, curl, or sing-box that requires package/system work;
- source-code edits or debugging;
- production service/network changes;
- project documentation or Git changes requested by the user.

After any maintenance that changes worker source or runtime state, start a new selection invocation. v4.2 itself avoids creating a frozen job before worker readiness, so a bootstrap-only failure does not create a resumable SNI run.

## Read-only Skill validation

Do not run `py_compile` against an installed read-only Skill without relocating the bytecode cache. Validate from a writable checkout when possible. If syntax compilation is needed in place, use:

```text
PYTHONPYCACHEPREFIX=/tmp/reality-sni-pycache python3 -m py_compile <file.py>
```

An `EROFS` caused only by `__pycache__` creation is a validation-environment error, not evidence that the Skill source is invalid.
