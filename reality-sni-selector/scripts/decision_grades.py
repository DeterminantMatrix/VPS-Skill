#!/usr/bin/env python3
from __future__ import annotations
from typing import Any

def _search_confidence(coverage: dict[str, Any], selectable_count: int, selectable_target: int) -> tuple[str, list[str]]:
    status = str(coverage.get("status") or "SPARSE")
    validated = int(coverage.get("validated") or 0)
    goal = max(1, int(coverage.get("goal") or 1))
    eligible = int(coverage.get("effective_eligible") or 0)
    eligible_goal = max(1, int(coverage.get("eligible_goal") or 1))
    lanes_present = "active_discovery_lanes" in coverage
    lanes = list(coverage.get("active_discovery_lanes") or [])
    reasons = [
        f"COVERAGE_{status}",
        f"VALIDATED_{validated}_OF_{goal}",
        f"ELIGIBLE_{eligible}_OF_{eligible_goal}",
        f"ACTIVE_DISCOVERY_LANES_{len(lanes)}",
    ]
    if status == "GOOD" and eligible >= eligible_goal and len(lanes) >= 2:
        return "HIGH", reasons
    if status in {"GOOD", "LIMITED"} and eligible >= max(5, eligible_goal // 2) and len(lanes) >= 2:
        return "MEDIUM", reasons
    if selectable_count >= selectable_target and validated >= 40 and (len(lanes) >= 2 or not lanes_present):
        reasons.append("SELECTABLE_TARGET_MET_DESPITE_LIMITED_SEARCH")
        if not lanes_present:
            reasons.append("LEGACY_COVERAGE_LANE_DATA_UNAVAILABLE")
        return "MEDIUM", reasons
    return "LOW", reasons


def _protocol_grade(row: dict[str, Any]) -> str:
    protocol = row.get("protocol_compliance") or {}
    state = str(protocol.get("state") or "")
    if state in {"PASS", "FAIL", "REVIEW"}:
        return state
    hard = set(row.get("hard_rejections") or [])
    protocol_hard = {
        "HARD:TLS_UNREACHABLE",
        "HARD:CERT_INVALID",
        "HARD:CERT_IDENTITY",
        "HARD:REALITY_MIN_TLS13",
        "HARD:REALITY_MIN_H2",
        "HARD:REALITY_CROSS_SITE_REDIRECT",
    }
    return "FAIL" if hard & protocol_hard else "UNKNOWN"


def _tls_reliability_grade(row: dict[str, Any]) -> str:
    success = float(row.get("success_rate") or 0.0)
    if success >= 0.9999:
        return "A+"
    if success >= 0.99:
        return "A"
    if success >= 0.97:
        return "B+"
    if success >= 0.95:
        return "B"
    return "F"


def _tls_grade(row: dict[str, Any]) -> str:
    """Compatibility alias; v4.4 reports this dimension as TLS reliability."""
    return _tls_reliability_grade(row)


def _network_affinity_grade(row: dict[str, Any]) -> tuple[str, str]:
    affinity = row.get("network_affinity") or {}
    return str(affinity.get("grade") or "UNKNOWN"), str(affinity.get("code") or "NETWORK_AFFINITY_UNKNOWN")


def _performance_grade(row: dict[str, Any], latency_target_ms: float) -> str:
    p50 = row.get("p50_ms")
    p95 = row.get("p95_ms")
    if p50 is None:
        return "UNKNOWN"
    p50f = float(p50)
    p95f = float(p95) if p95 is not None else p50f
    target = max(1.0, float(latency_target_ms))
    if p50f <= target * 0.75 and p95f <= target:
        return "A+"
    if p50f <= target and p95f <= target * 1.25:
        return "A"
    if p50f <= target * 1.25 and p95f <= target * 1.60:
        return "B"
    return "C"


def _runtime_stability_grade(row: dict[str, Any]) -> tuple[str, list[str]]:
    success = float(row.get("success_rate") or 0.0)
    p50 = row.get("p50_ms")
    p95 = row.get("p95_ms")
    mad = row.get("mad_ms")
    spread = None if p50 is None or p95 is None else max(0.0, float(p95) - float(p50))
    per_ip = [
        float(info.get("success_rate"))
        for info in (row.get("per_ip") or {}).values()
        if (info.get("samples") or 0) >= 3 and info.get("success_rate") is not None
    ]
    min_ip = min(per_ip) if per_ip else None
    volatile = bool((row.get("dns") or {}).get("volatile"))
    reasons: list[str] = []
    if volatile:
        reasons.append("DNS_VOLATILE")
    if min_ip is not None and min_ip < 0.95:
        reasons.append("PER_IP_SUCCESS_BELOW_95")
    if mad is not None and float(mad) > 4.0:
        reasons.append("MAD_ABOVE_4MS")
    if spread is not None and spread > 15.0:
        reasons.append("P95_SPREAD_ABOVE_15MS")
    if success >= 0.99 and not volatile and (min_ip is None or min_ip >= 0.95) and (mad is None or float(mad) <= 4.0) and (spread is None or spread <= 15.0):
        return "A", reasons
    if success >= 0.95 and not volatile and (min_ip is None or min_ip >= 0.90) and (mad is None or float(mad) <= 7.5) and (spread is None or spread <= 25.0):
        return "B", reasons
    return "C", reasons


def _durability_risk(row: dict[str, Any], stability_grade: str) -> tuple[str, list[str]]:
    """Operational heuristic based only on observed evidence.

    Institutional origin is a useful provenance hint, not a requirement. v4.4
    therefore does not penalize a clean general-regional or affinity candidate
    merely because it was not discovered through an institution directory.
    """
    reasons: list[str] = []
    front = (row.get("front_door") or {}).get("class") or "UNKNOWN"
    sources = set(row.get("sources") or [])
    lanes = set(row.get("lanes") or [])
    organizations = [v for v in (row.get("organizations") or []) if v]
    volatile = bool((row.get("dns") or {}).get("volatile"))
    review = list(row.get("review") or [])
    if volatile:
        reasons.append("DNS_VOLATILE")
    if front in {"UNKNOWN_EDGE_EVIDENCE", "UNKNOWN_TOOLING"}:
        reasons.append("FRONT_DOOR_UNCERTAIN")
    if review:
        reasons.append("REVIEW_SIGNALS_PRESENT")
    if not organizations:
        reasons.append("ORGANIZATION_EVIDENCE_LIMITED")
    if "institutional" in lanes or sources & {"wikidata_institutional", "osm_institutional", "openalex_institutional", "wikidata", "osm", "openalex"}:
        reasons.append("INSTITUTIONAL_PROVENANCE_BONUS")
    if "network_affinity" in lanes:
        reasons.append("NETWORK_AFFINITY_DISCOVERY_EVIDENCE")
    if volatile or review or front in {"UNKNOWN_EDGE_EVIDENCE", "UNKNOWN_TOOLING"}:
        return "HIGH", reasons
    if stability_grade == "A" and front in {"DIRECT_CONFIRMED", "DIRECT_LIKELY"} and organizations:
        return "LOW", reasons
    if stability_grade == "A" and front in {"DIRECT_CONFIRMED", "DIRECT_LIKELY"}:
        return "MEDIUM", reasons
    return "MEDIUM", reasons


def _overall_confidence(candidate: str, search: str) -> str:
    if candidate == "HIGH" and search == "HIGH":
        return "HIGH"
    if candidate == "HIGH" and search == "MEDIUM":
        return "MEDIUM_HIGH"
    if candidate == "HIGH":
        return "MEDIUM"
    if candidate == "MEDIUM" and search in {"HIGH", "MEDIUM"}:
        return "MEDIUM"
    return "LOW"


