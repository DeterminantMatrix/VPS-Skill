#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import decision_grades
import target_discovery
import target_worker
from controller_run import build_job


class V45RegressionTests(unittest.TestCase):
    def test_regional_profile_platform_filter_does_not_define_protocol_policy(self):
        self.assertTrue(target_discovery._is_third_party_profile_host("m.facebook.com"))
        self.assertTrue(target_discovery._is_third_party_profile_host("www.instagram.com"))
        self.assertFalse(target_discovery._is_third_party_profile_host("akstudio.cc"))

    def test_lane_balancing_preserves_small_affinity_and_institutional_lanes(self):
        rows = []
        rows += [{"hostname": f"g{i}.example", "sources": ["osm_general"], "lanes": ["general_regional"]} for i in range(20)]
        rows += [{"hostname": f"i{i}.org", "sources": ["wikidata_institutional"], "lanes": ["institutional"]} for i in range(3)]
        rows += [{"hostname": f"a{i}.net", "sources": ["shodan_affinity"], "lanes": ["network_affinity"]} for i in range(2)]
        selected, meta = target_discovery._balanced_records(rows, 10, "none.invalid", {"network_affinity": 2, "institutional": 3, "general_regional": 3})
        self.assertEqual(sum("network_affinity" in r["lanes"] for r in selected), 2)
        self.assertEqual(sum("institutional" in r["lanes"] for r in selected), 3)
        self.assertTrue(meta["cap_hit"])

    def test_source_error_value_error_has_safe_subtype(self):
        self.assertEqual(target_discovery._source_error("openalex", ValueError("response too large")), "openalex:ValueError:RESPONSE_TOO_LARGE")

    def test_unique_family_rows_deduplicates_apex_and_www(self):
        rows = [{"hostname": "akstudio.cc"}, {"hostname": "www.akstudio.cc"}, {"hostname": "other.hk"}]
        out = target_worker.unique_family_rows(rows, 5)
        self.assertEqual([r["hostname"] for r in out], ["akstudio.cc", "other.hk"])
        self.assertEqual(out[0]["candidate_family"], "akstudio.cc")

    def test_latency_consistency_does_not_raise_durability_risk(self):
        row = {
            "success_rate": 1.0, "p50_ms": 100, "p95_ms": 145, "mad_ms": 5.0,
            "front_door": {"class": "DIRECT_LIKELY"}, "dns": {"volatile": False},
            "review": [], "organizations": ["Example Org"], "sources": ["osm_general"], "lanes": ["general_regional"],
        }
        consistency, _ = decision_grades._latency_consistency_grade(row)
        risk, _ = decision_grades._durability_risk(row)
        self.assertEqual(consistency, "C")
        self.assertEqual(risk, "LOW")

    def test_global_optimality_is_downgraded_when_search_caps_hit(self):
        coverage = {
            "status": "GOOD", "validated": 240, "goal": 200, "effective_eligible": 16, "eligible_goal": 15,
            "active_discovery_lanes": ["general_regional", "institutional", "network_affinity"],
            "source_errors": [], "saturation": {"any_cap_hit": True},
        }
        confidence, reasons = decision_grades._global_optimality_confidence(coverage, 5, 5, quality_target_met=True)
        self.assertEqual(confidence, "MEDIUM")
        self.assertIn("SEARCH_CAP_SATURATED", reasons)

    def test_duplicate_family_does_not_fill_five_choice_portfolio(self):
        rows = [
            {"hostname": "akstudio.cc", "p50_ms": 30},
            {"hostname": "www.akstudio.cc", "p50_ms": 31},
            {"hostname": "one.hk", "p50_ms": 32},
            {"hostname": "two.hk", "p50_ms": 33},
            {"hostname": "three.hk", "p50_ms": 34},
            {"hostname": "four.hk", "p50_ms": 35},
        ]
        unique = target_worker.unique_family_rows(rows, 5)
        self.assertEqual(len(unique), 5)
        self.assertEqual([r["candidate_family"] for r in unique].count("akstudio.cc"), 1)
        self.assertNotIn("www.akstudio.cc", [r["hostname"] for r in unique])

    def test_quality_below_target_is_success_with_explicit_quality_status(self):
        guard = {"inventory_id": "test-vps", "alias": "test-vps", "target_ip": "2.27.212.12", "region": "US"}
        job = build_job(guard, [], "old.example", "explicit", worker_manifest="a" * 64)
        job["limits"].update({"eligibility_pool": 6, "fast_pool": 6, "deep_pool": 6, "deep_pool_cap": 6, "deep_refill_batch": 2, "reality_candidate_cap": 6, "quality_extension_probe_cap": 2})
        job["profile"]["eligible_survivor_goal"] = 5
        candidates = [{"hostname": "old.example", "sources": ["incumbent"], "organizations": ["Old"], "initial_ipv4": ["1.1.1.1"]}]
        candidates += [{"hostname": f"slow{i}.example", "sources": ["seed"], "organizations": [f"Org{i}"], "initial_ipv4": [f"1.1.2.{i}"]} for i in range(1, 6)]
        discovery = {"validated": candidates, "coverage": "LIMITED", "errors": [], "counts": {"validated_ipv4": len(candidates)}, "source_records": candidates, "lane_counts": {"general_regional": 5}, "active_discovery_lanes": ["general_regional"], "affinity_search": {}}

        def gate(candidate, **kwargs):
            return {**candidate, "current_ipv4": candidate["initial_ipv4"], "dns": {"volatile": False}, "tls": [{"success": True, "ip": candidate["initial_ipv4"][0], "elapsed_ms": 10.0, "tls_version": "TLSv1.3", "alpn": "h2"}], "http": [], "front_door": {"class": "DIRECT_LIKELY", "network_metadata": {}}, "protocol_compliance": {"state": "PASS", "tls13": True, "h2": True, "certificate": "PASS", "redirect_policy": "PASS", "per_ip": {}}, "hard_rejections": [], "review": [], "warnings": [], "eligibility": "ELIGIBLE"}

        def bench(rows, *, samples, timeout=5.0, deep=False, prior_results=None):
            out=[]
            for row in rows:
                p50 = 120.0 if row["hostname"] == "old.example" else 100.0 + len(row["hostname"])
                ip = (row.get("current_ipv4") or row.get("initial_ipv4"))[0]
                out.append({**row, "current_ipv4": row.get("current_ipv4") or row.get("initial_ipv4"), "samples": [{"success": True, "ip": ip, "elapsed_ms": p50, "tls_version": "TLSv1.3", "alpn": "h2"}] * samples, "sample_count": samples, "reused_samples": 3 if deep else 0, "new_samples": samples-(3 if deep else 0), "success_rate": 1.0, "per_ip": {ip: {"samples": samples, "success_rate": 1.0}}, "p50_ms": p50, "p90_ms": p50+20, "p95_ms": p50+35, "mad_ms": 5.0, "tls_versions": ["TLSv1.3"], "alpn_protocols": ["h2"]})
            return out

        def reality(host, ips, attempts, env, fail_fast=True):
            return {"hostname": host, "attempts": [{}]*5, "attempt_count": 5, "transport_successes": 5, "cleanup_successes": 5, "passed": True, "dirty": False, "code": "OK"}

        with patch.object(target_worker, "preflight", return_value={"observed_egress_ip": "2.27.212.12", "location": {"asn": 4837, "organization": "Target", "country_code": "US"}, "warnings": []}), \
             patch.object(target_worker, "discover", return_value=discovery), \
             patch.object(target_worker, "discover_extension", return_value={"validated": [], "errors": [], "lane_counts": {}, "counts": {"validated_ipv4": 0}}), \
             patch.object(target_worker, "gate_candidate", side_effect=gate), \
             patch.object(target_worker, "benchmark_candidates", side_effect=bench), \
             patch.object(target_worker, "enrich_deep_asn", return_value=None), \
             patch.object(target_worker, "reality_environment", return_value={"ready": True}), \
             patch.object(target_worker, "_run_reality_control", return_value={"passed": True, "dirty": False, "retried": False}), \
             patch.object(target_worker, "run_candidate", side_effect=reality):
            out = target_worker.run(job, {"protocol": 4, "implementation_version": "4.5", "manifest": "a" * 64})

        self.assertEqual(out["status"], "SUCCESS_QUALITY_BELOW_TARGET")
        self.assertEqual(out["counts"]["selectable_families"], 5)
        self.assertFalse(out["counts"]["quality_target_met"])
        self.assertIn(out["counts"]["adaptive_refill_stop_reason"], {"QUALITY_SEARCH_EXHAUSTED", "REALITY_CANDIDATE_CAP_REACHED"})


if __name__ == "__main__":
    unittest.main()
