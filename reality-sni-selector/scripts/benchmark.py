#!/usr/bin/env python3
from __future__ import annotations

import time
from typing import Any

from common import PROTOCOL_HARD_CODES, edge_priority, policy_priority, source_priority, stats
from target_probe import resolve_ipv4_observations, tls_probe_ip


def benchmark_candidates(
    candidates: list[dict[str, Any]],
    *,
    samples: int,
    timeout: float = 5.0,
    deep: bool = False,
    prior_results: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Benchmark candidates to a total sample count, optionally reusing same-run samples."""
    prior_map = {r.get("hostname"): r for r in (prior_results or []) if r.get("hostname")}
    state: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        host = candidate["hostname"]
        dns = resolve_ipv4_observations(host, observations=3 if deep else 2)
        ips = dns["common_ipv4"] or candidate.get("current_ipv4") or candidate.get("initial_ipv4") or []
        prior = prior_map.get(host) or {}
        reused = [dict(r) for r in (prior.get("samples") or [])[:samples]]
        for row in reused:
            row.setdefault("phase", "fast-reused" if deep else "reused")
        state[host] = {
            "candidate": candidate,
            "dns": dns,
            "ips": ips,
            "samples": reused,
            "reused_samples": len(reused),
        }

    # Interleave only the missing samples. Deep mode therefore tops Fast samples up
    # to the requested total instead of discarding and re-measuring them.
    remaining = max((samples - len(item["samples"]) for item in state.values()), default=0)
    for _ in range(remaining):
        for candidate in candidates:
            host = candidate["hostname"]
            item = state[host]
            if len(item["samples"]) >= samples:
                continue
            ips = item["ips"]
            sample_index = len(item["samples"])
            if not ips:
                item["samples"].append({"success": False, "ip": None, "error": "NO_IPV4", "elapsed_ms": None,
                                        "round": sample_index + 1, "phase": "deep" if deep else "fast"})
                continue
            ip = ips[sample_index % len(ips)]
            row = tls_probe_ip(host, ip, timeout=timeout)
            row["round"] = sample_index + 1
            row["phase"] = "deep" if deep else "fast"
            item["samples"].append(row)
            time.sleep(0.03)

    results: list[dict[str, Any]] = []
    for candidate in candidates:
        item = state[candidate["hostname"]]
        rows = item["samples"]
        ok = [r for r in rows if r.get("success")]
        values = [float(r["elapsed_ms"]) for r in ok if r.get("elapsed_ms") is not None]
        observed_ips = sorted({str(r.get("ip")) for r in rows if r.get("ip")} | set(item["ips"]))
        per_ip: dict[str, dict[str, Any]] = {}
        for ip in observed_ips:
            ip_rows = [r for r in rows if r.get("ip") == ip]
            ip_ok = [r for r in ip_rows if r.get("success")]
            per_ip[ip] = {
                "samples": len(ip_rows),
                "successes": len(ip_ok),
                "success_rate": round(len(ip_ok) / len(ip_rows), 4) if ip_rows else None,
                **stats([float(r["elapsed_ms"]) for r in ip_ok if r.get("elapsed_ms") is not None], include_tail=deep),
            }
        result = {
            "hostname": candidate["hostname"],
            "incumbent": bool(candidate.get("incumbent")),
            "sources": candidate.get("sources", []),
            "organizations": candidate.get("organizations", []),
            "distance_km": candidate.get("distance_km"),
            "eligibility": candidate.get("eligibility"),
            "front_door": candidate.get("front_door"),
            "protocol_compliance": candidate.get("protocol_compliance"),
            "warnings": list(candidate.get("warnings", [])),
            "review": list(candidate.get("review", [])),
            "hard_rejections": list(candidate.get("hard_rejections", [])),
            "dns": item["dns"],
            "current_ipv4": item["ips"],
            "samples": rows,
            "sample_count": len(rows),
            "reused_samples": item["reused_samples"],
            "new_samples": len(rows) - item["reused_samples"],
            "successes": len(ok),
            "success_rate": round(len(ok) / len(rows), 4) if rows else 0.0,
            "per_ip": per_ip,
            "tls_versions": sorted({str(r.get("tls_version")) for r in ok if r.get("tls_version")}),
            "alpn_protocols": sorted({str(r.get("alpn")) for r in ok if r.get("alpn")}),
            **stats(values, include_tail=deep),
        }
        results.append(result)
    return results



def p50_equivalence_band(value: Any, width_ms: float = 2.0) -> int:
    """Bucket tiny P50 differences so tail/stability can break near-ties."""
    if value is None:
        return 10**9
    width = max(0.5, float(width_ms))
    return int(round(float(value) / width))

def fast_rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
    p50 = row.get("p50_ms") if row.get("p50_ms") is not None else 1e9
    mad = row.get("mad_ms") if row.get("mad_ms") is not None else 1e9
    front = (row.get("front_door") or {}).get("class", "UNKNOWN")
    return (
        policy_priority(row.get("eligibility")),
        -float(row.get("success_rate") or 0.0),
        p50_equivalence_band(p50),
        float(mad),
        float(p50),
        edge_priority(front),
        source_priority(row.get("sources") or []),
        row["hostname"],
    )


def _tail_risk_bucket(p50: Any, p95: Any) -> int:
    if p50 is None or p95 is None:
        return 9
    spread = max(0.0, float(p95) - float(p50))
    if spread <= 10.0:
        return 0
    if spread <= 20.0:
        return 1
    if spread <= 35.0:
        return 2
    return 3


def deep_rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
    p50 = row.get("p50_ms") if row.get("p50_ms") is not None else 1e9
    p95 = row.get("p95_ms") if row.get("p95_ms") is not None else 1e9
    mad = row.get("mad_ms") if row.get("mad_ms") is not None else 1e9
    front = (row.get("front_door") or {}).get("class", "UNKNOWN")
    inconsistent = any(
        (v.get("success_rate") or 0.0) < 0.9
        for v in (row.get("per_ip") or {}).values()
        if (v.get("samples") or 0) >= 3
    )
    affinity = row.get("network_affinity") or {}
    return (
        policy_priority(row.get("eligibility")),
        -float(row.get("success_rate") or 0.0),
        p50_equivalence_band(p50),
        _tail_risk_bucket(p50, p95),
        int(affinity.get("rank", 9)),
        float(p95),
        float(mad),
        float(p50),
        int(inconsistent),
        edge_priority(front),
        source_priority(row.get("sources") or []),
        row["hostname"],
    )


def apply_deep_policy(row: dict[str, Any], incumbent: bool = False) -> dict[str, Any]:
    hard = set(row.get("hard_rejections") or [])
    successful = [sample for sample in (row.get("samples") or []) if sample.get("success")]
    if successful and any(sample.get("tls_version") != "TLSv1.3" for sample in successful):
        hard.add("HARD:REALITY_MIN_TLS13")
    if successful and any(sample.get("alpn") != "h2" for sample in successful):
        hard.add("HARD:REALITY_MIN_H2")
    if not incumbent:
        if (row.get("success_rate") or 0.0) < 0.95:
            hard.add("HARD:TLS_SUCCESS_LT_95")
        bad_ip = False
        for info in (row.get("per_ip") or {}).values():
            if (info.get("samples") or 0) >= 3 and (info.get("success_rate") or 0.0) < 0.90:
                bad_ip = True
        if bad_ip:
            hard.add("HARD:IP_SUCCESS_LT_90")
    row = dict(row)
    row["hard_rejections"] = sorted(hard)
    protocol = dict(row.get("protocol_compliance") or {})
    protocol_failures = sorted(set(protocol.get("hard_failures") or []) | (hard & PROTOCOL_HARD_CODES))
    if protocol_failures:
        protocol["state"] = "FAIL"
        protocol["hard_failures"] = protocol_failures
    if successful:
        protocol["tls13"] = all(sample.get("tls_version") == "TLSv1.3" for sample in successful)
        protocol["h2"] = all(sample.get("alpn") == "h2" for sample in successful)
    row["protocol_compliance"] = protocol
    row["eligibility"] = "BASELINE_ONLY" if incumbent and hard else "HARD_REJECTED" if hard else row.get("eligibility", "ELIGIBLE")
    return row
