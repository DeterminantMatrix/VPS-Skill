#!/usr/bin/env python3
from __future__ import annotations
from typing import Any

def _fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "unknown"
    return f"{value}{suffix}"


def _pct(value: Any) -> str:
    if value is None:
        return "unknown"
    return f"{float(value) * 100:.1f}%" if 0 <= float(value) <= 1 else f"{value}%"


def _front(row: dict[str, Any]) -> str:
    front = row.get("front_door") or {}
    cls = front.get("class") or "unknown"
    name = front.get("platform") or front.get("provider")
    return f"{cls}/{name}" if name else str(cls)


def _asn_org(row: dict[str, Any]) -> str:
    evidence = row.get("asn_evidence") or {}
    asn = evidence.get("asn")
    org = evidence.get("organization")
    if asn or org:
        return "/".join(str(v) for v in (asn, org) if v)
    front = row.get("front_door") or {}
    metadata = front.get("network_metadata") or {}
    for item in metadata.values() if isinstance(metadata, dict) else []:
        if isinstance(item, dict) and (item.get("asn") or item.get("organization")):
            return "/".join(str(v) for v in (item.get("asn"), item.get("organization")) if v)
    return "unknown"


def _reality(row: dict[str, Any]) -> str:
    state = row.get("reality_compatibility")
    summary = row.get("reality_summary") or row.get("reality") or {}
    if state == "PASS":
        return f"PASS {summary.get('transport_successes', 0)}/{summary.get('attempt_count', len(summary.get('attempts', [])) or 5)}"
    if state == "FAIL":
        stage = summary.get("dominant_failure_stage") or summary.get("code") or "failed"
        return f"FAIL/{stage}"
    if row.get("incumbent"):
        return "control/baseline"
    return "NOT_TESTED"



def _assessment_metrics(assessment: dict[str, Any]) -> str:
    metrics = assessment.get("metrics") or {}
    parts = []
    for key, label, suffix in (("success_rate", "success", ""), ("p50_ms", "P50", " ms"), ("p95_ms", "P95", " ms"), ("mad_ms", "MAD", " ms")):
        value = metrics.get(key)
        if value is None:
            continue
        if key == "success_rate":
            parts.append(f"{label} {_pct(value)}")
        else:
            parts.append(f"{label} {value}{suffix}")
    return ", ".join(parts) if parts else "measurement incomplete"

def _confidence_zh(value: Any) -> str:
    return {
        "HIGH": "高",
        "MEDIUM_HIGH": "中高",
        "MEDIUM": "中",
        "LOW": "低",
    }.get(str(value), str(value or "未知"))


def _risk_zh(value: Any) -> str:
    return {"LOW": "低", "MEDIUM": "中", "HIGH": "高"}.get(str(value), str(value or "未知"))


def _policy_label(row: dict[str, Any]) -> str:
    grade = row.get("policy_grade")
    if grade:
        return str(grade)
    if row.get("hard_rejections"):
        return "FAIL"
    return "REVIEW" if row.get("policy_eligibility") == "REVIEW_REQUIRED" else "PASS"


def _reality_label(row: dict[str, Any]) -> str:
    if row.get("reality_grade") == "A+":
        return "5/5 PASS"
    return _reality(row)


def _protocol_label(row: dict[str, Any]) -> str:
    grade = row.get("protocol_compliance_grade")
    if grade:
        return str(grade)
    protocol = row.get("protocol_compliance") or {}
    return str(protocol.get("state") or "UNKNOWN")


def _protocol_details(row: dict[str, Any]) -> str:
    protocol = row.get("protocol_compliance") or {}
    tls13 = "TLS1.3✓" if protocol.get("tls13") else "TLS1.3✗"
    h2 = "h2✓" if protocol.get("h2") else "h2✗"
    cert = str(protocol.get("certificate") or "UNKNOWN")
    redirect = str(protocol.get("redirect_policy") or "UNKNOWN")
    return f"{tls13} / {h2} / cert:{cert} / redirect:{redirect}"


def _certificate_validity(row: dict[str, Any]) -> str:
    """Report the shortest observed certificate validity without inventing missing data."""
    records: list[dict[str, Any]] = []
    direct = row.get("certificate")
    if isinstance(direct, dict):
        records.append(direct)
    for key in ("tls", "samples"):
        values = row.get(key) or []
        if isinstance(values, dict):
            values = [values]
        for value in values:
            if isinstance(value, dict) and isinstance(value.get("certificate"), dict):
                records.append(value["certificate"])
    observed = []
    for cert in records:
        days = cert.get("days_remaining")
        if days is None and not cert.get("not_after"):
            continue
        try:
            numeric_days = float(days) if days is not None else None
        except (TypeError, ValueError):
            numeric_days = None
        observed.append((numeric_days, str(cert.get("not_after") or "unknown")))
    if not observed:
        return "unknown"
    with_days = [item for item in observed if item[0] is not None]
    if with_days:
        days, not_after = min(with_days, key=lambda item: item[0])
        return f"{days:.2f} 天剩余（{not_after}）"
    return f"到期时间 {observed[0][1]}"


def _tls_versions(row: dict[str, Any]) -> str:
    versions = row.get("tls_versions") or []
    alpn = row.get("alpn_protocols") or []
    protocol = row.get("protocol_compliance") or {}
    if not versions:
        versions = sorted({v for info in (protocol.get("per_ip") or {}).values() for v in (info.get("tls_versions") or [])})
    if not alpn:
        alpn = sorted({v for info in (protocol.get("per_ip") or {}).values() for v in (info.get("alpn") or [])})
    left = ",".join(str(v) for v in versions) or "unknown"
    right = ",".join(str(v) for v in alpn) or "unknown"
    return f"{left} / {right}"


def _network_affinity(row: dict[str, Any]) -> str:
    affinity = row.get("network_affinity") or {}
    grade = row.get("network_affinity_grade") or affinity.get("grade") or "UNKNOWN"
    code = row.get("network_affinity_code") or affinity.get("code") or "NETWORK_AFFINITY_UNKNOWN"
    return f"{grade}/{code}"

