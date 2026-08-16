# Target worker installation / v4.1 redeploy / upgrade

This is a separately authorized administrative action on an owned VPS. It is not part of normal selection.

Install these reviewed files together under `/opt/reality-sni-selector/`:

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

After deployment, verify that invoking the wrapper without `run` returns `FIXED_COMMAND_REQUIRED` and that a controller job reports worker protocol 4 with the expected manifest.

After any v4.1 code update, redeploy the reviewed worker file set together. The controller manifest intentionally rejects stale v4/v4.1 worker mixtures.
