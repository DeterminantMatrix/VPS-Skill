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
    def test_target_measured_flow_produces_final_candidates(self):
        job = {
            "schema_version": 3,
            "profile_name": "target-measured-v3",
            "target": {"alias": "best-vm-us", "inventory_ipv4": "155.254.127.55"},
            "region": "US",
            "incumbent_mode": "explicit",
            "incumbent": "old.example.org",
            "seed_domains": ["old.example.org", "a.example.org", "b.example.org"],
            "port": 443,
            "limits": {"source_pool_cap": 1200, "discovered_cap": 600, "eligibility_pool": 120, "fast_pool": 50,
                       "deep_pool": 10, "top_n": 5, "fast_samples": 5, "deep_samples": 20, "reality_attempts": 5,
                       "ct_base_cap": 40, "ct_max_per_domain": 20, "dns_workers": 12},
            "profile": {"coverage_goal": 400, "primary_radius_km": 75, "expanded_radius_km": 150,
                        "ct_failure_budget": 3, "latency_target_ms": 60.0},
        }
        pre = {"observed_egress_ip": "155.254.127.55", "location": {"country_code": "US", "asn": 64500},
               "region_mismatch": False, "tools": {}, "warnings": []}
        candidates = [
            {"hostname": "old.example.org", "sources": ["incumbent"], "organizations": [], "initial_ipv4": ["93.184.216.34"]},
            {"hostname": "a.example.org", "sources": ["seed"], "organizations": [], "initial_ipv4": ["93.184.216.34"]},
            {"hostname": "b.example.org", "sources": ["seed"], "organizations": [], "initial_ipv4": ["93.184.216.34"]},
        ]

        def fake_gate(candidate, **kwargs):
            return {**candidate, "current_ipv4": ["93.184.216.34"], "tls": [{"success": True, "elapsed_ms": 30.0}],
                    "front_door": {"class": "DIRECT_LIKELY"}, "hard_rejections": [], "review": [], "warnings": [],
                    "eligibility": "ELIGIBLE"}

        def fake_benchmark(rows, *, samples, timeout, deep):
            out = []
            timings = {"old.example.org": 80.0, "a.example.org": 40.0, "b.example.org": 50.0}
            for row in rows:
                p50 = timings[row["hostname"]]
                out.append({"hostname": row["hostname"], "incumbent": bool(row.get("incumbent")),
                            "sources": row.get("sources", []), "organizations": [], "eligibility": row.get("eligibility", "ELIGIBLE"),
                            "front_door": row.get("front_door", {"class": "DIRECT_LIKELY"}), "warnings": [], "review": [],
                            "hard_rejections": [], "dns": {}, "current_ipv4": ["93.184.216.34"], "samples": [],
                            "sample_count": samples, "successes": samples, "success_rate": 1.0,
                            "per_ip": {"93.184.216.34": {"samples": samples, "success_rate": 1.0}},
                            "p50_ms": p50, "p90_ms": p50 + 5 if deep else None, "p95_ms": p50 + 8 if deep else None,
                            "max_ms": p50 + 10, "mad_ms": 1.0})
            return out

        def fake_reality(host, ips, attempts, env):
            return {"hostname": host, "attempts": [{}] * attempts, "transport_successes": attempts,
                    "cleanup_successes": attempts, "passed": True, "dirty": False, "code": "OK"}

        with patch.object(target_worker, "preflight", return_value=pre), \
             patch.object(target_worker, "discover", return_value={"validated": candidates, "coverage": "SPARSE", "errors": [],
                                                                     "counts": {"source_records": 3, "validated_ipv4": 3}, "source_records": candidates}), \
             patch.object(target_worker, "gate_candidate", side_effect=fake_gate), \
             patch.object(target_worker, "benchmark_candidates", side_effect=fake_benchmark), \
             patch.object(target_worker, "enrich_deep_asn", return_value=None), \
             patch.object(target_worker, "reality_environment", return_value={"ready": True, "sing_box": "/bin/true", "curl": "/bin/true"}), \
             patch.object(target_worker, "run_candidate", side_effect=fake_reality):
            result = target_worker.run(target_worker.validate_job(job))
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual([r["hostname"] for r in result["top5"]], ["a.example.org", "b.example.org"])
        self.assertEqual(result["top5"][0]["incumbent_p50_improvement_pct"], 50.0)


if __name__ == "__main__":
    unittest.main()
