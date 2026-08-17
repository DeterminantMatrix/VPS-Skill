#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import target_worker
import report
from controller_core import build_job


class WorkerFlowTests(unittest.TestCase):
    def _deep(self, host="old.example", p50=60.0, p95=70.0):
        return {"hostname": host, "incumbent": host == "old.example", "eligibility": "ELIGIBLE", "hard_rejections": [], "review": [], "warnings": [], "success_rate": 1.0, "sample_count": 20, "per_ip": {"1.1.1.1": {"samples": 20, "success_rate": 1.0}}, "p50_ms": p50, "p90_ms": p95 - 2, "p95_ms": p95, "mad_ms": 2.0, "dns": {"volatile": False}, "front_door": {"class": "DIRECT_LIKELY"}, "sources": ["wikidata"], "organizations": ["Example Org"]}

    def _control(self, passed=True, retried=False):
        return {"passed": passed, "dirty": False, "retried": retried, "attempts": [], "transport_successes": 1 if passed else 0, "cleanup_successes": 1}

    def test_incumbent_keep(self):
        out = target_worker.assess_incumbent("old.example", {"eligibility": "ELIGIBLE", "hard_rejections": [], "review": []}, self._deep(), self._control(), [], latency_target_ms=60, coverage_status="GOOD")
        self.assertEqual(out["code"], "KEEP")

    def test_incumbent_required_replace(self):
        gate = {"eligibility": "HARD_REJECTED", "hard_rejections": ["HARD:KNOWN_SHARED_PLATFORM"], "review": []}
        out = target_worker.assess_incumbent("old.example", gate, self._deep(), self._control(), [], latency_target_ms=60, coverage_status="GOOD")
        self.assertEqual((out["code"], out["verdict"]), ("REPLACE_REQUIRED", "需要更换"))

    def test_incumbent_recommended_replace(self):
        alternative = {"hostname": "new.example", "p50_ms": 35.0, "p95_ms": 50.0}
        out = target_worker.assess_incumbent("old.example", {"eligibility": "ELIGIBLE", "hard_rejections": [], "review": []}, self._deep(p50=70, p95=80), self._control(), [alternative], latency_target_ms=60, coverage_status="GOOD")
        self.assertEqual(out["code"], "REPLACE_RECOMMENDED")

    def test_incumbent_keep_with_review_after_control_retry(self):
        out = target_worker.assess_incumbent("old.example", {"eligibility": "ELIGIBLE", "hard_rejections": [], "review": []}, self._deep(), self._control(True, True), [], latency_target_ms=60, coverage_status="GOOD")
        self.assertEqual(out["code"], "KEEP_WITH_REVIEW")

    def test_policy_reject_not_promoted_by_reality(self):
        deep = [
            {**self._deep("good.example", 40, 50), "incumbent": False},
            {**self._deep("bad.example", 20, 25), "incumbent": False, "eligibility": "HARD_REJECTED", "hard_rejections": ["HARD:KNOWN_SHARED_PLATFORM"]},
        ]
        reality = {"candidates": [{"hostname": "good.example", "passed": True}, {"hostname": "bad.example", "passed": True}]}
        rows = target_worker.build_comparison(deep, [], reality, "old.example", 5, None)
        states = {r["hostname"]: r["final_state"] for r in rows}
        self.assertEqual((states["good.example"], states["bad.example"]), ("SELECTABLE", "POLICY_REJECTED"))

    def _result_for_decision(self, top, *, coverage_status="GOOD", validated=200, goal=200, incumbent_gate=None):
        incumbent = self._deep(p50=35.0, p95=42.0)
        metrics = {
            "eligibility": (incumbent_gate or {}).get("eligibility", "ELIGIBLE"),
            "hard_rejections": (incumbent_gate or {}).get("hard_rejections", []),
            "review": (incumbent_gate or {}).get("review", []),
            "success_rate": 1.0,
            "p50_ms": incumbent["p50_ms"],
            "p95_ms": incumbent["p95_ms"],
            "mad_ms": incumbent["mad_ms"],
            "reality_control": "PASS",
        }
        return {
            "status": "SUCCESS",
            "coverage": {"status": coverage_status, "validated": validated, "goal": goal, "profile": "quick"},
            "frozen_run": {"incumbent": "old.example", "profile": {"latency_target_ms": 60.0, "p50_equivalence_ms": 2.0}},
            "counts": {"selectable_target": 5},
            "top5": top,
            "comparison": top,
            "incumbent_assessment": {"hostname": "old.example", "verdict": "需要更换" if metrics["hard_rejections"] else "继续使用", "code": "REPLACE_REQUIRED" if metrics["hard_rejections"] else "KEEP", "confidence": "HIGH", "metrics": metrics, "reasons": metrics["hard_rejections"]},
        }

    def test_sparse_coverage_with_five_selectable_has_medium_search_confidence(self):
        top = []
        for i in range(1, 6):
            row = self._deep(f"d{i}.example", 50 + i, 60 + i) | {"incumbent": False, "final": "SELECTABLE", "policy_eligibility": "ELIGIBLE"}
            row["reality"] = {"passed": True, "attempt_count": 5, "transport_successes": 5, "attempts": []}
            top.append(row)
        view = report.build_decision_view(self._result_for_decision(top, coverage_status="SPARSE", validated=57, goal=200))
        self.assertEqual(view["top5"][0]["search_confidence"], "MEDIUM")
        self.assertEqual(view["top5"][0]["candidate_confidence"], "HIGH")
        self.assertEqual(view["top5"][0]["overall_recommendation_confidence"], "MEDIUM_HIGH")

    def test_near_tie_report_explains_tail_latency_tiebreak(self):
        a = self._deep("lacada.com", 55.340, 63.968) | {"incumbent": False, "final": "SELECTABLE", "policy_eligibility": "ELIGIBLE"}
        b = self._deep("www.wmala.com", 55.335, 66.989) | {"incumbent": False, "final": "SELECTABLE", "policy_eligibility": "ELIGIBLE"}
        for row in (a, b):
            row["reality"] = {"passed": True, "attempt_count": 5, "transport_successes": 5, "attempts": []}
        view = report.build_decision_view(self._result_for_decision([a, b]))
        self.assertEqual(view["top5"][0]["hostname"], "lacada.com")
        self.assertEqual(view["top5"][0]["ranking_rationale_code"], "NEAR_TIE_LEADER")
        self.assertIn("P95", view["top5"][0]["ranking_rationale"])

    def test_incumbent_faster_but_policy_rejected_tradeoff_is_explicit(self):
        alt = self._deep("new.example", 55.0, 65.0) | {"incumbent": False, "final": "SELECTABLE", "policy_eligibility": "ELIGIBLE"}
        alt["reality"] = {"passed": True, "attempt_count": 5, "transport_successes": 5, "attempts": []}
        gate = {"eligibility": "HARD_REJECTED", "hard_rejections": ["HARD:KNOWN_PUBLIC_CDN"], "review": []}
        view = report.build_decision_view(self._result_for_decision([alt], coverage_status="SPARSE", validated=57, goal=200, incumbent_gate=gate))
        assessment = view["incumbent_assessment"]
        self.assertEqual(assessment["verdict"], "需要更换")
        self.assertEqual(assessment["tradeoff_code"], "CURRENT_FASTER_BUT_POLICY_REJECTED")
        self.assertIn("性能更快", assessment["tradeoff_text"])

    def test_reality_control_retries_only_after_failure(self):
        first = {"attempts": [{"transport_success": False, "cleanup_success": True, "failure_stage": "PROXY_HEAD"}], "passed": False, "dirty": False}
        retry = {"attempts": [{"transport_success": True, "cleanup_success": True}, {"transport_success": True, "cleanup_success": True}], "passed": True, "dirty": False}
        with patch.object(target_worker, "run_candidate", side_effect=[first, retry]) as mocked:
            out = target_worker._run_reality_control("old.example", ["1.1.1.1"], {"ready": True})
        self.assertEqual((mocked.call_count, out["attempt_count"], out["passed"], out["retried"]), (2, 3, True, True))

    def test_adaptive_refill_continues_until_five_selectable(self):
        guard = {"inventory_id": "test-vps", "alias": "test-vps", "target_ip": "2.27.212.12", "region": "US"}
        job = build_job(guard, [], "old.example", "explicit", worker_manifest="a" * 64)
        job["limits"].update({"eligibility_pool": 10, "fast_pool": 10, "deep_pool": 4, "deep_pool_cap": 10, "deep_refill_batch": 2, "reality_candidate_cap": 9})
        job["profile"]["eligible_survivor_goal"] = 8
        candidates = [{"hostname": "old.example", "sources": ["incumbent"], "organizations": ["Old"], "initial_ipv4": ["1.1.1.1"]}]
        candidates += [{"hostname": f"d{i}.example", "sources": ["seed"], "organizations": [f"Org{i}"], "initial_ipv4": [f"1.1.1.{i+1}"]} for i in range(1, 10)]

        discovery = {"validated": candidates, "coverage": "SPARSE", "errors": [], "ct_skipped_sufficient_sources": False, "counts": {"validated_ipv4": len(candidates)}, "source_records": candidates}

        def fake_gate(candidate, **kwargs):
            return {
                **candidate,
                "current_ipv4": candidate["initial_ipv4"],
                "dns": {"volatile": False},
                "tls": [{"success": True, "ip": candidate["initial_ipv4"][0], "elapsed_ms": 10.0, "tls_version": "TLSv1.3", "alpn": "h2"}],
                "http": [{"success": True, "status": 200, "headers": {}}],
                "front_door": {"class": "DIRECT_LIKELY"},
                "protocol_compliance": {"state": "PASS", "tls13": True, "h2": True, "certificate": "PASS", "redirect_policy": "PASS", "per_ip": {}},
                "hard_rejections": [],
                "review": [],
                "warnings": [],
                "eligibility": "ELIGIBLE",
            }

        def fake_benchmark(rows, *, samples, timeout=5.0, deep=False, prior_results=None):
            out = []
            for row in rows:
                host = row["hostname"]
                idx = 0 if host == "old.example" else int(host[1:].split(".", 1)[0])
                sample_rows = [{"success": True, "ip": row.get("current_ipv4", row.get("initial_ipv4"))[0], "elapsed_ms": 20.0 + idx, "tls_version": "TLSv1.3", "alpn": "h2"} for _ in range(samples)]
                out.append({
                    **row,
                    "current_ipv4": row.get("current_ipv4") or row.get("initial_ipv4"),
                    "samples": sample_rows,
                    "sample_count": samples,
                    "reused_samples": 3 if deep else 0,
                    "new_samples": samples - (3 if deep else 0),
                    "success_rate": 1.0,
                    "per_ip": {sample_rows[0]["ip"]: {"samples": samples, "success_rate": 1.0}},
                    "p50_ms": 20.0 + idx,
                    "p90_ms": 22.0 + idx,
                    "p95_ms": 23.0 + idx,
                    "mad_ms": 0.5,
                    "tls_versions": ["TLSv1.3"],
                    "alpn_protocols": ["h2"],
                })
            return out

        def fake_enrich(rows, target_location, target_ip, metadata):
            for row in rows:
                row["asn_evidence"] = {"asn": 4837, "organization": "Target", "country_code": "US"}
                row["exact_target_asn"] = True
                row["network_affinity"] = {"grade": "A+", "code": "SAME_ASN", "rank": 0, "evidence": ["asn:4837"]}

        def fake_reality(host, ips, attempts, env, fail_fast=True):
            idx = int(host[1:].split(".", 1)[0])
            passed = idx >= 4
            return {"hostname": host, "attempts": [{}] * (5 if passed else 1), "attempt_count": 5 if passed else 1, "transport_successes": 5 if passed else 0, "cleanup_successes": 5 if passed else 1, "passed": passed, "dirty": False, "code": "OK" if passed else "HARD:REALITY_FAILED"}

        with patch.object(target_worker, "preflight", return_value={"observed_egress_ip": "2.27.212.12", "location": {"asn": 4837, "organization": "Target", "country_code": "US"}, "warnings": []}), \
             patch.object(target_worker, "discover", return_value=discovery), \
             patch.object(target_worker, "gate_candidate", side_effect=fake_gate), \
             patch.object(target_worker, "benchmark_candidates", side_effect=fake_benchmark), \
             patch.object(target_worker, "enrich_deep_asn", side_effect=fake_enrich), \
             patch.object(target_worker, "reality_environment", return_value={"ready": True}), \
             patch.object(target_worker, "_run_reality_control", return_value={"passed": True, "dirty": False, "retried": False}), \
             patch.object(target_worker, "run_candidate", side_effect=fake_reality):
            out = target_worker.run(job, {"protocol": 4, "implementation_version": "4.4", "manifest": "a" * 64})

        self.assertEqual(out["status"], "SUCCESS")
        self.assertEqual(out["counts"]["selectable"], 5)
        self.assertEqual(out["counts"]["deep_refill_rounds"], 3)
        self.assertEqual(out["counts"]["deep_refill_benchmarked"], 6)
        self.assertEqual(out["counts"]["adaptive_refill_stop_reason"], "SELECTABLE_TARGET_MET")
        self.assertEqual(out["counts"]["reality_tested"], 8)

    def test_low_gate_yield_triggers_bounded_discovery_extension(self):
        guard = {"inventory_id": "test-vps", "alias": "test-vps", "target_ip": "2.27.212.12", "region": "US"}
        job = build_job(guard, [], "old.example", "explicit", worker_manifest="a" * 64)
        job["limits"].update({"eligibility_pool": 8, "fast_pool": 8, "deep_pool": 4, "deep_pool_cap": 8, "deep_refill_batch": 2, "reality_candidate_cap": 8})
        job["profile"]["eligible_survivor_goal"] = 5
        initial = [
            {"hostname": "old.example", "sources": ["incumbent"], "lanes": ["incumbent"], "organizations": ["Old"], "initial_ipv4": ["1.1.1.1"]},
            {"hostname": "bad.example", "sources": ["osm_general"], "lanes": ["general_regional"], "organizations": ["Bad"], "initial_ipv4": ["1.1.1.2"]},
        ]
        discovery = {
            "validated": initial, "coverage": "SPARSE", "errors": [], "ct_skipped_sufficient_sources": True,
            "counts": {"validated_ipv4": 2}, "source_records": initial, "lane_counts": {"general_regional": 1},
            "source_counts": {"osm_general": 1}, "active_discovery_lanes": ["general_regional"],
            "affinity_search": {"target_ip": "2.27.212.12", "target_asn": 4837, "target_prefix": "2.27.212.0/24", "method": "TEST", "active_scan": False},
        }
        extension_rows = [
            {"hostname": f"new{i}.example", "sources": ["ct"], "lanes": ["general_regional", "passive_expansion"], "organizations": [f"Org{i}"], "initial_ipv4": [f"1.1.2.{i}"]}
            for i in range(1, 6)
        ]
        extension = {"validated": extension_rows, "errors": [], "lane_counts": {"general_regional": 5}, "counts": {"validated_ipv4": 5}}

        def fake_gate(candidate, **kwargs):
            bad = candidate["hostname"] == "bad.example"
            return {
                **candidate, "current_ipv4": candidate["initial_ipv4"], "dns": {"volatile": False},
                "tls": [] if bad else [{"success": True, "ip": candidate["initial_ipv4"][0], "elapsed_ms": 10.0, "tls_version": "TLSv1.3", "alpn": "h2"}],
                "http": [], "front_door": {"class": "DIRECT_LIKELY", "network_metadata": {}},
                "protocol_compliance": {"state": "FAIL" if bad else "PASS", "tls13": not bad, "h2": not bad, "certificate": "PASS", "redirect_policy": "PASS", "per_ip": {}},
                "hard_rejections": ["HARD:TLS_UNREACHABLE"] if bad else [], "review": [], "warnings": [],
                "eligibility": "BASELINE_ONLY" if candidate["hostname"] == "old.example" else "HARD_REJECTED" if bad else "ELIGIBLE",
            }

        with patch.object(target_worker, "preflight", return_value={"observed_egress_ip": "2.27.212.12", "location": {"asn": 4837, "organization": "Target", "country_code": "US"}, "warnings": []}), \
             patch.object(target_worker, "discover", return_value=discovery), \
             patch.object(target_worker, "discover_extension", return_value=extension) as ext_mock, \
             patch.object(target_worker, "gate_candidate", side_effect=fake_gate), \
             patch.object(target_worker, "benchmark_candidates", return_value=[]), \
             patch.object(target_worker, "reality_environment", return_value={"ready": False, "reason": "fixture"}):
            out = target_worker.run(job, {"protocol": 4, "implementation_version": "4.4", "manifest": "a" * 64})

        self.assertEqual(ext_mock.call_count, 1)
        self.assertTrue(out["coverage"]["discovery_extension"]["triggered"])
        self.assertEqual(out["coverage"]["discovery_extension"]["new_validated"], 5)
        self.assertGreaterEqual(out["coverage"]["effective_eligible"], 5)


if __name__ == "__main__":
    unittest.main()
