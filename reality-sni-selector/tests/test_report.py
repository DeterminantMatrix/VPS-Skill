#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from report import render_report


class ReportTests(unittest.TestCase):
    def _row(self, i: int):
        return {
            "recommendation_rank": i,
            "hostname": f"d{i}.example",
            "recommendation": "HIGH",
            "recommendation_grade": "A+" if i <= 2 else "A",
            "recommendation_label": "强烈推荐" if i <= 2 else "推荐",
            "final_state": "SELECTABLE",
            "final": "SELECTABLE",
            "policy_eligibility": "ELIGIBLE",
            "policy_grade": "PASS",
            "front_door": {"class": "DIRECT_LIKELY"},
            "protocol_compliance": {"state": "PASS", "tls13": True, "h2": True, "certificate": "PASS", "redirect_policy": "PASS", "per_ip": {"1.1.1.1": {"tls13": True, "h2": True, "tls_versions": ["TLSv1.3"], "alpn": ["h2"]}}},
            "tls_versions": ["TLSv1.3"],
            "alpn_protocols": ["h2"],
            "success_rate": 1.0,
            "sample_count": 20,
            "p50_ms": 30 + i,
            "p90_ms": 38 + i,
            "p95_ms": 40 + i,
            "mad_ms": 2,
            "reality_compatibility": "PASS",
            "reality_grade": "A+",
            "reality_summary": {"transport_successes": 5, "attempt_count": 5},
            "tls_grade": "A+",
            "performance_grade": "A+",
            "runtime_stability_grade": "A",
            "network_affinity": {"grade": "A+", "code": "SAME_ASN", "rank": 0},
            "network_affinity_grade": "A+",
            "network_affinity_code": "SAME_ASN",
            "durability_risk": "LOW",
            "candidate_confidence": "HIGH",
            "search_confidence": "HIGH",
            "overall_recommendation_confidence": "HIGH",
            "decision_reasons": ["POLICY_PASS", "REALITY_5_OF_5_PASS"],
            "ranking_rationale": "完整通过并按尾延迟与稳定性排序。",
            "incumbent_p50_improvement_pct": 40 - i,
            "sources": ["wikidata"],
            "organizations": ["Example Org"],
        }

    def _result(self, n=5):
        comparison = [self._row(i + 1) for i in range(n)]
        top = comparison[:5]
        decision = {
            "reporting_contract": "v4.4",
            "recommended_sni": top[0]["hostname"] if top else None,
            "recommended_grade": top[0]["recommendation_grade"] if top else None,
            "recommended_label": top[0]["recommendation_label"] if top else None,
            "candidate_confidence": "HIGH" if top else "LOW",
            "search_confidence": "HIGH",
            "overall_recommendation_confidence": "HIGH" if top else "LOW",
            "p50_equivalence_ms": 2.0,
        }
        return {
            "status": "SUCCESS",
            "frozen_run": {"region": "US", "incumbent": "old.example", "profile": {"run_mode": "quick"}},
            "preflight": {"observed_egress_ip": "155.254.127.55"},
            "coverage": {"profile": "quick", "status": "GOOD", "validated": 200, "goal": 200, "selection_maturity": "QUICK_CONFIDENT"},
            "counts": {"discovered": 200, "eligibility_selected": 80, "eligible": 30, "review_required": 4, "hard_rejected": 46, "fast_benchmarked": 36, "deep_benchmarked": 10, "deep_reused_samples": 30, "deep_new_samples": 170, "reality_tested": 5, "reality_passed": 5, "selectable": len(top), "selectable_target": 5},
            "decision_summary": decision,
            "incumbent_assessment": {"hostname": "old.example", "code": "KEEP", "verdict": "继续使用", "confidence": "HIGH", "reasons": ["CURRENT_SNI_PASSES_POLICY_RELIABILITY_AND_REALITY"], "tradeoff_text": "当前 SNI 与首选性能接近。", "metrics": {"success_rate": 1.0, "p50_ms": 60, "p95_ms": 70, "mad_ms": 2, "reality_control": "PASS", "hard_rejections": [], "protocol_compliance": {"state": "PASS", "tls13": True, "h2": True, "certificate": "PASS", "redirect_policy": "PASS", "per_ip": {}}, "tls_versions": ["TLSv1.3"], "alpn_protocols": ["h2"], "network_affinity": {"grade": "A+", "code": "SAME_ASN", "rank": 0}}},
            "comparison": comparison,
            "top5": top,
            "warnings": [],
        }

    def test_report_has_incumbent_assessment_and_five_domains(self):
        text = render_report(self._result())
        self.assertIn("当前 SNI 健康卡", text)
        self.assertIn("继续使用", text)
        self.assertIn("Top 5 核心决策表", text)
        for i in range(5):
            self.assertIn(f"`d{i+1}.example`", text)

    def test_report_exposes_decision_dimensions_and_model_commentary_rule(self):
        text = render_report(self._result())
        self.assertIn("运行稳定性", text)
        self.assertIn("Operational risk", text)
        self.assertIn("候选自身置信度", text)
        self.assertIn("搜索覆盖置信度", text)
        self.assertIn("模型评语规则", text)
        self.assertIn("排名理由", text)
        self.assertIn("REALITY Protocol", text)
        self.assertIn("TLS / ALPN", text)
        self.assertIn("Network affinity", text)

    def test_report_shows_sample_reuse(self):
        text = render_report(self._result())
        self.assertIn("reused 30", text)
        self.assertIn("new 170", text)

    def test_report_never_fabricates_rows(self):
        text = render_report(self._result(1))
        self.assertIn("FEWER_THAN_FIVE_SELECTABLE", text)
        self.assertIn("INSUFFICIENT_COMPARISON_DOMAINS", text)


if __name__ == "__main__":
    unittest.main()
