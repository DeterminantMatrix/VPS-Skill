from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import decision_postprocess  # noqa: E402
from controller_run import (  # noqa: E402
    classify_remote_failure,
    inventory_guard,
    prepare_run_dir,
    sanitize_remote_stderr,
)


class ControllerRuntimeTests(unittest.TestCase):
    def _inventory(self, root: Path, extra: str = "") -> Path:
        path = root / "hosts.yaml"
        path.write_text(
            """
hosts:
  lax-hostdzire:
    inventory_id: lax-hostdzire
    alias: lax-hostdzire
    name: HostDZire LAX
    region: US
    access:
      method: ssh
      address: 23.19.228.207
      hostname: 23.19.228.207
    capabilities:
      ssh: true
    state:
      retired: false
      forbidden: false
""" + extra,
            encoding="utf-8",
        )
        return path

    def test_unique_fuzzy_hostdzire_resolution(self):
        with tempfile.TemporaryDirectory() as td:
            guard = inventory_guard(self._inventory(Path(td)), "hostzdire")
            self.assertEqual(guard["inventory_id"], "lax-hostdzire")
            self.assertEqual(guard["target_ip"], "23.19.228.207")
            self.assertEqual(guard["selector_resolution"]["mode"], "FUZZY_UNIQUE")
            self.assertEqual(guard["selector_resolution"]["warning"], "TARGET_SELECTOR_FUZZY_MATCH")

    def test_similarly_named_targets_are_ambiguous(self):
        with tempfile.TemporaryDirectory() as td:
            extra = """
  nyc-hostdzire:
    inventory_id: nyc-hostdzire
    alias: nyc-hostdzire
    name: HostDZire NYC
    region: US
    access:
      method: ssh
      address: 198.51.100.19
    capabilities:
      ssh: true
    state:
      retired: false
      forbidden: false
"""
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                inventory_guard(self._inventory(Path(td), extra), "hostzdire")

    def test_dedicated_run_directory(self):
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            old = Path.cwd()
            try:
                import os
                os.chdir(parent)
                run_dir = prepare_run_dir(None, "lax-hostdzire")
            finally:
                os.chdir(old)
            self.assertEqual(run_dir.parent, parent)
            self.assertTrue(run_dir.name.startswith("sni-lax-hostdzire-"))

    def test_no_such_file_is_worker_unavailable(self):
        status, detail = classify_remote_failure(127, "bash: /usr/local/bin/reality-sni-target-worker: No such file or directory")
        self.assertEqual(status, "TARGET_WORKER_UNAVAILABLE")
        self.assertEqual(detail, "WORKER_PATH_OR_INTERPRETER_MISSING")

    def test_stderr_redacts_secret_assignments(self):
        text = sanitize_remote_stderr(b"token=abc123 password: hello No such file or directory")
        self.assertNotIn("abc123", text)
        self.assertNotIn("hello", text)
        self.assertIn("<redacted>", text)

    def test_decision_postprocess_writes_structured_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            result = {
                "status": "SUCCESS",
                "coverage": {"status": "SPARSE", "validated": 57, "goal": 200, "profile": "quick"},
                "frozen_run": {"incumbent": "old.example", "profile": {"latency_target_ms": 60.0, "p50_equivalence_ms": 2.0}},
                "counts": {"selectable_target": 5},
                "top5": [],
                "comparison": [],
                "incumbent_assessment": {"verdict": "暂无法评估", "code": "UNABLE_TO_ASSESS", "metrics": {}},
            }
            (run_dir / "target-result.json").write_text(json.dumps(result), encoding="utf-8")
            self.assertTrue(decision_postprocess.postprocess_run(run_dir))
            self.assertTrue((run_dir / "decision-summary.json").is_file())
            self.assertTrue((run_dir / "top5.json").is_file())
            self.assertIn("Reality SNI 优选决策报告", (run_dir / "report.md").read_text(encoding="utf-8"))

    def test_stage_status_freeze_text_has_no_stale_version_literal(self):
        source = (ROOT / "scripts" / "controller_runtime.py").read_text(encoding="utf-8")
        self.assertNotIn("v4.2 quick profile frozen", source)
        self.assertIn("profile frozen only after exact worker readiness", source)

    def test_quality_below_target_is_normalized_by_v45_wrapper(self):
        source = (ROOT / "scripts" / "controller_run.py").read_text(encoding="utf-8")
        self.assertIn("TARGET_MEASURED_RUN_STATUS:SUCCESS_QUALITY_BELOW_TARGET", source)


if __name__ == "__main__":
    unittest.main()
