# Target worker installation

This is a one-time administrative deployment on an owned VPS. It is deliberately separate from a normal SNI selection run.

Install these reviewed files together in a fixed directory such as `/opt/reality-sni-selector/`:

```text
common.py
target_discovery.py
target_probe.py
benchmark.py
reality_selftest.py
target_worker.py
```

Expose a fixed command named `reality-sni-target-worker` that executes:

```text
python3 /opt/reality-sni-selector/target_worker.py "$@"
```

The normal controller only invokes:

```text
reality-sni-target-worker run
```

Do not make the wrapper accept a configurable script path or arbitrary command. Do not install/update the worker automatically during selection.

After installation, verify locally on the target that:

```text
reality-sni-target-worker
```

returns `FIXED_COMMAND_REQUIRED`, and that only the `run` subcommand accepts a JSON job on stdin.

Keep the worker files root-owned or otherwise protected from the untrusted user context that can initiate selection jobs.
