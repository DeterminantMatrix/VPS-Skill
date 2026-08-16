#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import controller_run  # noqa: E402
import worker_bootstrap  # noqa: E402
import worker_lifecycle  # noqa: E402
from common import IMPLEMENTATION_VERSION, WORKER_PROTOCOL, compute_worker_manifest  # noqa: E402


class WorkerLifecycleTests(unittest.TestCase):
    def _payload(self, root: Path) -> tuple[Path, dict[str, str]]:
        archive = root / "payload.tar.gz"
        hashes = worker_lifecycle.build_payload_archive(SCRIPTS, archive)
        return archive, hashes

    def test_payload_has_only_fixed_worker_files_and_wrapper(self):
        with tempfile.TemporaryDirectory() as td:
            archive, hashes = self._payload(Path(td))
            self.assertEqual(hashes["manifest"], compute_worker_manifest(SCRIPTS))
            with tarfile.open(archive, "r:gz") as tf:
                self.assertEqual(
                    set(tf.getnames()),
                    set(worker_bootstrap.TARGET_FILES) | {worker_bootstrap.WRAPPER_NAME},
                )

    def test_install_absent_worker_creates_managed_marker(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive, hashes = self._payload(root)
            install_dir = root / "opt" / "reality-sni-selector"
            wrapper = root / "usr" / "local" / "bin" / "reality-sni-target-worker"
            result = worker_bootstrap.install_payload(
                archive,
                hashes["manifest"],
                hashes["wrapper_sha256"],
                IMPLEMENTATION_VERSION,
                WORKER_PROTOCOL,
                install_dir=install_dir,
                wrapper_path=wrapper,
            )
            self.assertEqual((result["status"], result["action"]), ("READY", "INSTALLED"))
            marker = json.loads((install_dir / ".managed.json").read_text())
            self.assertEqual(marker["managed_by"], "reality-sni-selector")
            self.assertEqual(marker["manifest"], hashes["manifest"])
            self.assertEqual(compute_worker_manifest(install_dir), hashes["manifest"])
            self.assertTrue(os.access(wrapper, os.X_OK))

    def test_recognized_legacy_worker_is_upgraded_with_backup(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive, hashes = self._payload(root)
            install_dir = root / "opt" / "reality-sni-selector"
            wrapper = root / "usr" / "local" / "bin" / "reality-sni-target-worker"
            install_dir.mkdir(parents=True)
            wrapper.parent.mkdir(parents=True)
            for name in worker_bootstrap.TARGET_FILES:
                (install_dir / name).write_bytes((SCRIPTS / name).read_bytes())
            wrapper.write_bytes((SCRIPTS / worker_bootstrap.WRAPPER_NAME).read_bytes())
            wrapper.chmod(0o755)
            legacy_manifest = worker_bootstrap.compute_manifest(install_dir)
            legacy_wrapper = hashlib.sha256(wrapper.read_bytes()).hexdigest()
            result = worker_bootstrap.install_payload(
                archive,
                hashes["manifest"],
                hashes["wrapper_sha256"],
                IMPLEMENTATION_VERSION,
                WORKER_PROTOCOL,
                install_dir=install_dir,
                wrapper_path=wrapper,
                legacy_manifests={legacy_manifest},
                legacy_wrapper_hashes={legacy_wrapper},
            )
            self.assertEqual(result["action"], "UPGRADED")
            self.assertEqual(result["previous_state"], "LEGACY_MANAGED")
            self.assertTrue(Path(result["backup"]).is_dir())

    def test_unknown_existing_worker_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive, hashes = self._payload(root)
            install_dir = root / "opt" / "reality-sni-selector"
            wrapper = root / "usr" / "local" / "bin" / "reality-sni-target-worker"
            install_dir.mkdir(parents=True)
            wrapper.parent.mkdir(parents=True)
            for name in worker_bootstrap.TARGET_FILES:
                (install_dir / name).write_text("unknown", encoding="utf-8")
            wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            wrapper.chmod(0o755)
            with self.assertRaises(worker_bootstrap.BootstrapError) as ctx:
                worker_bootstrap.install_payload(
                    archive,
                    hashes["manifest"],
                    hashes["wrapper_sha256"],
                    IMPLEMENTATION_VERSION,
                    WORKER_PROTOCOL,
                    install_dir=install_dir,
                    wrapper_path=wrapper,
                    legacy_manifests=set(),
                    legacy_wrapper_hashes=set(),
                )
            self.assertEqual(ctx.exception.code, "WORKER_PATH_CONFLICT")
            self.assertEqual((install_dir / "common.py").read_text(), "unknown")

    def test_probe_missing_worker(self):
        proc = subprocess.CompletedProcess([], 127, stdout=b"", stderr=b"bash: /usr/local/bin/reality-sni-target-worker: No such file or directory\n")
        with patch.object(worker_lifecycle, "_run", return_value=proc):
            out = worker_lifecycle.probe_worker("lax-hostdzire", "a" * 64)
        self.assertEqual((out["status"], out["ready"]), ("WORKER_MISSING", False))

    def test_probe_exact_identity_ready(self):
        manifest = "a" * 64
        payload = json.dumps({
            "schema_version": 4,
            "status": "IDENTITY",
            "worker": {"protocol": WORKER_PROTOCOL, "implementation_version": IMPLEMENTATION_VERSION, "manifest": manifest},
        }).encode()
        proc = subprocess.CompletedProcess([], 0, stdout=payload, stderr=b"")
        with patch.object(worker_lifecycle, "_run", return_value=proc):
            out = worker_lifecycle.probe_worker("lax-hostdzire", manifest)
        self.assertTrue(out["ready"])
        self.assertEqual(out["status"], "READY")

    def test_controller_does_not_freeze_when_worker_readiness_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inventory = root / "hosts.yaml"
            inventory.write_text(
                """hosts:\n  lax-hostdzire:\n    inventory_id: lax-hostdzire\n    alias: lax-hostdzire\n    name: HostDZire LAX\n    region: US\n    access: {method: ssh, address: 23.19.228.207}\n    capabilities: {ssh: true}\n    state: {retired: false, forbidden: false}\n""",
                encoding="utf-8",
            )
            old_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.object(sys, "argv", ["controller_run.py", "hostzdire", "--inventory", str(inventory)]), patch.object(
                    controller_run.lifecycle,
                    "ensure_worker_ready",
                    return_value={"status": "WORKER_PATH_CONFLICT", "ready": False, "action": "BOOTSTRAP_FAILED", "expected_manifest": "a" * 64},
                ):
                    rc = controller_run.main()
            finally:
                os.chdir(old_cwd)
            self.assertEqual(rc, 3)
            runs = [p for p in root.iterdir() if p.is_dir() and p.name.startswith("sni-lax-hostdzire-")]
            self.assertEqual(len(runs), 1)
            self.assertFalse((runs[0] / "frozen-run.json").exists())
            self.assertTrue((runs[0] / "worker-lifecycle.json").exists())


if __name__ == "__main__":
    unittest.main()
