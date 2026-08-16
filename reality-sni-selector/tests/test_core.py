#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import benchmark
import controller_run
import reality_selftest
from benchmark import apply_deep_policy, deep_rank_key
from common import mad, percentile, registrable_domain, validate_hostname
from controller_run import build_job, inventory_guard
from target_probe import classify_front_door, classify_network_organization
from target_worker import select_probe_pool, validate_job


class CoreTests(unittest.TestCase):
    def test_hostname_and_domain(self):
        self.assertEqual(validate_hostname("WWW.Example.COM."), "www.example.com")
        self.assertEqual(registrable_domain("a.b.example.co.uk"), "example.co.uk")

    def test_stats_helpers(self):
        self.assertEqual(percentile([10, 20, 30, 40, 50], 0.5), 30)
        self.assertEqual(mad([10, 20, 30, 40, 50]), 10)

    def test_vercel_is_public_cdn(self):
        row = classify_front_door("www.example.org", ["foo.vercel-dns-016.com"], "dig", {"success": True, "headers": {}})
        self.assertEqual(row["class"], "PUBLIC_CDN_CONFIRMED")

    def test_pantheon_header_is_shared_platform(self):
        row = classify_front_door("lapl.org", [], "dig", {"success": True, "headers": {"x-pantheon-styx-hostname": "styx-us-a"}})
        self.assertEqual((row["class"], row["platform"]), ("SHARED_PLATFORM_CONFIRMED", "Pantheon"))

    def test_pantheon_org_is_shared_platform(self):
        cls, name, _ = classify_network_organization({"organization": "Pantheon Systems, Inc."})
        self.assertEqual((cls, name), ("SHARED_PLATFORM_CONFIRMED", "Pantheon"))

    def test_missing_head_is_not_direct(self):
        row = classify_front_door("www.example.org", [], "dig", {"success": False, "headers": {}})
        self.assertEqual(row["class"], "UNKNOWN_EDGE_EVIDENCE")

    def test_deep_reliability_gate(self):
        row = {"hostname": "a.example", "success_rate": .9, "per_ip": {"1.1.1.1": {"samples": 10, "success_rate": .9}}, "hard_rejections": [], "eligibility": "ELIGIBLE"}
        self.assertIn("HARD:TLS_SUCCESS_LT_95", apply_deep_policy(row)["hard_rejections"])

    def test_policy_precedes_latency(self):
        clean = {"hostname": "clean.example", "eligibility": "ELIGIBLE", "success_rate": 1.0, "p50_ms": 50, "p95_ms": 60, "mad_ms": 2, "front_door": {"class": "DIRECT_LIKELY"}, "per_ip": {}, "sources": []}
        review = {"hostname": "review.example", "eligibility": "REVIEW_REQUIRED", "success_rate": 1.0, "p50_ms": 20, "p95_ms": 25, "mad_ms": 1, "front_door": {"class": "UNKNOWN_EDGE_EVIDENCE"}, "per_ip": {}, "sources": []}
        self.assertLess(deep_rank_key(clean), deep_rank_key(review))

    def test_fixed_elf_precedes_path_wrapper(self):
        with tempfile.TemporaryDirectory() as td:
            binary = Path(td) / "sing-box"
            binary.write_bytes(b"\x7fELFfixture")
            os.chmod(binary, 0o755)
            with patch.object(reality_selftest, "SING_BOX_FIXED_PATHS", (str(binary),)), patch.object(reality_selftest.shutil, "which", return_value="/tmp/wrapper"):
                self.assertEqual(reality_selftest.find_sing_box(), str(binary))

    def _guard(self):
        return {"inventory_id": "best-vm-us", "alias": "best-vm-us", "target_ip": "155.254.127.55", "region": "US"}

    def test_inventory_and_quick_profile(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "hosts.yaml"
            p.write_text("hosts:\n  best-vm-us:\n    inventory_id: best-vm-us\n    alias: best-vm-us\n    region: US\n    access: {method: ssh, address: 155.254.127.55}\n    capabilities: {ssh: true}\n    state: {retired: false, forbidden: false}\n", encoding="utf-8")
            guard = inventory_guard(p, "155.254.127.55")
        job = build_job(guard, [], "old.example", "explicit", worker_manifest="a" * 64)
        validate_job(json.loads(json.dumps(job)))
        self.assertEqual((job["implementation_version"], job["limits"]["eligibility_pool"], job["limits"]["fast_samples"]), ("4.1", 60, 3))

    def test_audit_profile(self):
        job = build_job(self._guard(), [], "old.example", "explicit", worker_manifest="a" * 64, profile_mode="audit")
        validate_job(json.loads(json.dumps(job)))
        self.assertEqual((job["profile"]["coverage_goal"], job["limits"]["eligibility_pool"], job["limits"]["fast_samples"]), (400, 120, 5))

    def test_old_inventory_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "hosts.yaml"
            p.write_text("hosts:\n  best-vm-us:\n    ipv4: 155.254.127.55\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                inventory_guard(p, "155.254.127.55")

    def test_port_change_rejected(self):
        job = build_job(self._guard(), [], "old.example", "explicit", worker_manifest="a" * 64)
        job["port"] = 8443
        with self.assertRaises(ValueError):
            validate_job(job)

    def test_deep_reuses_fast_samples(self):
        candidate = {"hostname": "a.example", "incumbent": False, "sources": [], "organizations": [], "eligibility": "ELIGIBLE", "front_door": {"class": "DIRECT_LIKELY"}, "warnings": [], "review": [], "hard_rejections": [], "current_ipv4": ["1.1.1.1"]}
        prior = [{**candidate, "samples": [{"success": True, "ip": "1.1.1.1", "elapsed_ms": 10.0}, {"success": True, "ip": "1.1.1.1", "elapsed_ms": 11.0}, {"success": True, "ip": "1.1.1.1", "elapsed_ms": 12.0}]}]
        with patch.object(benchmark, "resolve_ipv4_observations", return_value={"common_ipv4": ["1.1.1.1"], "union_ipv4": ["1.1.1.1"]}), patch.object(benchmark, "tls_probe_ip", return_value={"success": True, "ip": "1.1.1.1", "elapsed_ms": 13.0}):
            out = benchmark.benchmark_candidates([candidate], samples=5, deep=True, prior_results=prior)[0]
        self.assertEqual((out["sample_count"], out["reused_samples"], out["new_samples"]), (5, 3, 2))

    def test_reality_fail_fast(self):
        failure = {"transport_success": False, "cleanup_success": True, "failure_stage": "PROXY_HEAD", "code": "ERROR:REALITY_PROXY_HEAD_TRANSPORT"}
        with patch.object(reality_selftest, "run_attempt", return_value=failure) as mocked:
            out = reality_selftest.run_candidate("a.example", ["1.1.1.1"], attempts=5, env={"ready": True}, fail_fast=True)
        self.assertEqual((mocked.call_count, out["attempt_count"], out["early_stopped"]), (1, 1, True))

    def test_worker_mismatch_detection(self):
        class P:
            returncode = 1
            def __init__(self, payload): self.payload = payload
            def communicate(self, payload, timeout): return self.payload, b""
            def kill(self): pass
        job = {"expected_worker_manifest": "a" * 64}
        old = json.dumps({"schema_version": 3}).encode()
        with patch.object(controller_run.subprocess, "Popen", return_value=P(old)):
            self.assertEqual(controller_run.run_remote("best-vm-us", job, 60)[1], "TARGET_WORKER_VERSION_MISMATCH")
        wrong = json.dumps({"schema_version": 4, "worker": {"protocol": 4, "implementation_version": "4.1", "manifest": "b" * 64}}).encode()
        with patch.object(controller_run.subprocess, "Popen", return_value=P(wrong)):
            self.assertEqual(controller_run.run_remote("best-vm-us", job, 60)[1], "TARGET_WORKER_BUILD_MISMATCH")

    def test_probe_pool_diversity(self):
        rows = [
            {"hostname": "old.example", "sources": ["incumbent"], "organizations": ["Old"], "initial_ipv4": ["1.1.1.1"]},
            {"hostname": "a.one.edu", "sources": ["seed"], "organizations": ["A"], "initial_ipv4": ["2.2.2.2"]},
            {"hostname": "b.one.edu", "sources": ["seed"], "organizations": ["A"], "initial_ipv4": ["2.2.2.2"]},
            {"hostname": "a.two.edu", "sources": ["osm"], "organizations": ["B"], "initial_ipv4": ["3.3.3.3"]},
        ]
        selected, _ = select_probe_pool(rows, "old.example", 3)
        self.assertEqual(len({registrable_domain(r["hostname"]) for r in selected}), 3)


if __name__ == "__main__":
    unittest.main()
