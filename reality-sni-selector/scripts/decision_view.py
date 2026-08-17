#!/usr/bin/env python3
from __future__ import annotations
from typing import Any
from common import PROTOCOL_HARD_CODES, RELIABILITY_HARD_CODES, SAFETY_HARD_CODES, SAFETY_REVIEW_CODES
from decision_grades import (
    _durability_risk,
    _network_affinity_grade,
    _overall_confidence,
    _performance_grade,
    _protocol_grade,
    _runtime_stability_grade,
    _search_confidence,
    _tls_reliability_grade,
)

def _enrich_candidate(row: dict[str, Any], *, search_confidence: str, search_reasons: list[str], latency_target_ms: float, selectable: bool) -> dict[str, Any]:
    out = dict(row)
    final_state = "SELECTABLE" if selectable else str(out.get("final_state") or out.get("final") or "UNKNOWN")
    hard = list(out.get("hard_rejections") or [])
    hard_set = set(hard)
    safety_hard = sorted(hard_set & SAFETY_HARD_CODES)
    protocol_hard = sorted(hard_set & PROTOCOL_HARD_CODES)
    reliability_hard = sorted(hard_set & RELIABILITY_HARD_CODES)
    review_signals = list(out.get("review") or [])
    safety_review = sorted(set(review_signals) & SAFETY_REVIEW_CODES)
    policy_grade = "FAIL" if safety_hard else "REVIEW" if safety_review else "PASS"
    reality = out.get("reality") or out.get("reality_summary") or {}
    reality_pass = bool(reality.get("passed")) or out.get("reality_compatibility") == "PASS"
    attempts = int(reality.get("attempt_count") or len(reality.get("attempts") or []))
    passes = int(reality.get("transport_successes") or (5 if reality_pass else 0))
    protocol_grade = _protocol_grade(out)
    tls_reliability = _tls_reliability_grade(out)
    performance = _performance_grade(out, latency_target_ms)
    stability, stability_reasons = _runtime_stability_grade(out)
    durability, durability_reasons = _durability_risk(out, stability)
    affinity_grade, affinity_code = _network_affinity_grade(out)
    complete_deep = int(out.get("sample_count") or 0) >= 20
    candidate_confidence = "HIGH" if selectable and complete_deep and reality_pass and attempts >= 5 and passes >= 5 and float(out.get("success_rate") or 0.0) >= 0.95 else "MEDIUM" if complete_deep else "LOW"
    overall = _overall_confidence(candidate_confidence, search_confidence)
    if selectable and protocol_grade == "PASS" and candidate_confidence == "HIGH" and stability == "A" and performance in {"A+", "A"} and durability == "LOW":
        rec_grade, rec_label = "A+", "强烈推荐"
    elif selectable and protocol_grade == "PASS" and candidate_confidence == "HIGH" and stability in {"A", "B"} and performance in {"A+", "A", "B"} and durability in {"LOW", "MEDIUM"}:
        rec_grade, rec_label = "A", "推荐"
    elif selectable:
        rec_grade, rec_label = "B+", "可选"
    else:
        rec_grade, rec_label = str(out.get("recommendation") or "C"), "对照"
    reasons = []
    if selectable:
        reasons += ["POLICY_PASS", "REALITY_5_OF_5_PASS"]
    elif hard:
        reasons += hard
    reasons += [
        f"PROTOCOL_COMPLIANCE_{protocol_grade}",
        f"TLS_RELIABILITY_{tls_reliability}",
        f"PERFORMANCE_GRADE_{performance}",
        f"RUNTIME_STABILITY_{stability}",
        f"NETWORK_AFFINITY_{affinity_code}",
        f"DURABILITY_RISK_{durability}",
        f"SEARCH_CONFIDENCE_{search_confidence}",
    ]
    out.update({
        "final_state": final_state,
        "policy_grade": policy_grade,
        "protocol_hard_rejections": protocol_hard,
        "safety_hard_rejections": safety_hard,
        "safety_review_signals": safety_review,
        "reliability_hard_rejections": reliability_hard,
        "reality_grade": "A+" if reality_pass else "F" if reality else "NOT_TESTED",
        "protocol_compliance_grade": protocol_grade,
        "tls_reliability_grade": tls_reliability,
        "tls_grade": tls_reliability,
        "performance_grade": performance,
        "runtime_stability_grade": stability,
        "runtime_stability_reasons": stability_reasons,
        "network_affinity_grade": affinity_grade,
        "network_affinity_code": affinity_code,
        "durability_risk": durability,
        "durability_reasons": durability_reasons,
        "candidate_confidence": candidate_confidence,
        "search_confidence": search_confidence,
        "search_confidence_reasons": list(search_reasons),
        "overall_recommendation_confidence": overall,
        "recommendation_grade": rec_grade,
        "recommendation_label": rec_label,
        "recommendation_tier": "TIER_A_PRIMARY" if selectable and rec_grade in {"A+", "A"} else "TIER_B_BACKUP" if selectable else "TIER_C_REFERENCE",
        "decision_reasons": reasons,
    })
    out["model_commentary_facts"] = {
        "hostname": out.get("hostname"),
        "final_state": final_state,
        "protocol_compliance": protocol_grade,
        "protocol_details": out.get("protocol_compliance") or {},
        "policy": policy_grade,
        "reality": "PASS_5_OF_5" if reality_pass else "FAIL_OR_NOT_TESTED",
        "tls_reliability": tls_reliability,
        "p50_ms": out.get("p50_ms"),
        "p95_ms": out.get("p95_ms"),
        "mad_ms": out.get("mad_ms"),
        "performance": performance,
        "runtime_stability": stability,
        "network_affinity": {"grade": affinity_grade, "code": affinity_code},
        "discovery_lanes": out.get("lanes") or [],
        "discovery_sources": out.get("sources") or [],
        "durability_risk": durability,
        "candidate_confidence": candidate_confidence,
        "search_confidence": search_confidence,
        "overall_confidence": overall,
        "incumbent_p50_improvement_pct": out.get("incumbent_p50_improvement_pct"),
    }
    return out


def _ranking_rationale(rows: list[dict[str, Any]], index: int, equivalence_ms: float) -> tuple[str, str]:
    row = rows[index]
    if index == 0:
        other = rows[1] if len(rows) > 1 else None
        if other and row.get("p50_ms") is not None and other.get("p50_ms") is not None:
            diff = abs(float(row["p50_ms"]) - float(other["p50_ms"]))
            if diff <= equivalence_ms:
                affinity = row.get("network_affinity_code") or "NETWORK_AFFINITY_UNKNOWN"
                return "NEAR_TIE_LEADER", f"与第二名 P50 仅差 {diff:.3f} ms（≤{equivalence_ms:g} ms，视为近似持平）；名次主要由 P95、MAD、网络亲和性（{affinity}）、运行稳定性和长期风险信号打破平局。"
        return "CLEAR_LEADER", "在完整 SELECTABLE 候选中综合 Policy、Reality、TLS、尾延迟和稳定性证据排名最高。"
    prev = rows[index - 1]
    if row.get("p50_ms") is not None and prev.get("p50_ms") is not None:
        diff = abs(float(row["p50_ms"]) - float(prev["p50_ms"]))
        if diff <= equivalence_ms:
            affinity = row.get("network_affinity_code") or "NETWORK_AFFINITY_UNKNOWN"
            return "NEAR_TIE", f"与上一名 P50 仅差 {diff:.3f} ms（≤{equivalence_ms:g} ms），属于近似同级；排序主要参考 P95、MAD、网络亲和性（{affinity}）、运行稳定性和长期风险信号。"
        return "LATENCY_GAP", f"P50 与上一名相差 {diff:.3f} ms；在同样通过 Policy/Reality 的前提下综合表现略逊。"
    return "RANKED_SELECTABLE", "完整通过 Policy、Benchmark 与 Reality；按综合性能和稳定性证据排序。"


def _tradeoff(assessment: dict[str, Any], best: dict[str, Any] | None) -> tuple[str, str, dict[str, Any] | None]:
    metrics = assessment.get("metrics") or {}
    current_p50 = metrics.get("p50_ms")
    current_p95 = metrics.get("p95_ms")
    if not best or current_p50 is None or best.get("p50_ms") is None or float(current_p50) <= 0:
        return "NO_COMPARISON", "尚无足够证据比较当前 SNI 与首选候选。", None
    p50_imp = round((float(current_p50) - float(best["p50_ms"])) / float(current_p50) * 100.0, 2)
    p95_imp = None
    if current_p95 is not None and best.get("p95_ms") is not None and float(current_p95) > 0:
        p95_imp = round((float(current_p95) - float(best["p95_ms"])) / float(current_p95) * 100.0, 2)
    alt = {"hostname": best.get("hostname"), "p50_ms": best.get("p50_ms"), "p95_ms": best.get("p95_ms"), "p50_improvement_pct": p50_imp, "p95_improvement_pct": p95_imp, "recommendation_grade": best.get("recommendation_grade"), "overall_recommendation_confidence": best.get("overall_recommendation_confidence")}
    hard = list(metrics.get("hard_rejections") or [])
    if p50_imp < -2.0 and hard:
        return "CURRENT_FASTER_BUT_POLICY_REJECTED", f"当前 SNI 性能更快（P50 约快 {abs(p50_imp):.1f}%），但命中硬策略拒绝 {', '.join(hard)}；性能优势不能抵消该风险，因此仍需更换。", alt
    if p50_imp < -2.0:
        return "CURRENT_FASTER_THAN_RECOMMENDED", f"当前 SNI 的 P50 比首选候选更快约 {abs(p50_imp):.1f}%；是否更换应优先服从当前 verdict 的策略/可靠性依据。", alt
    if p50_imp > 2.0:
        return "RECOMMENDED_FASTER_THAN_CURRENT", f"首选候选的 P50 比当前 SNI 改善约 {p50_imp:.1f}%。", alt
    return "PERFORMANCE_NEAR_TIE", "当前 SNI 与首选候选的 P50 基本持平，应优先比较策略、Reality、P95/MAD 与稳定性。", alt


def build_decision_view(result: dict[str, Any]) -> dict[str, Any]:
    coverage = result.get("coverage") or {}
    counts = result.get("counts") or {}
    frozen = result.get("frozen_run") or {}
    profile = frozen.get("profile") or {}
    latency_target = float(profile.get("latency_target_ms") or 60.0)
    equivalence_ms = float(profile.get("p50_equivalence_ms") or 2.0)
    selectable_target = int(counts.get("selectable_target") or 5)
    raw_top = list(result.get("top5") or [])
    search_conf, search_reasons = _search_confidence(coverage, len(raw_top), selectable_target)
    top = [_enrich_candidate(row, search_confidence=search_conf, search_reasons=search_reasons, latency_target_ms=latency_target, selectable=True) for row in raw_top]
    for idx, row in enumerate(top):
        code, text = _ranking_rationale(top, idx, equivalence_ms)
        row["recommendation_rank"] = idx + 1
        row["ranking_rationale_code"] = code
        row["ranking_rationale"] = text
    by_host = {row.get("hostname"): row for row in top}
    comparison = []
    for raw in result.get("comparison") or []:
        host = raw.get("hostname")
        if host in by_host:
            comparison.append(dict(by_host[host]))
        else:
            comparison.append(_enrich_candidate(raw, search_confidence=search_conf, search_reasons=search_reasons, latency_target_ms=latency_target, selectable=False))
    assessment = dict(result.get("incumbent_assessment") or {})
    tradeoff_code, tradeoff_text, alt = _tradeoff(assessment, top[0] if top else None)
    assessment["tradeoff_code"] = tradeoff_code
    assessment["tradeoff_text"] = tradeoff_text
    if alt:
        assessment["best_alternative"] = alt
    best = top[0] if top else {}
    summary = {
        "reporting_contract": "v4.4",
        "recommended_sni": best.get("hostname"),
        "recommended_grade": best.get("recommendation_grade"),
        "recommended_label": best.get("recommendation_label"),
        "candidate_confidence": best.get("candidate_confidence", "LOW"),
        "search_confidence": search_conf,
        "search_confidence_reasons": search_reasons,
        "overall_recommendation_confidence": best.get("overall_recommendation_confidence", "LOW"),
        "p50_equivalence_ms": equivalence_ms,
        "selectable_count": len(top),
        "selectable_target": selectable_target,
        "coverage": coverage,
        "incumbent_tradeoff_code": tradeoff_code,
        "incumbent_tradeoff_text": tradeoff_text,
        "network_affinity_search": result.get("network_affinity_search") or {},
        "discovery_lanes": coverage.get("lane_counts") or {},
    }
    return {"top5": top, "comparison": comparison, "incumbent_assessment": assessment, "decision_summary": summary}

