#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from report import render_report


class ReportTests(unittest.TestCase):
    def _result(self, n=5):
        comparison = [{"recommendation_rank": i + 1, "hostname": f"d{i+1}.example", "recommendation": "HIGH", "final_state": "SELECTABLE", "policy_eligibility": "ELIGIBLE", "front_door": {"class": "DIRECT_LIKELY"}, "success_rate": 1.0, "p50_ms": 30 + i, "p95_ms": 40 + i, "mad_ms": 2, "reality_compatibility": "PASS", "reality_summary": {"transport_successes": 5, "attempt_count": 5}} for i in range(n)]
        return {"status": "SUCCESS", "frozen_run": {"region": "US", "incumbent": "old.example", "profile": {"run_mode": "quick"}}, "preflight": {"observed_egress_ip": "155.254.127.55"}, "coverage": {"profile": "quick", "status": "GOOD", "validated": 150, "goal": 150, "selection_maturity": "QUICK_CONFIDENT"}, "counts": {"discovered": 150, "eligibility_selected": 60, "fast_benchmarked": 30, "deep_benchmarked": 10, "deep_reused_samples": 30, "deep_new_samples": 170, "reality_tested": 5, "reality_passed": 5, "selectable": 5, "selectable_target": 5}, "incumbent_assessment": {"code": "KEEP", "verdict": "继续使用", "confidence": "HIGH", "reasons": ["CURRENT_SNI_PASSES_POLICY_RELIABILITY_AND_REALITY"], "metrics": {"success_rate": 1.0, "p50_ms": 60, "p95_ms": 70, "mad_ms": 2, "reality_control": "PASS"}}, "comparison": comparison, "top5": comparison[:5], "warnings": []}

    def test_report_has_incumbent_assessment_and_five_domains(self):
        text = render_report(self._result())
        self.assertIn("Current SNI assessment", text)
        self.assertIn("继续使用", text)
        for i in range(5):
            self.assertIn(f"`d{i+1}.example`", text)

    def test_report_shows_sample_reuse(self):
        text = render_report(self._result())
        self.assertIn("Reused Fast samples in Deep", text)
        self.assertIn("New Deep samples", text)

    def test_report_never_fabricates_rows(self):
        text = render_report(self._result(1))
        self.assertIn("INSUFFICIENT_COMPARISON_DOMAINS", text)


if __name__ == "__main__":
    unittest.main()
