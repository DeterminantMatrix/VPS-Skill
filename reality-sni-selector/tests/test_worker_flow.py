#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import target_worker  # noqa: E402


class WorkerFlowTests(unittest.TestCase):
    def test_target_measured_flow_produces_ranked_comparison(self):
        manifest = "a" * 64
        job = {
            "schema_version": 4,
            "worker_protocol": 4,
            "expected_worker_manifest": manifest,
            "profile_name": "target-measured-v4",
            "target": {"inventory_id": "best-vm-us", "alias": "best-vm-us", "inventory_ipv4": "155.254.127.55"},
            "region": "US",
            "incumbent_mode": "explicit",
            "incumbent": "old.example.org",
            "seed_domains": ["old.example.org", "a.example.org", "b.example.org", "c.example.org", "d.example.org", "e.example.org"],
            "port": 443,
            "limits": {"source_pool_cap": 1200, "discovered_cap": 600, "eligibility_pool": 120, "fast_pool": 50,
                       "deep_pool": 10, "top_n": 5, "comparison_min_domains": 5, "fast_samples": 5, "deep_samples": 20,
                       "reality_attempts": 5, "ct_base_cap": 40, "ct_max_per_domain": 20, "dns_workers": 12, "ip_metadata_budget": 128},
            "profile": {"coverage_goal": 400, "primary_radius_km": 75, "expanded_radius_km": 150,
                        "ct_failure_budget": 3, "latency_target_ms": 60.0, "strict_shared_edge": True},
        }
        pre = {"observed_egress_ip": "155.254.127.55", "location": {"country_code": "US", "asn": 64500},
               "region_mismatch": False, "tools": {}, "warnings": []}
        hosts = ["old.example.org", "a.example.org", "b.example.org", "c.example.org", "d.example.org", "e.example.org"]
        candidates = [
            {"hostname": h, "sources": ["incumbent" if h == "old.example.org" else "seed"], "organizations": [h],
             "initial_ipv4": [f"93.184.216.{30+i}"]}
            for i, h in enumerate(hosts)
        ]

        def fake_gate(candidate, **kwargs):
            return {**candidate, "current_ipv4": candidate["initial_ipv4"], "tls": [{"success": True, "elapsed_ms": 30.0}],
                    "front_door": {"class": "DIRECT_LIKELY"}, "hard_rejections": [], "review": [], "warnings": [],
                    "eligibility": "ELIGIBLE"}

        timings = {"old.example.org": 80.0, "a.example.org": 40.0, "b.example.org": 42.0, "c.example.org": 44.0,
                   "d.example.org": 46.0, "e.example.org": 48.0}

        def fake_benchmark(rows, *, samples, timeout, deep):
            out = []
            for row in rows:
                p50 = timings[row["hostname"]]
                out.append({"hostname": row["hostname"], "incumbent": bool(row.get("incumbent")),
                            "sources": row.get("sources", []), "organizations": row.get("organizations", []),
                            "eligibility": row.get("eligibility", "ELIGIBLE"), "front_door": row.get("front_door", {"class": "DIRECT_LIKELY"}),
                            "warnings": [], "review": [], "hard_rejections": [], "dns": {}, "current_ipv4": row.get("current_ipv4") or row.get("initial_ipv4"),
                            "samples": [], "sample_count": samples, "successes": samples, "success_rate": 1.0,
                            "per_ip": {(row.get("current_ipv4") or row.get("initial_ipv4"))[0]: {"samples": samples, "success_rate": 1.0}},
                            "p50_ms": p50, "p90_ms": p50 + 5 if deep else None, "p95_ms": p50 + 8 if deep else None,
                            "max_ms": p50 + 10, "mad_ms": 1.0})
            return out

        def fake_reality(host, ips, attempts, env):
            return {"hostname": host, "attempts": [{"transport_success": True, "cleanup_success": True}] * attempts,
                    "attempt_count": attempts, "transport_successes": attempts, "cleanup_successes": attempts,
                    "passed": True, "dirty": False, "code": "OK", "failure_counts": {}, "dominant_failure_stage": None}

        identity = {"protocol": 4, "manifest": manifest, "profile": "target-measured-v4"}
        with patch.object(target_worker, "preflight", return_value=pre), \
             patch.object(target_worker, "discover", return_value={"validated": candidates, "coverage": "LIMITED", "errors": ["ct:TimeoutError"],
                                                                     "counts": {"source_records": 6, "validated_ipv4": 6}, "source_records": candidates}), \
             patch.object(target_worker, "gate_candidate", side_effect=fake_gate), \
             patch.object(target_worker, "benchmark_candidates", side_effect=fake_benchmark), \
             patch.object(target_worker, "enrich_deep_asn", return_value=None), \
             patch.object(target_worker, "reality_environment", return_value={"ready": True, "sing_box": "/bin/true", "curl": "/bin/true"}), \
             patch.object(target_worker, "run_candidate", side_effect=fake_reality):
            result = target_worker.run(target_worker.validate_job(job), identity)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual([r["hostname"] for r in result["top5"]], ["a.example.org", "b.example.org", "c.example.org", "d.example.org", "e.example.org"])
        self.assertEqual(result["top5"][0]["incumbent_p50_improvement_pct"], 50.0)
        self.assertGreaterEqual(len({r["hostname"] for r in result["comparison"]}), 5)
        self.assertTrue(any(r["hostname"] == "old.example.org" for r in result["comparison"]))
        self.assertEqual(result["coverage"]["selection_maturity"], "PROVISIONAL")


    def test_reality_control_retries_only_after_first_failure(self):
        first = {"hostname": "old.example", "attempts": [{"transport_success": False, "cleanup_success": True, "failure_stage": "PROXY_HEAD"}],
                 "attempt_count": 1, "transport_successes": 0, "cleanup_successes": 1, "passed": False, "dirty": False, "code": "HARD:REALITY_FAILED"}
        retry = {"hostname": "old.example", "attempts": [{"transport_success": True, "cleanup_success": True, "failure_stage": None},
                                                                  {"transport_success": True, "cleanup_success": True, "failure_stage": None}],
                 "attempt_count": 2, "transport_successes": 2, "cleanup_successes": 2, "passed": True, "dirty": False, "code": "OK"}
        with patch.object(target_worker, "run_candidate", side_effect=[first, retry]) as mocked:
            out = target_worker._run_reality_control("old.example", ["93.184.216.34"], {"ready": True})
        self.assertEqual(mocked.call_count, 2)
        self.assertTrue(out["passed"])
        self.assertTrue(out["retried"])
        self.assertEqual(out["transport_successes"], 2)
        self.assertEqual(out["attempt_count"], 3)

    def test_comparison_does_not_promote_reality_passed_policy_reject(self):
        deep = [
            {"hostname": "good.example", "incumbent": False, "eligibility": "ELIGIBLE", "hard_rejections": [], "success_rate": 1.0,
             "p50_ms": 40, "p95_ms": 50, "mad_ms": 2},
            {"hostname": "pantheon.example", "incumbent": False, "eligibility": "HARD_REJECTED", "hard_rejections": ["HARD:KNOWN_SHARED_PLATFORM"],
             "success_rate": 1.0, "p50_ms": 20, "p95_ms": 25, "mad_ms": 1},
        ]
        reality = {"candidates": [
            {"hostname": "good.example", "passed": True, "transport_successes": 5, "attempt_count": 5},
            {"hostname": "pantheon.example", "passed": True, "transport_successes": 5, "attempt_count": 5},
        ]}
        rows = target_worker.build_comparison(deep, [], reality, "old.example", 5, None)
        good = next(r for r in rows if r["hostname"] == "good.example")
        bad = next(r for r in rows if r["hostname"] == "pantheon.example")
        self.assertEqual(good["final_state"], "SELECTABLE")
        self.assertEqual(bad["final_state"], "POLICY_REJECTED")
        self.assertLess(good["recommendation_rank"], bad["recommendation_rank"])


if __name__ == "__main__":
    unittest.main()
