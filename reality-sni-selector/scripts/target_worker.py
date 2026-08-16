#!/usr/bin/env python3
"""Fixed target-side worker for target-measured Reality SNI selection.

Install deliberately on an owned VPS and expose it as `reality-sni-target-worker`.
Normal controller runs invoke only `reality-sni-target-worker run` and pass a frozen
JSON job on stdin.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from benchmark import apply_deep_policy, benchmark_candidates, deep_rank_key, fast_rank_key
from common import edge_priority, fetch_bytes, fetch_json, read_json_stdin, source_priority, validate_hostname
from reality_selftest import environment as reality_environment
from reality_selftest import run_candidate
from target_discovery import discover
from target_probe import gate_candidate, resolve_ipv4_observations

ABSOLUTE_LIMITS = {
    "source_pool_cap": 1200,
    "discovered_cap": 600,
    "eligibility_pool": 120,
    "fast_pool": 50,
    "deep_pool": 10,
    "top_n": 5,
    "fast_samples": 10,
    "deep_samples": 30,
    "reality_attempts": 5,
    "ct_base_cap": 60,
    "ct_max_per_domain": 30,
    "dns_workers": 16,
}


def validate_job(job: Any) -> dict[str, Any]:
    if not isinstance(job, dict) or job.get("schema_version") != 3 or job.get("profile_name") != "target-measured-v3":
        raise ValueError("unsupported job schema/profile")
    if job.get("port") != 443:
        raise ValueError("only TCP/443 is permitted")
    target = job.get("target")
    if not isinstance(target, dict) or not target.get("alias") or not target.get("inventory_ipv4"):
        raise ValueError("missing target identity")
    incumbent_mode = str(job.get("incumbent_mode") or "explicit")
    if incumbent_mode not in {"explicit", "auto"}:
        raise ValueError("invalid incumbent mode")
    if incumbent_mode == "explicit":
        job["incumbent"] = validate_hostname(str(job.get("incumbent") or ""))
    else:
        job["incumbent"] = None
    seeds = job.get("seed_domains")
    if not isinstance(seeds, list):
        raise ValueError("invalid seed domains")
    if len(seeds) > ABSOLUTE_LIMITS["source_pool_cap"]:
        raise ValueError("seed list too large")
    job["seed_domains"] = [validate_hostname(str(v)) for v in seeds]
    limits = job.get("limits")
    if not isinstance(limits, dict):
        raise ValueError("missing limits")
    for key, ceiling in ABSOLUTE_LIMITS.items():
        value = limits.get(key)
        if not isinstance(value, int) or value <= 0 or value > ceiling:
            raise ValueError(f"invalid/unsafe limit: {key}")
    if limits["reality_attempts"] != 5:
        raise ValueError("Reality attempts are fixed at five")
    profile = job.get("profile")
    if not isinstance(profile, dict):
        raise ValueError("missing profile")
    if not (1 <= int(profile.get("primary_radius_km", 0)) <= 75):
        raise ValueError("invalid primary radius")
    if not (1 <= int(profile.get("expanded_radius_km", 0)) <= 150):
        raise ValueError("invalid expanded radius")
    if int(profile.get("ct_failure_budget", 0)) != 3:
        raise ValueError("CT failure budget must remain fixed")
    latency = float(profile.get("latency_target_ms", 0))
    if not (1 <= latency <= 1000):
        raise ValueError("invalid latency target")
    return job


AUTO_CONFIG_FILES = [
    Path("/etc/sing-box/config.json"),
    Path("/etc/sing-box/config.jsonc"),
    Path("/usr/local/etc/sing-box/config.json"),
    Path("/usr/local/etc/sing-box/config.jsonc"),
    Path("/opt/sing-box/config.json"),
]
AUTO_CONFIG_DIRS = [Path("/etc/sing-box/conf.d"), Path("/etc/sing-box/config.d")]


def _strip_json_comments(text: str) -> str:
    out = []
    i = 0
    in_string = False
    escape = False
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and nxt == "/":
            i += 2
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue
        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _extract_reality_targets(value: Any, found: set[str]) -> None:
    if isinstance(value, dict):
        tls = value.get("tls")
        if isinstance(tls, dict):
            reality = tls.get("reality")
            if isinstance(reality, dict):
                handshake = reality.get("handshake")
                candidate = None
                if isinstance(handshake, dict):
                    candidate = handshake.get("server")
                if isinstance(candidate, str):
                    try:
                        found.add(validate_hostname(candidate))
                    except ValueError:
                        server_name = tls.get("server_name")
                        if isinstance(server_name, str):
                            try:
                                found.add(validate_hostname(server_name))
                            except ValueError:
                                pass
        for child in value.values():
            _extract_reality_targets(child, found)
    elif isinstance(value, list):
        for child in value:
            _extract_reality_targets(child, found)


def resolve_auto_incumbent() -> tuple[str | None, str | None]:
    paths = list(AUTO_CONFIG_FILES)
    for directory in AUTO_CONFIG_DIRS:
        if directory.is_dir():
            paths.extend(sorted(list(directory.glob("*.json")) + list(directory.glob("*.jsonc")))[:32])
    found: set[str] = set()
    readable = 0
    for path in paths:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
            data = json.loads(_strip_json_comments(text))
            readable += 1
            _extract_reality_targets(data, found)
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
    if len(found) == 1:
        return next(iter(found)), None
    if len(found) > 1:
        return None, "AUTO_INCUMBENT_AMBIGUOUS"
    return None, "AUTO_INCUMBENT_UNAVAILABLE" if readable else "AUTO_INCUMBENT_CONFIG_UNREADABLE"


def _tool_version(command: str) -> str | None:
    path = shutil.which(command)
    if not path:
        return None
    try:
        proc = subprocess.run([path, "version" if command == "sing-box" else "--version"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=5, check=False)
        lines = (proc.stdout or proc.stderr or "").splitlines()
        return lines[0][:200] if lines else path
    except Exception:
        return path


def preflight(job: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "observed_egress_ip": None,
        "location": None,
        "region_mismatch": False,
        "tools": {
            "python3": shutil.which("python3"),
            "curl": shutil.which("curl"),
            "dig": shutil.which("dig"),
            "sing_box": shutil.which("sing-box"),
            "sing_box_version": _tool_version("sing-box"),
        },
        "warnings": [],
    }
    try:
        raw = fetch_bytes("https://api.ipify.org", timeout=6, max_bytes=128)
        ip = raw.decode("ascii", errors="ignore").strip()
        out["observed_egress_ip"] = ip or None
    except Exception:
        out["warnings"].append("TARGET_EGRESS_UNAVAILABLE")
        return out

    ip = out["observed_egress_ip"]
    loc = None
    try:
        data = fetch_json(f"https://ipwho.is/{ip}", timeout=7, max_bytes=250_000)
        if isinstance(data, dict) and data.get("success", True):
            conn = data.get("connection") if isinstance(data.get("connection"), dict) else {}
            loc = {
                "country": data.get("country"),
                "country_code": data.get("country_code"),
                "region": data.get("region"),
                "city": data.get("city"),
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
                "asn": conn.get("asn"),
                "organization": conn.get("org") or conn.get("isp"),
                "source": "ipwho.is",
            }
    except Exception:
        pass
    if not loc:
        try:
            data = fetch_json(f"https://ipapi.co/{ip}/json/", timeout=7, max_bytes=250_000)
            if isinstance(data, dict) and not data.get("error"):
                loc = {
                    "country": data.get("country_name"),
                    "country_code": data.get("country_code"),
                    "region": data.get("region"),
                    "city": data.get("city"),
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "asn": data.get("asn"),
                    "organization": data.get("org"),
                    "source": "ipapi.co",
                }
        except Exception:
            pass
    out["location"] = loc
    if not loc or not isinstance(loc.get("latitude"), (int, float)) or not isinstance(loc.get("longitude"), (int, float)):
        out["warnings"].append("LOCATION_DEGRADED")
    declared = str(job.get("region") or "").upper()
    observed = str((loc or {}).get("country_code") or "").upper()
    if len(declared) == 2 and len(observed) == 2 and declared != observed:
        out["region_mismatch"] = True
        out["warnings"].append("REGION_MISMATCH_REVIEW")
    return out


def select_probe_pool(candidates: list[dict[str, Any]], incumbent: str, limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(candidates, key=lambda r: (0 if r["hostname"] == incumbent else 1, source_priority(r.get("sources") or []), r["hostname"]))
    selected = []
    deferred = []
    for rec in ordered:
        item = dict(rec)
        item["incumbent"] = rec["hostname"] == incumbent
        if len(selected) < limit:
            item["execution"] = "PROBED"
            selected.append(item)
        else:
            item["execution"] = "DEFERRED_BUDGET"
            item["status_code"] = "DEFERRED:PROBE_BUDGET"
            deferred.append(item)
    return selected, deferred


def gate_selection_key(row: dict[str, Any]) -> tuple[Any, ...]:
    successful = [r for r in row.get("tls", []) if r.get("success") and r.get("elapsed_ms") is not None]
    p50_like = sorted(float(r["elapsed_ms"]) for r in successful)
    coarse = p50_like[len(p50_like) // 2] if p50_like else 1e9
    front = (row.get("front_door") or {}).get("class", "UNKNOWN")
    return (0 if row.get("incumbent") else 1, 0 if not row.get("hard_rejections") else 1,
            edge_priority(front), float(coarse), source_priority(row.get("sources") or []), row["hostname"])


def _candidate_asn(ip: str) -> dict[str, Any] | None:
    try:
        data = fetch_json(f"https://ipwho.is/{ip}", timeout=6, max_bytes=200_000)
        if not isinstance(data, dict) or not data.get("success", True):
            return None
        conn = data.get("connection") if isinstance(data.get("connection"), dict) else {}
        return {"ip": ip, "asn": conn.get("asn"), "organization": conn.get("org") or conn.get("isp")}
    except Exception:
        return None


def enrich_deep_asn(rows: list[dict[str, Any]], target_asn: Any) -> None:
    for row in rows:
        ips = row.get("current_ipv4") or []
        evidence = _candidate_asn(ips[0]) if ips else None
        row["asn_evidence"] = evidence
        row["exact_target_asn"] = bool(evidence and target_asn and str(evidence.get("asn")) == str(target_asn))


def _rejection_rows(eligibility: list[dict[str, Any]], deep: list[dict[str, Any]], reality: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for stage, items in (("eligibility", eligibility), ("deep_benchmark", deep)):
        for item in items:
            for code in item.get("hard_rejections") or []:
                key = (item["hostname"], stage, code)
                if key not in seen:
                    seen.add(key)
                    rows.append({"hostname": item["hostname"], "stage": stage, "class": "HARD", "code": code})
            for code in item.get("review") or []:
                key = (item["hostname"], stage, code)
                if key not in seen:
                    seen.add(key)
                    rows.append({"hostname": item["hostname"], "stage": stage, "class": "REVIEW", "code": code})
    for item in reality.get("candidates", []):
        if not item.get("passed"):
            code = item.get("code") or "HARD:REALITY_FAILED"
            key = (item.get("hostname"), "reality", code)
            if key not in seen:
                rows.append({"hostname": item.get("hostname"), "stage": "reality", "class": "HARD" if code.startswith("HARD:") else "ERROR", "code": code})
    return rows


def run(job: dict[str, Any]) -> dict[str, Any]:
    pre = preflight(job)
    warnings = list(pre.get("warnings") or [])
    errors: list[str] = []
    if job.get("incumbent_mode") == "auto":
        resolved, incumbent_error = resolve_auto_incumbent()
        if incumbent_error:
            return {
                "schema_version": 3, "status": incumbent_error, "frozen_run": job, "preflight": pre,
                "regional_candidates": {}, "candidates": [], "probe_pool": [], "eligibility": [], "fast_benchmark": [],
                "deep_benchmark": [], "reality": {}, "preliminary_top5": [], "top5": [], "rejections": [],
                "warnings": warnings, "errors": [incumbent_error], "counts": {},
            }
        job = dict(job)
        job["incumbent"] = resolved
        job["resolved_incumbent_at"] = pre.get("observed_egress_ip") and "before_candidate_evaluation"
        if resolved not in job["seed_domains"]:
            job["seed_domains"] = list(job["seed_domains"]) + [resolved]
    if not pre.get("observed_egress_ip"):
        return {
            "schema_version": 3, "status": "TARGET_EGRESS_UNAVAILABLE", "frozen_run": job, "preflight": pre,
            "regional_candidates": {}, "candidates": [], "probe_pool": [], "eligibility": [], "fast_benchmark": [],
            "deep_benchmark": [], "reality": {}, "preliminary_top5": [], "top5": [], "rejections": [],
            "warnings": warnings, "errors": ["TARGET_EGRESS_UNAVAILABLE"], "counts": {},
        }

    discovery = discover(job, pre)
    warnings.extend(discovery.get("errors") or [])
    candidates = discovery["validated"]
    pool, deferred = select_probe_pool(candidates, job["incumbent"], job["limits"]["eligibility_pool"])

    eligibility = []
    for candidate in pool:
        row = gate_candidate(candidate, dns_observations=2, tls_samples_per_ip=2, timeout=5.0)
        if row.get("incumbent") and row.get("hard_rejections"):
            row["eligibility"] = "BASELINE_ONLY"
        eligibility.append(row)

    benchmarkable = [r for r in eligibility if not r.get("hard_rejections") or r.get("incumbent")]
    benchmarkable.sort(key=gate_selection_key)
    fast_input = benchmarkable[: job["limits"]["fast_pool"]]
    fast = benchmark_candidates(fast_input, samples=job["limits"]["fast_samples"], timeout=5.0, deep=False)
    fast.sort(key=fast_rank_key)

    incumbent_fast = next((r for r in fast if r.get("incumbent")), None)
    non_inc = [r for r in fast if not r.get("incumbent")]
    deep_seed = []
    if incumbent_fast:
        deep_seed.append(incumbent_fast)
    deep_seed.extend(non_inc[: max(0, job["limits"]["deep_pool"] - len(deep_seed))])

    deep = benchmark_candidates(deep_seed, samples=job["limits"]["deep_samples"], timeout=5.0, deep=True)
    deep = [apply_deep_policy(r, incumbent=bool(r.get("incumbent"))) for r in deep]
    target_asn = (pre.get("location") or {}).get("asn")
    enrich_deep_asn(deep, target_asn)
    deep.sort(key=deep_rank_key)

    prelim = [r for r in deep if not r.get("incumbent") and not r.get("hard_rejections")]
    prelim = prelim[: job["limits"]["top_n"]]

    reality_env = reality_environment()
    reality: dict[str, Any] = {"environment": reality_env, "status": "NOT_RUN", "control": None, "candidates": []}
    final_top: list[dict[str, Any]] = []
    status = "SUCCESS"

    if not prelim:
        reality["status"] = "NOT_RUN_NO_DEEP_SURVIVORS"
        status = "NO_DEEP_SURVIVORS"
    elif not reality_env.get("ready"):
        reality["status"] = "UNAVAILABLE"
        warnings.append(f"REALITY_UNAVAILABLE:{reality_env.get('reason')}")
        status = "PARTIAL_REALITY_UNAVAILABLE"
    else:
        incumbent_gate = next((r for r in eligibility if r["hostname"] == job["incumbent"]), None)
        incumbent_ips = (incumbent_gate or {}).get("current_ipv4") or (incumbent_gate or {}).get("initial_ipv4") or []
        if not incumbent_ips:
            incumbent_ips = resolve_ipv4_observations(job["incumbent"], observations=2).get("common_ipv4") or []
        control = run_candidate(job["incumbent"], incumbent_ips, attempts=1, env=reality_env)
        reality["control"] = control
        if not control.get("passed"):
            reality["status"] = "INVALID:REALITY_CONTROL_FAILED"
            status = "INVALID_REALITY_CONTROL"
        else:
            reality["status"] = "RUNNING"
            incumbent_deep = next((r for r in deep if r.get("incumbent")), None)
            incumbent_p50 = incumbent_deep.get("p50_ms") if incumbent_deep else None
            for row in prelim:
                test = run_candidate(row["hostname"], row.get("current_ipv4") or [], attempts=job["limits"]["reality_attempts"], env=reality_env)
                reality["candidates"].append(test)
                if test.get("dirty"):
                    reality["status"] = "TARGET_DIRTY_STATE"
                    status = "TARGET_DIRTY_STATE"
                    errors.append("TARGET_DIRTY_STATE")
                    break
                if test.get("passed"):
                    final = dict(row)
                    final["reality"] = test
                    final["final"] = "REVIEW_REQUIRED" if row.get("eligibility") == "REVIEW_REQUIRED" else "SELECTABLE"
                    if incumbent_p50 and row.get("p50_ms") is not None and incumbent_p50 > 0:
                        final["incumbent_p50_improvement_pct"] = round((incumbent_p50 - row["p50_ms"]) / incumbent_p50 * 100.0, 2)
                    else:
                        final["incumbent_p50_improvement_pct"] = None
                    if row.get("p50_ms") is not None and row["p50_ms"] > float(job["profile"]["latency_target_ms"]):
                        final.setdefault("warnings", []).append("TARGET:P50_ABOVE_GOAL")
                    final_top.append(final)
            if status != "TARGET_DIRTY_STATE":
                reality["status"] = "COMPLETE"
                if not final_top:
                    status = "NO_REALITY_SURVIVORS"
                elif any(r.get("final") == "REVIEW_REQUIRED" for r in final_top):
                    status = "SUCCESS_WITH_REVIEW"

    hard_rejected = sum(1 for r in eligibility if r.get("hard_rejections") and not r.get("incumbent"))
    review_required = sum(1 for r in eligibility if not r.get("hard_rejections") and r.get("review"))
    counts = {
        "discovered": len(candidates),
        "eligibility_selected": len(pool),
        "deferred_budget": len(deferred),
        "hard_rejected": hard_rejected,
        "review_required": review_required,
        "fast_benchmarked": len(fast),
        "deep_benchmarked": len(deep),
        "reality_tested": len(reality.get("candidates") or []),
        "selectable": sum(1 for r in final_top if r.get("final") == "SELECTABLE"),
    }
    rejections = _rejection_rows(eligibility, deep, reality)
    return {
        "schema_version": 3,
        "status": status,
        "frozen_run": job,
        "preflight": pre,
        "regional_candidates": {"coverage": discovery.get("coverage"), "counts": discovery.get("counts"), "errors": discovery.get("errors"), "source_records": discovery.get("source_records")},
        "candidates": candidates,
        "probe_pool": pool + deferred,
        "eligibility": eligibility,
        "fast_benchmark": fast,
        "deep_benchmark": deep,
        "reality": reality,
        "preliminary_top5": prelim,
        "top5": final_top[: job["limits"]["top_n"]],
        "rejections": rejections,
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
        "counts": counts,
    }


def main() -> int:
    if sys.argv[1:] != ["run"]:
        print(json.dumps({"status": "BLOCKED", "reason": "FIXED_COMMAND_REQUIRED"}))
        return 2
    try:
        job = validate_job(read_json_stdin())
        result = run(job)
    except Exception as exc:
        result = {"schema_version": 3, "status": "WORKER_FAILED", "reason": type(exc).__name__, "top5": [], "preliminary_top5": []}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    sys.stdout.write("\n")
    return 0 if result.get("status") not in {"WORKER_FAILED", "TARGET_DIRTY_STATE", "TARGET_EGRESS_UNAVAILABLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
