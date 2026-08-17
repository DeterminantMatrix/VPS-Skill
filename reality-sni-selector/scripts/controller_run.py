#!/usr/bin/env python3
"""v4.4 entrypoint: stable controller runtime plus deterministic decision postprocessing."""
from __future__ import annotations

import contextlib
import io
import re
import subprocess
from pathlib import Path
from typing import Any

import controller_runtime as _runtime
from decision_postprocess import postprocess_run

# Re-export the stable public helpers used by tests/integrations.
build_job = _runtime.build_job
load_seeds = _runtime.load_seeds
auto_seed_file = _runtime.auto_seed_file
resolve_inventory_path = _runtime.resolve_inventory_path
inventory_guard = _runtime.inventory_guard
prepare_run_dir = _runtime.prepare_run_dir
sanitize_remote_stderr = _runtime.sanitize_remote_stderr
classify_remote_failure = _runtime.classify_remote_failure
lifecycle = _runtime.lifecycle
core = _runtime.core


def run_remote(alias: str, job: dict[str, Any], timeout: int):
    # Keep monkeypatch-friendly behavior for callers/tests while delegating to the stable runtime.
    _runtime.subprocess = subprocess
    return _runtime.run_remote(alias, job, timeout)


def main() -> int:
    # Capture only the controller's local stdout so we can locate its dedicated run directory,
    # then replay it verbatim to the caller before deterministic v4.4 postprocessing.
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = _runtime.main()
    output = buffer.getvalue()
    print(output, end="")
    matches = re.findall(r"^RUN_DIR:(.+)$", output, flags=re.MULTILINE)
    if matches:
        try:
            postprocess_run(Path(matches[-1]).expanduser().resolve())
        except Exception as exc:
            # Measurement already completed; fail visibly rather than silently returning a thin report.
            print(f"DECISION_POSTPROCESS_FAILED:{type(exc).__name__}")
            return 4 if rc == 0 else rc
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
