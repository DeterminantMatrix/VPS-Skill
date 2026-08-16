#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from report import render_report  # noqa: E402


class ReportTests(unittest.TestCase):
    def test_report_has_hierarchical_counts_and_five_domain_table(self):
        comparison = []
        for i in range(5):
            comparison.append({
                "recommendation_rank": i + 1,
                "hostname": f"d{i+1}.example.org",
                "recommendation": "HIGH" if i < 2 else "PENDING",
                "final_state": "SELECTABLE" if i < 2 else "NOT_REALITY_TESTED",
                "policy_eligibility": "ELIGIBLE",
                "front_door": {"class": "DIRECT_LIKELY"},
                "success_rate": 1.0,
                "p50_ms": 30 + i,
                "p95_ms": 40 + i,
                "mad_ms": 2 + i,
                "reality_compatibility": "PASS" if i < 2 else "NOT_TESTED",
                "reality_summary": {"transport_successes": 5, "attempt_count": 5} if i < 2 else None,
                "asn_evidence": {"asn": 64500 + i, "organization": f"Org{i+1}"},
                "incumbent_p50_improvement_pct": 20 - i,
            })
        text = render_report({
            "status": "SUCCESS",
            "frozen_run": {"region": "US", "incumbent": "old.example.org"},
            "preflight": {"observed_egress_ip": "155.254.127.55"},
            "coverage": {"status": "LIMITED", "validated": 239, "goal": 400, "selection_maturity": "PROVISIONAL", "source_errors": ["CT_SKIPPED_AFTER_FAILURE_BUDGET"]},
            "counts": {"discovered": 239, "eligibility_selected": 120, "deferred_budget": 119, "deferred_diversity": 22,
                       "eligible": 60, "hard_rejected": 46, "review_required": 14, "fast_benchmarked": 50,
                       "deep_benchmarked": 10, "reality_tested": 5, "reality_passed": 4, "selectable": 2},
            "comparison": comparison,
            "top5": [],
            "warnings": [],
        })
        self.assertIn("Coverage: `LIMITED` (239 / goal 400)", text)
        self.assertIn("Selected for eligibility: **120**", text)
        self.assertIn("Deferred before eligibility: **119**", text)
        self.assertIn("## Recommendation comparison", text)
        for i in range(5):
            self.assertIn(f"`d{i+1}.example.org`", text)
        self.assertNotIn("INSUFFICIENT_COMPARISON_DOMAINS", text)

    def test_report_never_fabricates_missing_comparison_rows(self):
        text = render_report({
            "status": "SUCCESS_WITH_REVIEW",
            "frozen_run": {"region": "US", "incumbent": "old.example.org"},
            "preflight": {}, "coverage": {}, "counts": {},
            "comparison": [{"recommendation_rank": 1, "hostname": "one.example", "recommendation": "LOW"}],
            "top5": [], "warnings": [],
        })
        self.assertIn("INSUFFICIENT_COMPARISON_DOMAINS", text)


if __name__ == "__main__":
    unittest.main()
