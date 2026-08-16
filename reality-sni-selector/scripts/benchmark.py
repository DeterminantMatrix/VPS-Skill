#!/usr/bin/env python3
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from common import edge_priority, source_priority, stats
from target_probe import resolve_ipv4_observations, tls_probe_ip


def benchmark_candidates(candidates: list[dict[str, Any]], *, samples: int, timeout: float = 5.0, deep: bool = False) -> list[dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        host = candidate["hostname"]
        dns = resolve_ipv4_observations(host, observations=3 if deep else 2)
        ips = dns["common_ipv4"] or candidate.get("current_ipv4") or candidate.get("initial_ipv4") or []
        state[host] = {"candidate": candidate, "dns": dns, "ips": ips, "samples": []}

    # Interleave candidates by rounds. Each candidate gets exactly `samples` total samples,
    # balanced deterministically across its common IPv4 set.
    for round_no in range(samples):
        for candidate in candidates:
            host = candidate["hostname"]
            item = state[host]
            ips = item["ips"]
            if not ips:
                item["samples"].append({"success": False, "ip": None, "error": "NO_IPV4", "elapsed_ms": None})
                continue
            ip = ips[round_no % len(ips)]
            row = tls_probe_ip(host, ip, timeout=timeout)
            row["round"] = round_no + 1
            item["samples"].append(row)
            time.sleep(0.03)

    results: list[dict[str, Any]] = []
    for candidate in candidates:
        item = state[candidate["hostname"]]
        rows = item["samples"]
        ok = [r for r in rows if r.get("success")]
        values = [float(r["elapsed_ms"]) for r in ok if r.get("elapsed_ms") is not None]
        per_ip: dict[str, dict[str, Any]] = {}
        for ip in item["ips"]:
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
            "eligibility": candidate.get("eligibility"),
            "front_door": candidate.get("front_door"),
            "warnings": list(candidate.get("warnings", [])),
            "review": list(candidate.get("review", [])),
            "hard_rejections": list(candidate.get("hard_rejections", [])),
            "dns": item["dns"],
            "current_ipv4": item["ips"],
            "samples": rows,
            "sample_count": len(rows),
            "successes": len(ok),
            "success_rate": round(len(ok) / len(rows), 4) if rows else 0.0,
            "per_ip": per_ip,
            **stats(values, include_tail=deep),
        }
        results.append(result)
    return results


def fast_rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
    p50 = row.get("p50_ms") if row.get("p50_ms") is not None else 1e9
    mad = row.get("mad_ms") if row.get("mad_ms") is not None else 1e9
    front = (row.get("front_door") or {}).get("class", "UNKNOWN")
    return (-float(row.get("success_rate") or 0.0), float(p50), float(mad), edge_priority(front), source_priority(row.get("sources") or []), row["hostname"])


def deep_rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
    p50 = row.get("p50_ms") if row.get("p50_ms") is not None else 1e9
    p95 = row.get("p95_ms") if row.get("p95_ms") is not None else 1e9
    mad = row.get("mad_ms") if row.get("mad_ms") is not None else 1e9
    front = (row.get("front_door") or {}).get("class", "UNKNOWN")
    inconsistent = any((v.get("success_rate") or 0.0) < 0.9 for v in (row.get("per_ip") or {}).values() if (v.get("samples") or 0) >= 3)
    return (-float(row.get("success_rate") or 0.0), float(p50), float(p95), float(mad), int(inconsistent), edge_priority(front),
            -int(bool(row.get("exact_target_asn"))), source_priority(row.get("sources") or []), row["hostname"])


def apply_deep_policy(row: dict[str, Any], incumbent: bool = False) -> dict[str, Any]:
    hard = set(row.get("hard_rejections") or [])
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
    row["eligibility"] = "BASELINE_ONLY" if incumbent and hard else "HARD_REJECTED" if hard else row.get("eligibility", "ELIGIBLE")
    return row
