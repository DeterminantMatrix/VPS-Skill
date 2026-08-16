# Target worker installation / v4.1 redeploy / upgrade

This is a separately authorized administrative action on an owned VPS. It is not part of normal selection.

Before replacing an existing installation, inspect and back up the current `/opt/reality-sni-selector/` directory and `/usr/local/bin/reality-sni-target-worker` when present. Then install these reviewed files together under `/opt/reality-sni-selector/`:

```text
common.py
target_discovery.py
target_probe.py
benchmark.py
reality_selftest.py
target_worker.py
```

Install the reviewed wrapper exactly at:

```text
/usr/local/bin/reality-sni-target-worker
```

The wrapper accepts only:

```text
/usr/local/bin/reality-sni-target-worker run
```

and executes `/usr/bin/python3 /opt/reality-sni-selector/target_worker.py run`.

Keep files root-owned or equivalently protected. Do not make the wrapper accept configurable script paths or arbitrary commands.

## v4 upgrade requirement

v4 freezes a SHA-256 manifest over the six target-worker Python files. After changing any of those files, explicitly redeploy the complete set before the next selection run. A stale deployment must fail closed with `TARGET_WORKER_BUILD_MISMATCH` rather than continue with mixed code.

After deployment, verify that invoking the wrapper without `run` returns `FIXED_COMMAND_REQUIRED`. Then run `python3 scripts/controller_run.py <inventory-target> --worker-check-only`; require `WORKER_CONTRACT_OK`, protocol 4, implementation 4.1, and the expected six-file manifest before starting a new selection run. If the fixed path or its interpreter cannot start, classify it as `TARGET_WORKER_UNAVAILABLE`.

After any v4.1 code update, redeploy the reviewed worker file set together. The controller manifest intentionally rejects stale v4/v4.1 worker mixtures.
