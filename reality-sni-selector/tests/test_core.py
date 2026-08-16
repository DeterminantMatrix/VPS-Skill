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

from benchmark import apply_deep_policy, deep_rank_key  # noqa: E402
from common import mad, percentile, registrable_domain, validate_hostname  # noqa: E402
import controller_run  # noqa: E402
from controller_run import build_job, inventory_guard, load_seeds  # noqa: E402
import reality_selftest  # noqa: E402
from reality_selftest import _configs  # noqa: E402
from target_probe import classify_front_door, classify_network_organization  # noqa: E402
from target_worker import select_probe_pool, validate_job  # noqa: E402


class CoreTests(unittest.TestCase):
    def test_hostname_and_domain(self):
        self.assertEqual(validate_hostname("WWW.Example.COM."), "www.example.com")
        self.assertEqual(registrable_domain("a.b.example.co.uk"), "example.co.uk")
        with self.assertRaises(ValueError):
            validate_hostname("bad host")

    def test_stats_helpers(self):
        values = [10, 20, 30, 40, 50]
        self.assertEqual(percentile(values, 0.5), 30)
        self.assertEqual(mad(values), 10)

    def test_vercel_cname_is_public_cdn(self):
        row = classify_front_door("www.example.org", ["foo.vercel-dns-016.com"], "dig", {"success": True, "headers": {}})
        self.assertEqual(row["class"], "PUBLIC_CDN_CONFIRMED")
        self.assertEqual(row["provider"], "Vercel")

    def test_pantheon_header_is_shared_platform(self):
        row = classify_front_door(
            "lapl.org", [], "dig",
            {"success": True, "headers": {"x-pantheon-styx-hostname": "styx-us-a-123"}},
        )
        self.assertEqual(row["class"], "SHARED_PLATFORM_CONFIRMED")
        self.assertEqual(row["platform"], "Pantheon")

    def test_pantheon_network_org_is_shared_platform(self):
        cls, name, evidence = classify_network_organization({"organization": "Pantheon Systems, Inc."})
        self.assertEqual(cls, "SHARED_PLATFORM_CONFIRMED")
        self.assertEqual(name, "Pantheon")
        self.assertIn("network_org", evidence)

    def test_head_failure_is_not_direct(self):
        row = classify_front_door("www.example.org", [], "dig", {"success": False, "headers": {}})
        self.assertEqual(row["class"], "UNKNOWN_EDGE_EVIDENCE")

    def test_missing_dig_is_review_not_direct(self):
        row = classify_front_door("www.example.org", [], "missing", {"success": True, "headers": {}})
        self.assertEqual(row["class"], "UNKNOWN_TOOLING")

    def test_deep_policy_reliability(self):
        row = {
            "hostname": "a.example.org", "success_rate": 0.9,
            "per_ip": {"1.1.1.1": {"samples": 10, "success_rate": 0.9}},
            "hard_rejections": [], "eligibility": "ELIGIBLE",
        }
        out = apply_deep_policy(row)
        self.assertIn("HARD:TLS_SUCCESS_LT_95", out["hard_rejections"])

    def test_policy_state_precedes_latency(self):
        clean = {"hostname": "clean.example", "eligibility": "ELIGIBLE", "success_rate": 1.0, "p50_ms": 50, "p95_ms": 60,
                 "mad_ms": 2, "front_door": {"class": "DIRECT_LIKELY"}, "per_ip": {}, "sources": []}
        review = {"hostname": "review.example", "eligibility": "REVIEW_REQUIRED", "success_rate": 1.0, "p50_ms": 20, "p95_ms": 25,
                  "mad_ms": 1, "front_door": {"class": "UNKNOWN_EDGE_EVIDENCE"}, "per_ip": {}, "sources": []}
        self.assertLess(deep_rank_key(clean), deep_rank_key(review))

    def test_reality_fixture_keeps_hostname_sni_and_ipv4_handshake(self):
        server, client = _configs("www.example.org", "1.1.1.1", 30001, 30002, "priv", "pub", "00000000-0000-4000-8000-000000000000", "0123456789abcdef")
        tls = server["inbounds"][0]["tls"]
        self.assertEqual(tls["server_name"], "www.example.org")
        self.assertEqual(tls["reality"]["handshake"]["server"], "1.1.1.1")
        self.assertEqual(client["outbounds"][0]["tls"]["server_name"], "www.example.org")

    def test_fixed_elf_path_precedes_path_wrapper(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wrapper = root / "wrapper"
            wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            os.chmod(wrapper, 0o755)
            binary = root / "sing-box"
            binary.write_bytes(b"\x7fELF" + b"fixture")
            os.chmod(binary, 0o755)
            with patch.object(reality_selftest, "SING_BOX_FIXED_PATHS", (str(binary),)), \
                 patch.object(reality_selftest.shutil, "which", return_value=str(wrapper)):
                self.assertEqual(reality_selftest.find_sing_box(), str(binary))

    def test_local_inventory_contract_and_job(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inventory = root / "hosts.yaml"
            inventory.write_text("""
schema_version: 1
inventory_version: test-1
source_of_truth: inventory/hosts.yaml
hosts:
  best-vm-us:
    inventory_id: best-vm-us
    alias: best-vm-us
    region: US
    access:
      method: ssh
      hostname: 155.254.127.55
      address: 155.254.127.55
      port: 22
      user: root
      proxy_jump: null
      identity_ref: external:ssh-config
    capabilities:
      ssh: true
    state:
      retired: false
      forbidden: false
""", encoding="utf-8")
            guard = inventory_guard(inventory, "155.254.127.55")
            self.assertEqual(guard["inventory_id"], "best-vm-us")
            self.assertEqual(guard["alias"], "best-vm-us")
            self.assertEqual(guard["region"], "US")
            seeds = root / "seeds.txt"
            seeds.write_text("example.edu\n# comment\nwww.example.org\n", encoding="utf-8")
            values = load_seeds(seeds)
            job = build_job(guard, values, "incumbent.example", "explicit", worker_manifest="a" * 64)
            validate_job(json.loads(json.dumps(job)))

    def test_old_inventory_shape_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            inventory = Path(td) / "hosts.yaml"
            inventory.write_text("""
hosts:
  best-vm-us:
    ipv4: 155.254.127.55
    access: {method: ssh}
    capabilities: {ssh: true}
""", encoding="utf-8")
            with self.assertRaises(ValueError):
                inventory_guard(inventory, "155.254.127.55")

    def test_job_rejects_port_change(self):
        guard = {"inventory_id": "best-vm-us", "alias": "best-vm-us", "target_ip": "155.254.127.55", "region": "US"}
        job = build_job(guard, ["example.edu", "incumbent.example"], "incumbent.example", "explicit", worker_manifest="a" * 64)
        job["port"] = 8443
        with self.assertRaises(ValueError):
            validate_job(job)


    def test_controller_detects_worker_protocol_and_build_mismatch(self):
        class FakeProc:
            returncode = 1
            def __init__(self, payload):
                self.payload = payload
            def communicate(self, payload, timeout):
                return self.payload, b""
            def kill(self):
                pass

        job = {"expected_worker_manifest": "a" * 64}
        old = json.dumps({"schema_version": 3, "status": "WORKER_FAILED"}).encode()
        with patch.object(controller_run.subprocess, "Popen", return_value=FakeProc(old)):
            result, status = controller_run.run_remote("best-vm-us", job, 60)
            self.assertIsNone(result)
            self.assertEqual(status, "TARGET_WORKER_VERSION_MISMATCH")

        wrong_build = json.dumps({"schema_version": 4, "worker": {"protocol": 4, "manifest": "b" * 64}}).encode()
        with patch.object(controller_run.subprocess, "Popen", return_value=FakeProc(wrong_build)):
            result, status = controller_run.run_remote("best-vm-us", job, 60)
            self.assertIsNone(result)
            self.assertEqual(status, "TARGET_WORKER_BUILD_MISMATCH")

    def test_probe_pool_prefers_diversity(self):
        candidates = [
            {"hostname": "old.example.org", "sources": ["incumbent"], "organizations": ["Old"], "initial_ipv4": ["1.1.1.1"]},
            {"hostname": "a.one.edu", "sources": ["seed"], "organizations": ["Org1"], "initial_ipv4": ["2.2.2.2"]},
            {"hostname": "b.one.edu", "sources": ["seed"], "organizations": ["Org1"], "initial_ipv4": ["2.2.2.2"]},
            {"hostname": "a.two.edu", "sources": ["wikidata"], "organizations": ["Org2"], "initial_ipv4": ["3.3.3.3"]},
            {"hostname": "a.three.edu", "sources": ["osm"], "organizations": ["Org3"], "initial_ipv4": ["4.4.4.4"]},
        ]
        selected, deferred = select_probe_pool(candidates, "old.example.org", 3)
        hosts = {r["hostname"] for r in selected}
        self.assertIn("old.example.org", hosts)
        self.assertIn("a.one.edu", hosts)
        self.assertTrue("a.two.edu" in hosts or "a.three.edu" in hosts)
        self.assertTrue(any(r.get("status_code") == "DEFERRED:DIVERSITY_BUDGET" for r in deferred))


if __name__ == "__main__":
    unittest.main()
