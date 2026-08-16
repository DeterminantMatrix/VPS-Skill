from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

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


if __name__ == "__main__":
    unittest.main()
