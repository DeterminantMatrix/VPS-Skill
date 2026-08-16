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
from controller_run import build_job, inventory_guard, load_seeds  # noqa: E402
import reality_selftest  # noqa: E402
from reality_selftest import _configs  # noqa: E402
from target_probe import classify_front_door  # noqa: E402
from target_worker import validate_job  # noqa: E402


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

    def test_vercel_cname_is_hard_evidence(self):
        row = classify_front_door("www.example.org", ["foo.vercel-dns-016.com"], "dig", {"headers": {}})
        self.assertEqual(row["class"], "PUBLIC_CDN")
        self.assertEqual(row["provider"], "Vercel")

    def test_unknown_edge_is_not_public_cdn(self):
        row = classify_front_door("www.example.org", ["edge.unknown-host.net"], "dig", {"headers": {}})
        self.assertEqual(row["class"], "UNKNOWN_EDGE_EVIDENCE")

    def test_missing_dig_is_review_not_direct(self):
        row = classify_front_door("www.example.org", [], "missing", {"headers": {}})
        self.assertEqual(row["class"], "UNKNOWN_TOOLING")

    def test_deep_policy_reliability(self):
        row = {
            "hostname": "a.example.org", "success_rate": 0.9, "per_ip": {"1.1.1.1": {"samples": 10, "success_rate": 0.9}},
            "hard_rejections": [], "eligibility": "ELIGIBLE",
        }
        out = apply_deep_policy(row)
        self.assertIn("HARD:TLS_SUCCESS_LT_95", out["hard_rejections"])

    def test_reality_fixture_keeps_hostname_sni_and_ipv4_handshake(self):
        server, client = _configs("www.example.org", "1.1.1.1", 30001, 30002, "priv", "pub", "00000000-0000-4000-8000-000000000000", "0123456789abcdef")
        tls = server["inbounds"][0]["tls"]
        self.assertEqual(tls["server_name"], "www.example.org")
        self.assertEqual(tls["reality"]["handshake"]["server"], "1.1.1.1")
        self.assertEqual(client["outbounds"][0]["tls"]["server_name"], "www.example.org")

    def test_sing_box_wrapper_falls_back_to_fixed_elf(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wrapper = root / "sing-box-wrapper"
            wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            os.chmod(wrapper, 0o755)
            binary = root / "sing-box"
            binary.write_bytes(b"\x7fELF" + b"fixture")
            os.chmod(binary, 0o755)
            with patch.object(reality_selftest.shutil, "which", return_value=str(wrapper)), \
                 patch.object(reality_selftest, "SING_BOX_FALLBACKS", (str(binary),)):
                self.assertEqual(reality_selftest.find_sing_box(), str(binary))

    def test_inventory_guard_and_job(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inventory = root / "hosts.yaml"
            inventory.write_text("""
hosts:
  best-vm-us:
    ipv4: 155.254.127.55
    active: true
    access:
      method: ssh
      alias: best-vm-us
    capabilities:
      ssh: true
""", encoding="utf-8")
            guard = inventory_guard(inventory, "155.254.127.55")
            self.assertEqual(guard["alias"], "best-vm-us")
            seeds = root / "seeds.txt"
            seeds.write_text("example.edu\n# comment\nwww.example.org\n", encoding="utf-8")
            values = load_seeds(seeds)
            job = build_job(guard, values, "incumbent.example", "explicit")
            validate_job(json.loads(json.dumps(job)))

    def test_local_vps_control_inventory_schema(self):
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
            self.assertEqual(guard["alias"], "best-vm-us")
            self.assertEqual(guard["region"], "US")

    def test_job_rejects_port_change(self):
        guard = {"alias": "best-vm-us", "target_ip": "155.254.127.55", "region": "US"}
        job = build_job(guard, ["example.edu", "incumbent.example"], "incumbent.example", "explicit")
        job["port"] = 8443
        with self.assertRaises(ValueError):
            validate_job(job)


if __name__ == "__main__":
    unittest.main()
