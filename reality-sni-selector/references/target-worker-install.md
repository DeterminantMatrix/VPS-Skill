# Target worker installation / automatic lifecycle v4.3.5

Normal v4.3.5 selection owns readiness of its reviewed fixed worker. Manual predeployment is no longer required when the existing SSH alias can write the fixed paths.

See `worker-lifecycle.md` for the automatic sequence.

## Managed file set

The six manifest-covered worker files are installed together under `/opt/reality-sni-selector/`:

```text
common.py
target_discovery.py
target_probe.py
benchmark.py
reality_selftest.py
target_worker.py
```

The managed directory also contains `.managed.json` with protocol/version/manifest/wrapper-hash metadata.

The reviewed wrapper is installed exactly at:

```text
/usr/local/bin/reality-sni-target-worker
```

It accepts only two fixed operations:

```text
/usr/local/bin/reality-sni-target-worker identity
/usr/local/bin/reality-sni-target-worker run
```

`identity` is read-only and generates no candidate traffic. `run` executes `/usr/bin/python3 /opt/reality-sni-selector/target_worker.py run`.

## Existing installations

- no worker paths: install automatically;
- valid `.managed.json`: upgrade automatically if stale;
- exact reviewed pre-marker v4/v4.1 manifest/wrapper: treat as legacy-managed and upgrade;
- anything else at the fixed paths: fail `WORKER_PATH_CONFLICT` without overwriting.

Existing managed installations are backed up before replacement. Stage and post-install hashes must match before selection can freeze.

Use `--worker-bootstrap never` when the user explicitly wants a no-write readiness check. Use `--worker-ready-only` to prepare/verify the worker without freezing or running SNI candidate tests.
