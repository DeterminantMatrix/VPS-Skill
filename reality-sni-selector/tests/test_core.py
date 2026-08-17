#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import benchmark
import controller_run
import reality_selftest
import target_probe
import target_discovery
import decision_view
from benchmark import apply_deep_policy, deep_rank_key
from common import mad, percentile, registrable_domain, validate_hostname
from controller_run import build_job, inventory_guard
from target_probe import classify_front_door, classify_network_organization
from target_worker import classify_network_affinity, select_deep_refill_batch, select_probe_pool, validate_job


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

    def test_near_tie_p50_uses_tail_latency(self):
        wmala = {"hostname": "www.wmala.com", "eligibility": "ELIGIBLE", "success_rate": 1.0, "p50_ms": 55.335, "p95_ms": 66.989, "mad_ms": 3.0, "front_door": {"class": "DIRECT_LIKELY"}, "per_ip": {}, "sources": []}
        lacada = {"hostname": "lacada.com", "eligibility": "ELIGIBLE", "success_rate": 1.0, "p50_ms": 55.340, "p95_ms": 63.968, "mad_ms": 3.0, "front_door": {"class": "DIRECT_LIKELY"}, "per_ip": {}, "sources": []}
        self.assertLess(deep_rank_key(lacada), deep_rank_key(wmala))

    def test_network_affinity_breaks_otherwise_equal_deep_tie(self):
        base = {"eligibility": "ELIGIBLE", "success_rate": 1.0, "p50_ms": 40.0, "p95_ms": 45.0, "mad_ms": 1.0, "front_door": {"class": "DIRECT_LIKELY"}, "per_ip": {}, "sources": []}
        same = {**base, "hostname": "same.example", "network_affinity": {"rank": 0, "grade": "A+", "code": "SAME_ASN"}}
        other = {**base, "hostname": "other.example", "network_affinity": {"rank": 3, "grade": "C", "code": "DIFFERENT_OR_REMOTE_NETWORK"}}
        self.assertLess(deep_rank_key(same), deep_rank_key(other))


    def test_same_asn_does_not_override_bad_tail(self):
        base = {"eligibility": "ELIGIBLE", "success_rate": 1.0, "p50_ms": 40.0, "mad_ms": 1.0, "front_door": {"class": "DIRECT_LIKELY"}, "per_ip": {}, "sources": []}
        same_bad_tail = {**base, "hostname": "same.example", "p95_ms": 90.0, "network_affinity": {"rank": 0, "grade": "A+", "code": "SAME_ASN"}}
        other_good_tail = {**base, "hostname": "other.example", "p95_ms": 45.0, "network_affinity": {"rank": 3, "grade": "C", "code": "DIFFERENT_OR_REMOTE_NETWORK"}}
        self.assertLess(deep_rank_key(other_good_tail), deep_rank_key(same_bad_tail))

    def test_deep_protocol_downgrade_updates_protocol_state(self):
        row = {
            "hostname": "a.example", "eligibility": "ELIGIBLE", "hard_rejections": [],
            "success_rate": 1.0, "per_ip": {"1.1.1.1": {"samples": 3, "success_rate": 1.0}},
            "samples": [
                {"success": True, "tls_version": "TLSv1.3", "alpn": "h2"},
                {"success": True, "tls_version": "TLSv1.2", "alpn": "h2"},
            ],
            "protocol_compliance": {"state": "PASS", "tls13": True, "h2": True, "hard_failures": []},
        }
        out = apply_deep_policy(row)
        self.assertIn("HARD:REALITY_MIN_TLS13", out["hard_rejections"])
        self.assertEqual(out["protocol_compliance"]["state"], "FAIL")
        self.assertFalse(out["protocol_compliance"]["tls13"])

    def test_protocol_failure_is_separate_from_safety_policy_grade(self):
        row = {
            "hostname": "legacy.example", "final_state": "PROTOCOL_REJECTED",
            "hard_rejections": ["HARD:REALITY_MIN_TLS13"], "review": [],
            "protocol_compliance": {"state": "FAIL", "tls13": False, "h2": True, "hard_failures": ["HARD:REALITY_MIN_TLS13"]},
            "success_rate": 1.0, "sample_count": 20, "per_ip": {},
        }
        out = decision_view._enrich_candidate(row, search_confidence="HIGH", search_reasons=[], latency_target_ms=60.0, selectable=False)
        self.assertEqual(out["protocol_compliance_grade"], "FAIL")
        self.assertEqual(out["policy_grade"], "PASS")
        self.assertEqual(out["protocol_hard_rejections"], ["HARD:REALITY_MIN_TLS13"])
        self.assertEqual(out["safety_hard_rejections"], [])

    def test_transient_source_fetch_retries_once(self):
        with patch.object(target_discovery, "fetch_json", side_effect=[urllib.error.URLError("timeout"), {"ok": True}]) as mocked, patch.object(target_discovery.time, "sleep"):
            out = target_discovery._fetch_json_one_retry("https://example.invalid")
        self.assertEqual(out, {"ok": True})
        self.assertEqual(mocked.call_count, 2)

    def test_nontransient_source_http_error_does_not_retry(self):
        err = urllib.error.HTTPError("https://example.invalid", 404, "not found", {}, None)
        with patch.object(target_discovery, "fetch_json", side_effect=err) as mocked, patch.object(target_discovery.time, "sleep"):
            with self.assertRaises(urllib.error.HTTPError):
                target_discovery._fetch_json_one_retry("https://example.invalid")
        self.assertEqual(mocked.call_count, 1)


    def test_general_osm_lane_is_not_forced_institutional(self):
        self.assertEqual(target_discovery._osm_lane({"shop": "books"}), "general_regional")
        self.assertEqual(target_discovery._osm_lane({"amenity": "university"}), "institutional")

    def test_affinity_passive_sampling_is_bounded(self):
        sampled = target_discovery.sample_affinity_ips("23.19.228.207", "23.19.228.0/24", ["23.19.228.0/24", "23.19.229.0/24"], 12)
        self.assertLessEqual(len(sampled), 12)
        self.assertNotIn("23.19.228.207", sampled)
        self.assertTrue(all(target_discovery.is_public_ipv4(ip) for ip in sampled))

    def test_probe_pool_reserves_affinity_lane(self):
        candidates = [
            {"hostname": "old.example", "sources": ["incumbent"], "lanes": ["incumbent"], "organizations": [], "initial_ipv4": ["8.8.8.8"]},
            {"hostname": "aff.example", "sources": ["shodan_affinity"], "lanes": ["network_affinity"], "organizations": [], "initial_ipv4": ["1.1.1.1"]},
            {"hostname": "gen.example", "sources": ["osm_general"], "lanes": ["general_regional"], "organizations": [], "initial_ipv4": ["9.9.9.9"]},
        ]
        selected, _ = select_probe_pool(candidates, "old.example", 2, {"network_affinity": 1})
        self.assertEqual({row["hostname"] for row in selected}, {"old.example", "aff.example"})

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
        self.assertEqual((job["implementation_version"], job["profile"]["coverage_goal"], job["limits"]["eligibility_pool"], job["limits"]["fast_pool"], job["limits"]["deep_pool"], job["limits"]["deep_pool_cap"], job["limits"]["deep_refill_batch"], job["limits"]["reality_candidate_cap"]), ("4.4", 200, 80, 36, 10, 18, 4, 16))

    def test_quick_profile_freezes_near_tie_window(self):
        job = build_job(self._guard(), [], "old.example", "explicit", worker_manifest="a" * 64)
        self.assertEqual(job["profile"]["p50_equivalence_ms"], 2.0)
        validate_job(json.loads(json.dumps(job)))

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
        stale = json.dumps({"schema_version": 4, "worker": {"protocol": 4, "implementation_version": "4.2", "manifest": "b" * 64}}).encode()
        with patch.object(controller_run.subprocess, "Popen", return_value=P(stale)):
            self.assertEqual(controller_run.run_remote("best-vm-us", job, 60)[1], "TARGET_WORKER_VERSION_MISMATCH")
        wrong = json.dumps({"schema_version": 4, "worker": {"protocol": 4, "implementation_version": "4.4", "manifest": "b" * 64}}).encode()
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

    def test_tls13_and_h2_are_reality_protocol_hard_gates(self):
        candidate = {"hostname": "legacy.example", "sources": ["seed"], "organizations": []}
        with patch.object(target_probe, "resolve_ipv4_observations", return_value={"common_ipv4": ["1.1.1.1"], "union_ipv4": ["1.1.1.1"], "volatile": False, "errors": []}), \
             patch.object(target_probe, "tls_probe_ip", return_value={"success": True, "ip": "1.1.1.1", "elapsed_ms": 20.0, "tls_version": "TLSv1.2", "alpn": "http/1.1"}), \
             patch.object(target_probe, "dig_cname", return_value=([], "dig")), \
             patch.object(target_probe, "http_head_ip", return_value={"success": True, "status": 200, "headers": {}}):
            row = target_probe.gate_candidate(candidate, tls_samples_per_ip=1)
        self.assertIn("HARD:REALITY_MIN_TLS13", row["hard_rejections"])
        self.assertIn("HARD:REALITY_MIN_H2", row["hard_rejections"])
        self.assertEqual(row["protocol_compliance"]["state"], "FAIL")

    def test_cross_site_redirect_is_reality_protocol_hard_gate(self):
        candidate = {"hostname": "www.example.org", "sources": ["seed"], "organizations": []}
        with patch.object(target_probe, "resolve_ipv4_observations", return_value={"common_ipv4": ["1.1.1.1"], "union_ipv4": ["1.1.1.1"], "volatile": False, "errors": []}), \
             patch.object(target_probe, "tls_probe_ip", return_value={"success": True, "ip": "1.1.1.1", "elapsed_ms": 20.0, "tls_version": "TLSv1.3", "alpn": "h2"}), \
             patch.object(target_probe, "dig_cname", return_value=([], "dig")), \
             patch.object(target_probe, "http_head_ip", return_value={"success": True, "status": 302, "headers": {"location": "https://other.example.net/"}}):
            row = target_probe.gate_candidate(candidate, tls_samples_per_ip=1)
        self.assertIn("HARD:REALITY_CROSS_SITE_REDIRECT", row["hard_rejections"])
        self.assertEqual(row["protocol_compliance"]["redirect_policy"], "FAIL")

    def test_same_asn_is_network_affinity_bonus(self):
        same = classify_network_affinity("2.27.212.12", {"asn": 4837, "organization": "Target", "country_code": "US"}, {"asn": 4837, "organization": "Other", "country_code": "US"}, ["23.1.2.3"])
        other = classify_network_affinity("2.27.212.12", {"asn": 4837, "organization": "Target", "country_code": "US"}, {"asn": 9999, "organization": "Other", "country_code": "US"}, ["23.1.2.3"])
        self.assertEqual((same["grade"], same["code"], same["rank"]), ("A+", "SAME_ASN", 0))
        self.assertLess(same["rank"], other["rank"])

    def test_deep_refill_takes_next_fast_survivors_without_duplicates(self):
        fast = [{"hostname": f"d{i}.example", "eligibility": "ELIGIBLE", "hard_rejections": [], "incumbent": False} for i in range(1, 8)]
        deep = fast[:2]
        refill = select_deep_refill_batch(fast, deep, batch_size=4, deep_cap=5)
        self.assertEqual([row["hostname"] for row in refill], ["d3.example", "d4.example", "d5.example"])


if __name__ == "__main__":
    unittest.main()
