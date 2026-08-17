#!/usr/bin/env python3
from __future__ import annotations
from typing import Any

def _run_coverage_confidence(coverage: dict[str, Any], selectable_count: int, selectable_target: int) -> tuple[str, list[str]]:
    """Confidence that the configured bounded search ran with useful breadth/quality."""
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


def _global_optimality_confidence(
    coverage: dict[str, Any],
    selectable_count: int,
    selectable_target: int,
    *,
    quality_target_met: bool,
) -> tuple[str, list[str]]:
    """Confidence that this bounded run is close to the best available choice.

    This is intentionally stricter than run-coverage confidence. Hitting source
    caps, source failures, weak lane diversity, or failing the quality target
    prevents a HIGH global-optimality claim.
    """
    run_conf, reasons = _run_coverage_confidence(coverage, selectable_count, selectable_target)
    saturation = coverage.get("saturation") or {}
    source_errors = list(coverage.get("source_errors") or [])
    lanes = list(coverage.get("active_discovery_lanes") or [])
    reasons = list(reasons)
    if saturation.get("any_cap_hit"):
        reasons.append("SEARCH_CAP_SATURATED")
    if source_errors:
        reasons.append("SOURCE_ERRORS_PRESENT")
    if len(lanes) < 3:
        reasons.append("DISCOVERY_LANE_COVERAGE_INCOMPLETE")
    if not quality_target_met:
        reasons.append("QUALITY_TARGET_NOT_MET")
    if run_conf == "LOW":
        return "LOW", reasons
    if run_conf == "HIGH" and not saturation.get("any_cap_hit") and not source_errors and len(lanes) >= 3 and quality_target_met:
        return "HIGH", reasons
    if selectable_count >= selectable_target:
        return "MEDIUM", reasons
    return "LOW" if run_conf == "MEDIUM" else "MEDIUM", reasons


def _search_confidence(coverage: dict[str, Any], selectable_count: int, selectable_target: int) -> tuple[str, list[str]]:
    """Compatibility alias for the v4.5 run-coverage confidence dimension."""
    return _run_coverage_confidence(coverage, selectable_count, selectable_target)

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
    """Compatibility alias; v4.5 reports this dimension as TLS reliability."""
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


def _latency_consistency_grade(row: dict[str, Any]) -> tuple[str, list[str]]:
    """Grade observed latency dispersion separately from transport reliability."""
    p50 = row.get("p50_ms")
    p95 = row.get("p95_ms")
    mad = row.get("mad_ms")
    spread = None if p50 is None or p95 is None else max(0.0, float(p95) - float(p50))
    reasons: list[str] = []
    if mad is not None and float(mad) > 4.0:
        reasons.append("MAD_ABOVE_4MS")
    if spread is not None and spread > 15.0:
        reasons.append("P95_SPREAD_ABOVE_15MS")
    if (mad is None or float(mad) <= 4.0) and (spread is None or spread <= 15.0):
        return "A", reasons
    if (mad is None or float(mad) <= 7.5) and (spread is None or spread <= 25.0):
        return "B", reasons
    return "C", reasons


def _runtime_stability_grade(row: dict[str, Any]) -> tuple[str, list[str]]:
    """Compatibility alias for old artifacts; use latency_consistency in v4.5."""
    return _latency_consistency_grade(row)

def _durability_risk(row: dict[str, Any], _legacy_stability_grade: str | None = None) -> tuple[str, list[str]]:
    """Operational heuristic independent of one-run latency dispersion.

    Durability uses only current observable DNS/front-door/review/organization
    evidence. P50/P95/MAD belong to performance and latency consistency, not to
    a claim about future availability.
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
    if front in {"DIRECT_CONFIRMED", "DIRECT_LIKELY"} and organizations:
        return "LOW", reasons
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


