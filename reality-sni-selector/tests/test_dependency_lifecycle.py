#!/usr/bin/env python3
import importlib
import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
dependency_lifecycle = importlib.import_module("dependency_lifecycle")


class DependencyLifecycleTest(unittest.TestCase):
    def test_ready_dig_requires_no_install(self):
        response = (0, "STATUS=READY\nDIG_PATH=/usr/bin/dig\nDIG_VERSION=DIG 9.18.49\n", "")
        with mock.patch.object(dependency_lifecycle, "_remote", return_value=response) as remote:
            result = dependency_lifecycle.ensure_dig("target")
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "NONE")
        self.assertFalse(result["required"])
        self.assertEqual(remote.call_count, 1)

    def test_missing_dig_is_installed_and_cleanup_is_required(self):
        responses = [
            (0, "STATUS=MISSING\n", ""),
            (0, "\n".join([
                "MANAGER=apt",
                "CANDIDATE=bind9-dnsutils",
                "PRE_PACKAGE_LIST_SHA256=alpha",
                "CANDIDATE_INSTALLED=no",
                "NEW_PACKAGES=bind9-dnsutils,libfoo:amd64",
                "INSTALL_RC=0",
                "INSTALL_SUMMARY=installed",
                "PHASE_STATUS=OK",
            ]) + "\n", ""),
            (0, "STATUS=READY\nDIG_PATH=/usr/bin/dig\nDIG_VERSION=DIG 9.18.49\n", ""),
        ]
        with mock.patch.object(dependency_lifecycle, "_remote", side_effect=responses):
            result = dependency_lifecycle.ensure_dig("target")
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "INSTALLED")
        self.assertTrue(result["cleanup_required"])
        self.assertEqual(result["packages"], ["bind9-dnsutils", "libfoo:amd64"])

    def test_unsupported_manager_fails_closed(self):
        responses = [
            (0, "STATUS=MISSING\n", ""),
            (0, "MANAGER=unsupported\nPHASE_STATUS=UNSUPPORTED_MANAGER\n", ""),
        ]
        with mock.patch.object(dependency_lifecycle, "_remote", side_effect=responses):
            result = dependency_lifecycle.ensure_dig("target")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "DIG_AUTO_INSTALL_UNSUPPORTED")

    def test_cleanup_verifies_package_list_digest(self):
        lifecycle = {
            "required": True,
            "cleanup_required": True,
            "package_manager": "apt",
            "pre_package_list_sha256": "alpha",
            "packages": ["bind9-dnsutils"],
        }
        response = (0, "\n".join([
            "REMOVE_RC=0",
            "DIRTY=no",
            "POST_PACKAGE_LIST_SHA256=alpha",
            "PHASE_STATUS=OK",
        ]) + "\n", "")
        with mock.patch.object(dependency_lifecycle, "_remote", return_value=response):
            result = dependency_lifecycle.restore_dig("target", lifecycle)
        self.assertTrue(result["cleanup"]["ok"])
        self.assertEqual(result["cleanup"]["status"], "RESTORED")

    def test_dirty_cleanup_is_reported(self):
        lifecycle = {
            "required": True,
            "cleanup_required": True,
            "package_manager": "apt",
            "pre_package_list_sha256": "alpha",
            "packages": ["bind9-dnsutils"],
        }
        response = (0, "\n".join([
            "REMOVE_RC=0",
            "DIRTY=yes",
            "POST_PACKAGE_LIST_SHA256=beta",
            "PHASE_STATUS=FAILED",
        ]) + "\n", "")
        with mock.patch.object(dependency_lifecycle, "_remote", return_value=response):
            result = dependency_lifecycle.restore_dig("target", lifecycle)
        self.assertFalse(result["cleanup"]["ok"])
        self.assertEqual(result["cleanup"]["status"], "TARGET_DIRTY_STATE")


if __name__ == "__main__":
    raise SystemExit(unittest.main())
