#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from report import render_report  # noqa: E402


class ReportTests(unittest.TestCase):
    def test_report_distinguishes_deferred(self):
        text = render_report({
            "status": "SUCCESS",
            "frozen_run": {"region": "US", "incumbent": "old.example"},
            "preflight": {"observed_egress_ip": "203.0.113.1"},
            "counts": {"discovered": 577, "eligibility_selected": 120, "deferred_budget": 457, "hard_rejected": 10,
                       "review_required": 4, "fast_benchmarked": 50, "deep_benchmarked": 10, "reality_tested": 5, "selectable": 3},
            "top5": [], "preliminary_top5": [], "warnings": [],
        })
        self.assertIn("Deferred by budget: 457", text)
        self.assertIn("Hard rejected: 10", text)


if __name__ == "__main__":
    unittest.main()
