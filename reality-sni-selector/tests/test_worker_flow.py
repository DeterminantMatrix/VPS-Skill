#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import target_worker


class WorkerFlowTests(unittest.TestCase):
    def _deep(self, host="old.example", p50=60.0, p95=70.0):
        return {"hostname": host, "incumbent": host == "old.example", "eligibility": "ELIGIBLE", "hard_rejections": [], "review": [], "success_rate": 1.0, "per_ip": {"1.1.1.1": {"samples": 20, "success_rate": 1.0}}, "p50_ms": p50, "p95_ms": p95, "mad_ms": 2.0}

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

    def test_reality_control_retries_only_after_failure(self):
        first = {"attempts": [{"transport_success": False, "cleanup_success": True, "failure_stage": "PROXY_HEAD"}], "passed": False, "dirty": False}
        retry = {"attempts": [{"transport_success": True, "cleanup_success": True}, {"transport_success": True, "cleanup_success": True}], "passed": True, "dirty": False}
        with patch.object(target_worker, "run_candidate", side_effect=[first, retry]) as mocked:
            out = target_worker._run_reality_control("old.example", ["1.1.1.1"], {"ready": True})
        self.assertEqual((mocked.call_count, out["attempt_count"], out["passed"], out["retried"]), (2, 3, True, True))


if __name__ == "__main__":
    unittest.main()
