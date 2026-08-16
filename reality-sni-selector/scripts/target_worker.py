#!/usr/bin/env python3
"""Fixed target-side worker for target-measured Reality SNI selection v4."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from benchmark import apply_deep_policy, benchmark_candidates, deep_rank_key, fast_rank_key
from common import (
    IMPLEMENTATION_VERSION,
    JOB_SCHEMA_VERSION,
    PROFILE_NAME,
    WORKER_PROTOCOL,
    compute_worker_manifest,
    edge_priority,
    fetch_bytes,
    fetch_json,
    policy_priority,
    read_json_stdin,
    registrable_domain,
    source_priority,
    validate_hostname,
)
from reality_selftest import environment as reality_environment
from reality_selftest import find_sing_box, run_candidate
from target_discovery import discover
from target_probe import classify_network_organization, gate_candidate, resolve_ipv4_observations

ABSOLUTE_LIMITS = {
    "source_pool_cap": 1200,
    "discovered_cap": 600,
    "eligibility_pool": 120,
    "fast_pool": 50,
    "deep_pool": 10,
    "top_n": 5,
    "comparison_min_domains": 10,
    "fast_samples": 10,
    "deep_samples": 30,
    "reality_attempts": 5,
    "reality_candidate_cap": 10,
    "selectable_target": 5,
    "ct_base_cap": 60,
    "ct_max_per_domain": 30,
    "dns_workers": 16,
    "ip_metadata_budget": 256,
}

FIXED_CONFIG_FILES = [
    Path("/etc/sing-box/config.json"),
    Path("/etc/sing-box/config.jsonc"),
    Path("/usr/local/etc/sing-box/config.json"),
    Path("/usr/local/etc/sing-box/config.jsonc"),
    Path("/opt/sing-box/config.json"),
    Path("/opt/sing-box/config.jsonc"),
]
FIXED_CONFIG_DIRS = [Path("/etc/sing-box/conf.d"), Path("/etc/sing-box/config.d")]
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def worker_identity() -> dict[str, Any]:
    directory = Path(__file__).resolve().parent
    return {
        "protocol": WORKER_PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "manifest": compute_worker_manifest(directory),
        "profile": PROFILE_NAME,
    }


def validate_job(job: Any) -> dict[str, Any]:
    if not isinstance(job, dict):
        raise ValueError("job must be an object")
    if job.get("schema_version") != JOB_SCHEMA_VERSION or job.get("profile_name") != PROFILE_NAME:
        raise ValueError("unsupported job schema/profile")
    if job.get("worker_protocol") != WORKER_PROTOCOL:
        raise ValueError("unsupported worker protocol")
    if job.get("implementation_version") != IMPLEMENTATION_VERSION:
        raise ValueError("unsupported implementation version")
    expected = str(job.get("expected_worker_manifest") or "")
    if not HEX64_RE.fullmatch(expected):
        raise ValueError("invalid expected worker manifest")
    if job.get("port") != 443:
        raise ValueError("only TCP/443 is permitted")
    target = job.get("target")
    if not isinstance(target, dict) or not target.get("inventory_id") or not target.get("alias") or not target.get("inventory_ipv4"):
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
    if limits["comparison_min_domains"] < 5:
        raise ValueError("comparison must target at least five domains")
    if limits["reality_candidate_cap"] < limits["selectable_target"]:
        raise ValueError("Reality candidate cap cannot be smaller than selectable target")
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
    if profile.get("strict_shared_edge") is not True:
        raise ValueError("strict shared-edge policy must remain enabled")
    if profile.get("run_mode") not in {"quick", "audit"}:
        raise ValueError("invalid run mode")
    stop_target = int(profile.get("source_stop_target", 0))
    if not (1 <= stop_target <= limits["source_pool_cap"] <= ABSOLUTE_LIMITS["source_pool_cap"]):
        raise ValueError("invalid source stop target")
    if not isinstance(profile.get("adaptive_gate"), bool):
        raise ValueError("adaptive_gate must be boolean")
    return job


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
                candidate = handshake.get("server") if isinstance(handshake, dict) else None
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


def _config_files_from_directory(directory: Path, cap: int = 64) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(list(directory.glob("*.json")) + list(directory.glob("*.jsonc")))[:cap]


def _parse_sing_box_config_args(argv: list[str], cwd: Path) -> list[Path]:
    """Resolve only sing-box global -c/-C/-D config arguments without executing shell."""
    working = cwd
    for idx, arg in enumerate(argv):
        if arg in {"-D", "--directory"} and idx + 1 < len(argv):
            candidate = Path(argv[idx + 1])
            working = candidate if candidate.is_absolute() else cwd / candidate
        elif arg.startswith("--directory="):
            candidate = Path(arg.split("=", 1)[1])
            working = candidate if candidate.is_absolute() else cwd / candidate
    paths: list[Path] = []
    idx = 0
    while idx < len(argv):
        arg = argv[idx]
        value: str | None = None
        mode: str | None = None
        if arg in {"-c", "--config"} and idx + 1 < len(argv):
            value, mode = argv[idx + 1], "file"
            idx += 1
        elif arg.startswith("--config="):
            value, mode = arg.split("=", 1)[1], "file"
        elif arg in {"-C", "--config-directory"} and idx + 1 < len(argv):
            value, mode = argv[idx + 1], "dir"
            idx += 1
        elif arg.startswith("--config-directory="):
            value, mode = arg.split("=", 1)[1], "dir"
        if value:
            candidate = Path(value)
            candidate = candidate if candidate.is_absolute() else working / candidate
            if mode == "file":
                paths.append(candidate)
            else:
                paths.extend(_config_files_from_directory(candidate))
        idx += 1
    if not paths:
        for name in ("config.json", "config.jsonc"):
            candidate = working / name
            if candidate.is_file():
                paths.append(candidate)
    return paths


def _live_sing_box_config_paths(proc_root: Path = Path("/proc")) -> list[Path]:
    paths: list[Path] = []
    try:
        entries = list(proc_root.iterdir())
    except OSError:
        return []
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            exe = os.path.realpath(entry / "exe")
            if os.path.basename(exe) != "sing-box":
                continue
            raw = (entry / "cmdline").read_bytes()
            argv = [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]
            if not argv:
                continue
            cwd = Path(os.path.realpath(entry / "cwd"))
            paths.extend(_parse_sing_box_config_args(argv, cwd))
        except (OSError, ValueError):
            continue
    dedup: list[Path] = []
    seen = set()
    for path in paths:
        real = os.path.realpath(path)
        if real not in seen:
            seen.add(real)
            dedup.append(Path(real))
    return dedup


def _fixed_config_paths() -> list[Path]:
    paths = list(FIXED_CONFIG_FILES)
    for directory in FIXED_CONFIG_DIRS:
        paths.extend(_config_files_from_directory(directory, cap=32))
    return paths


def _resolve_targets_from_paths(paths: list[Path]) -> tuple[set[str], int]:
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
    return found, readable


def resolve_auto_incumbent(proc_root: Path = Path("/proc")) -> tuple[str | None, str | None, dict[str, Any]]:
    live_paths = _live_sing_box_config_paths(proc_root)
    found, readable = _resolve_targets_from_paths(live_paths)
    source = "LIVE_PROCESS_CONFIG" if readable else "FIXED_CONFIG_FALLBACK"
    if not readable:
        fallback_paths = _fixed_config_paths()
        found, readable = _resolve_targets_from_paths(fallback_paths)
    info = {"source": source, "readable_config_count": readable, "candidate_count": len(found)}
    if len(found) == 1:
        return next(iter(found)), None, info
    if len(found) > 1:
        return None, "AUTO_INCUMBENT_AMBIGUOUS", info
    return None, "AUTO_INCUMBENT_UNAVAILABLE" if readable else "AUTO_INCUMBENT_CONFIG_UNREADABLE", info


def _tool_version(command: str) -> str | None:
    path = find_sing_box() if command == "sing-box" else shutil.which(command)
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
            "sing_box": find_sing_box(),
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


class IPMetadataCache:
    def __init__(self, budget: int):
        self.budget = max(0, int(budget))
        self.used = 0
        self.cache: dict[str, dict[str, Any] | None] = {}
        self.errors = 0

    def lookup(self, ip: str) -> dict[str, Any] | None:
        if ip in self.cache:
            return self.cache[ip]
        if self.used >= self.budget:
            return None
        self.used += 1
        try:
            data = fetch_json(f"https://ipwho.is/{ip}", timeout=6, max_bytes=200_000)
            if not isinstance(data, dict) or not data.get("success", True):
                self.cache[ip] = None
                return None
            conn = data.get("connection") if isinstance(data.get("connection"), dict) else {}
            value = {
                "ip": ip,
                "asn": conn.get("asn"),
                "organization": conn.get("org") or conn.get("isp"),
                "country_code": data.get("country_code"),
            }
            self.cache[ip] = value
            return value
        except Exception:
            self.errors += 1
            self.cache[ip] = None
            return None


def _diversity_facts(rec: dict[str, Any]) -> tuple[str, tuple[str, ...], str]:
    try:
        domain = registrable_domain(rec["hostname"])
    except ValueError:
        domain = rec["hostname"]
    ips = tuple(sorted(rec.get("initial_ipv4") or []))
    organizations = rec.get("organizations") or []
    organization = str(organizations[0]).strip().lower() if organizations else ""
    return domain, ips, organization


def select_probe_pool(candidates: list[dict[str, Any]], incumbent: str, limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(
        candidates,
        key=lambda r: (
            0 if r["hostname"] == incumbent else 1,
            source_priority(r.get("sources") or []),
            float(r.get("distance_km")) if r.get("distance_km") is not None else 1e9,
            r["hostname"],
        ),
    )
    selected: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    skipped_for_diversity: set[str] = set()
    seen_domains: set[str] = set()
    seen_ipsets: set[tuple[str, ...]] = set()
    seen_orgs: set[str] = set()

    for rec in ordered:
        if rec["hostname"] == incumbent and len(selected) < limit:
            item = dict(rec)
            item["incumbent"] = True
            item["execution"] = "PROBED"
            item["selection_pass"] = "INCUMBENT"
            selected.append(item)
            domain, ips, org = _diversity_facts(rec)
            seen_domains.add(domain)
            if ips:
                seen_ipsets.add(ips)
            if org:
                seen_orgs.add(org)
        else:
            remaining.append(rec)

    def admit(pass_name: str, predicate) -> None:
        nonlocal remaining
        kept = []
        for rec in remaining:
            if len(selected) >= limit:
                kept.append(rec)
                continue
            domain, ips, org = _diversity_facts(rec)
            if not predicate(domain, ips, org):
                skipped_for_diversity.add(rec["hostname"])
                kept.append(rec)
                continue
            item = dict(rec)
            item["incumbent"] = False
            item["execution"] = "PROBED"
            item["selection_pass"] = pass_name
            selected.append(item)
            seen_domains.add(domain)
            if ips:
                seen_ipsets.add(ips)
            if org:
                seen_orgs.add(org)
        remaining = kept

    admit("DIVERSE", lambda d, ips, org: d not in seen_domains and (not ips or ips not in seen_ipsets) and (not org or org not in seen_orgs))
    admit("RELAXED_DIVERSE", lambda d, ips, org: d not in seen_domains or (ips and ips not in seen_ipsets))
    admit("FILL", lambda d, ips, org: True)

    deferred = []
    for rec in remaining:
        item = dict(rec)
        item["incumbent"] = rec["hostname"] == incumbent
        item["execution"] = "DEFERRED_BUDGET"
        if rec["hostname"] in skipped_for_diversity:
            item["status_code"] = "DEFERRED:DIVERSITY_BUDGET"
        else:
            item["status_code"] = "DEFERRED:PROBE_BUDGET"
        deferred.append(item)
    return selected, deferred


def gate_selection_key(row: dict[str, Any]) -> tuple[Any, ...]:
    successful = [r for r in row.get("tls", []) if r.get("success") and r.get("elapsed_ms") is not None]
    values = sorted(float(r["elapsed_ms"]) for r in successful)
    coarse = values[len(values) // 2] if values else 1e9
    front = (row.get("front_door") or {}).get("class", "UNKNOWN")
    return (
        policy_priority(row.get("eligibility")),
        edge_priority(front),
        float(coarse),
        source_priority(row.get("sources") or []),
        row["hostname"],
    )


def enrich_deep_asn(rows: list[dict[str, Any]], target_asn: Any, metadata: IPMetadataCache) -> None:
    for row in rows:
        ips = row.get("current_ipv4") or []
        evidence = metadata.lookup(ips[0]) if ips else None
        row["asn_evidence"] = evidence
        row["exact_target_asn"] = bool(evidence and target_asn and str(evidence.get("asn")) == str(target_asn))
        network_class, network_name, network_evidence = classify_network_organization(evidence)
        if row.get("incumbent"):
            continue
        if network_class == "SHARED_PLATFORM_CONFIRMED":
            row.setdefault("hard_rejections", []).append("HARD:KNOWN_SHARED_PLATFORM")
            row["hard_rejections"] = sorted(set(row["hard_rejections"]))
            row["eligibility"] = "HARD_REJECTED"
            row["front_door"] = {
                **(row.get("front_door") or {}),
                "class": network_class,
                "platform": network_name,
                "provider": None,
                "evidence": sorted(set((row.get("front_door") or {}).get("evidence", []) + ([network_evidence] if network_evidence else []))),
            }
        elif network_class == "PUBLIC_CDN_CONFIRMED":
            row.setdefault("hard_rejections", []).append("HARD:KNOWN_PUBLIC_CDN")
            row["hard_rejections"] = sorted(set(row["hard_rejections"]))
            row["eligibility"] = "HARD_REJECTED"
            row["front_door"] = {
                **(row.get("front_door") or {}),
                "class": network_class,
                "provider": network_name,
                "platform": None,
                "evidence": sorted(set((row.get("front_door") or {}).get("evidence", []) + ([network_evidence] if network_evidence else []))),
            }


def _run_reality_control(hostname: str, ips: list[str], env: dict[str, Any]) -> dict[str, Any]:
    first = run_candidate(hostname, ips, attempts=1, env=env)
    first["retried"] = False
    if first.get("passed") or first.get("dirty"):
        return first
    retry = run_candidate(hostname, ips, attempts=2, env=env)
    rows = list(first.get("attempts") or []) + list(retry.get("attempts") or [])
    for idx, row in enumerate(rows, 1):
        row["attempt"] = idx
    successes = sum(1 for r in rows if r.get("transport_success"))
    cleanups = sum(1 for r in rows if r.get("cleanup_success"))
    dirty = any(not r.get("cleanup_success") for r in rows)
    passed = len(rows) == 3 and successes >= 2 and cleanups == 3 and not dirty
    failures: dict[str, int] = {}
    for row in rows:
        stage = row.get("failure_stage")
        if stage:
            failures[str(stage)] = failures.get(str(stage), 0) + 1
    return {
        "hostname": hostname,
        "attempts": rows,
        "attempt_count": len(rows),
        "transport_successes": successes,
        "cleanup_successes": cleanups,
        "passed": passed,
        "dirty": dirty,
        "retried": True,
        "code": "OK" if passed else "TARGET_DIRTY_STATE" if dirty else "HARD:REALITY_CONTROL_FAILED",
        "failure_counts": failures,
        "dominant_failure_stage": max(failures, key=failures.get) if failures else None,
    }


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


def _recommendation_state(row: dict[str, Any], reality_by_host: dict[str, dict[str, Any]]) -> tuple[int, str, str]:
    if row.get("incumbent"):
        return 3, "BASELINE", "BASELINE"
    if row.get("hard_rejections"):
        return 6, "EXCLUDED", "POLICY_REJECTED"
    test = reality_by_host.get(row["hostname"])
    if test and test.get("passed"):
        if row.get("eligibility") == "ELIGIBLE":
            return 0, "HIGH", "SELECTABLE"
        return 1, "CAUTION", "REVIEW_REQUIRED"
    if test and not test.get("passed"):
        return 5, "NO", "REALITY_FAILED"
    if row.get("eligibility") == "ELIGIBLE":
        return 2, "PENDING", "NOT_REALITY_TESTED"
    if row.get("eligibility") == "REVIEW_REQUIRED":
        return 4, "LOW", "REVIEW_NOT_REALITY_TESTED"
    return 7, "NO", "RANKED_OUT"


def _reliability_failures(row: dict[str, Any] | None) -> list[str]:
    if not row:
        return ["INCUMBENT_DEEP_MISSING"]
    failures: list[str] = []
    if float(row.get("success_rate") or 0.0) < 0.95:
        failures.append("TLS_SUCCESS_LT_95")
    for ip, info in (row.get("per_ip") or {}).items():
        if (info.get("samples") or 0) >= 3 and float(info.get("success_rate") or 0.0) < 0.90:
            failures.append(f"IP_SUCCESS_LT_90:{ip}")
    return failures


def assess_incumbent(
    incumbent: str,
    incumbent_gate: dict[str, Any] | None,
    incumbent_deep: dict[str, Any] | None,
    control: dict[str, Any] | None,
    selectable: list[dict[str, Any]],
    *,
    latency_target_ms: float,
    coverage_status: str,
) -> dict[str, Any]:
    """Evaluate the current production SNI using the same policy/reliability/Reality evidence."""
    result: dict[str, Any] = {
        "hostname": incumbent,
        "code": "UNABLE_TO_ASSESS",
        "verdict": "暂无法评估",
        "confidence": "LOW",
        "reasons": [],
        "metrics": {},
        "best_alternative": None,
    }
    if not incumbent_gate or not incumbent_deep:
        result["reasons"].append("INCUMBENT_MEASUREMENT_INCOMPLETE")
        return result

    hard = list(incumbent_gate.get("hard_rejections") or [])
    review = list(incumbent_gate.get("review") or [])
    reliability = _reliability_failures(incumbent_deep)
    result["metrics"] = {
        "policy_state": incumbent_gate.get("eligibility"),
        "hard_rejections": hard,
        "review": review,
        "success_rate": incumbent_deep.get("success_rate"),
        "p50_ms": incumbent_deep.get("p50_ms"),
        "p95_ms": incumbent_deep.get("p95_ms"),
        "mad_ms": incumbent_deep.get("mad_ms"),
        "reality_control": "PASS" if control and control.get("passed") else "FAIL" if control else "NOT_RUN",
        "reality_control_retried": bool(control and control.get("retried")),
    }

    if hard:
        result.update(code="REPLACE_REQUIRED", verdict="需要更换", confidence="HIGH")
        result["reasons"].append("CURRENT_SNI_POLICY_HARD_REJECT")
        result["reasons"].extend(hard)
        return result
    if reliability:
        result.update(code="REPLACE_REQUIRED", verdict="需要更换", confidence="HIGH")
        result["reasons"].append("CURRENT_SNI_RELIABILITY_BELOW_GATE")
        result["reasons"].extend(reliability)
        return result
    if control and control.get("dirty"):
        result["reasons"].append("REALITY_CONTROL_CLEANUP_UNCERTAIN")
        return result
    if control and not control.get("passed"):
        result.update(code="REPLACE_REQUIRED", verdict="需要更换", confidence="MEDIUM")
        result["reasons"].append("CURRENT_SNI_REALITY_CONTROL_FAILED")
        return result
    if not control:
        result["reasons"].append("REALITY_CONTROL_NOT_AVAILABLE")
        return result

    best = min(
        (r for r in selectable if r.get("p50_ms") is not None),
        key=lambda r: float(r["p50_ms"]),
        default=None,
    )
    p50_imp = None
    p95_imp = None
    if best and incumbent_deep.get("p50_ms") and float(incumbent_deep["p50_ms"]) > 0:
        p50_imp = round((float(incumbent_deep["p50_ms"]) - float(best["p50_ms"])) / float(incumbent_deep["p50_ms"]) * 100.0, 2)
    if best and incumbent_deep.get("p95_ms") and best.get("p95_ms") is not None and float(incumbent_deep["p95_ms"]) > 0:
        p95_imp = round((float(incumbent_deep["p95_ms"]) - float(best["p95_ms"])) / float(incumbent_deep["p95_ms"]) * 100.0, 2)
    if best:
        result["best_alternative"] = {
            "hostname": best.get("hostname"),
            "p50_ms": best.get("p50_ms"),
            "p95_ms": best.get("p95_ms"),
            "p50_improvement_pct": p50_imp,
            "p95_improvement_pct": p95_imp,
        }

    transient = bool(control.get("retried"))
    incumbent_p50 = incumbent_deep.get("p50_ms")
    decisive_alt = bool(
        p50_imp is not None and p50_imp >= 30.0 and
        (p95_imp is None or p95_imp >= 15.0)
    )
    above_target_with_alt = bool(
        incumbent_p50 is not None and float(incumbent_p50) > latency_target_ms and
        p50_imp is not None and p50_imp >= 20.0
    )

    if decisive_alt or above_target_with_alt:
        result.update(code="REPLACE_RECOMMENDED", verdict="建议更换", confidence="HIGH" if coverage_status == "GOOD" else "MEDIUM")
        result["reasons"].append("SELECTABLE_ALTERNATIVE_MATERIALLY_FASTER")
    elif review or transient:
        result.update(code="KEEP_WITH_REVIEW", verdict="暂可继续使用，建议复核", confidence="MEDIUM")
        if review:
            result["reasons"].append("CURRENT_SNI_HAS_REVIEW_SIGNALS")
            result["reasons"].extend(review)
        if transient:
            result["reasons"].append("REALITY_CONTROL_REQUIRED_RETRY")
    elif (p50_imp is not None and p50_imp >= 15.0) or (incumbent_p50 is not None and float(incumbent_p50) > latency_target_ms):
        result.update(code="KEEP_OPTIMIZABLE", verdict="可继续使用，但有优化空间", confidence="HIGH" if coverage_status == "GOOD" else "MEDIUM")
        result["reasons"].append("CURRENT_SNI_SAFE_BUT_NOT_PERFORMANCE_OPTIMAL")
    else:
        result.update(code="KEEP", verdict="继续使用", confidence="HIGH" if coverage_status == "GOOD" else "MEDIUM")
        result["reasons"].append("CURRENT_SNI_PASSES_POLICY_RELIABILITY_AND_REALITY")
        if not best:
            result["reasons"].append("NO_BETTER_SELECTABLE_ALTERNATIVE_FOUND")
        elif p50_imp is not None:
            result["reasons"].append("BEST_ALTERNATIVE_IMPROVEMENT_BELOW_REPLACEMENT_THRESHOLD")
    return result


def build_comparison(
    deep: list[dict[str, Any]],
    fast: list[dict[str, Any]],
    reality: dict[str, Any],
    incumbent: str,
    minimum: int,
    incumbent_p50: float | None,
) -> list[dict[str, Any]]:
    reality_by_host = {r.get("hostname"): r for r in reality.get("candidates", []) if r.get("hostname")}
    rows_by_host: dict[str, dict[str, Any]] = {}
    for stage, items in (("DEEP", deep), ("FAST_ONLY", fast)):
        for source in items:
            if source["hostname"] in rows_by_host:
                continue
            row = dict(source)
            row["benchmark_stage"] = stage
            rows_by_host[row["hostname"]] = row
    scored = []
    for row in rows_by_host.values():
        group, level, final_state = _recommendation_state(row, reality_by_host)
        test = reality_by_host.get(row["hostname"])
        row["reality_compatibility"] = "PASS" if test and test.get("passed") else "FAIL" if test else "NOT_TESTED"
        row["reality_summary"] = test
        row["policy_eligibility"] = row.get("eligibility")
        row["final_state"] = final_state
        row["recommendation"] = level
        row["recommendation_group"] = group
        if incumbent_p50 and row.get("p50_ms") is not None and incumbent_p50 > 0:
            row["incumbent_p50_improvement_pct"] = round((incumbent_p50 - float(row["p50_ms"])) / incumbent_p50 * 100.0, 2)
        else:
            row["incumbent_p50_improvement_pct"] = None
        scored.append(row)
    scored.sort(key=lambda r: (
        r["recommendation_group"],
        -float(r.get("success_rate") or 0.0),
        float(r.get("p50_ms")) if r.get("p50_ms") is not None else 1e9,
        float(r.get("p95_ms")) if r.get("p95_ms") is not None else 1e9,
        r["hostname"],
    ))
    desired = max(5, int(minimum))
    chosen = scored[:desired]
    incumbent_row = next((r for r in scored if r["hostname"] == incumbent), None)
    if incumbent_row and all(r["hostname"] != incumbent for r in chosen):
        chosen.append(incumbent_row)
    for rank, row in enumerate(chosen, 1):
        row["recommendation_rank"] = rank
    return chosen


def _empty_result(job: dict[str, Any], identity: dict[str, Any], status: str, *, preflight_data: dict[str, Any] | None = None, warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema_version": JOB_SCHEMA_VERSION,
        "worker": identity,
        "status": status,
        "frozen_run": job,
        "preflight": preflight_data or {},
        "coverage": {},
        "regional_candidates": {},
        "candidates": [],
        "probe_pool": [],
        "eligibility": [],
        "fast_benchmark": [],
        "deep_benchmark": [],
        "reality": {},
        "preliminary_top5": [],
        "top5": [],
        "comparison": [],
        "incumbent_assessment": {"hostname": job.get("incumbent"), "code": "UNABLE_TO_ASSESS", "verdict": "暂无法评估", "confidence": "LOW", "reasons": [status]},
        "rejections": [],
        "warnings": warnings or [],
        "errors": [status],
        "counts": {},
    }


def run(job: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    pre = preflight(job)
    warnings = list(pre.get("warnings") or [])
    errors: list[str] = []

    if job.get("incumbent_mode") == "auto":
        resolved, incumbent_error, incumbent_info = resolve_auto_incumbent()
        if incumbent_error:
            result = _empty_result(job, identity, incumbent_error, preflight_data=pre, warnings=warnings)
            result["incumbent_resolution"] = incumbent_info
            return result
        job = dict(job)
        job["incumbent"] = resolved
        job["incumbent_resolution"] = incumbent_info
        job["resolved_incumbent_at"] = "before_candidate_evaluation"
        if resolved not in job["seed_domains"]:
            job["seed_domains"] = list(job["seed_domains"]) + [resolved]

    if not pre.get("observed_egress_ip"):
        return _empty_result(job, identity, "TARGET_EGRESS_UNAVAILABLE", preflight_data=pre, warnings=warnings)

    discovery = discover(job, pre)
    warnings.extend(discovery.get("errors") or [])
    candidates = discovery["validated"]
    coverage_status = discovery.get("coverage") or "SPARSE"
    run_mode = str(job["profile"].get("run_mode") or "quick")
    coverage = {
        "profile": run_mode,
        "goal": int(job["profile"]["coverage_goal"]),
        "validated": len(candidates),
        "status": coverage_status,
        "selection_maturity": (
            "QUICK_CONFIDENT" if run_mode == "quick" and coverage_status == "GOOD"
            else "AUDIT_MATURE" if run_mode == "audit" and coverage_status == "GOOD"
            else "PROVISIONAL"
        ),
        "ct_skipped_sufficient_sources": bool(discovery.get("ct_skipped_sufficient_sources")),
        "source_errors": discovery.get("errors") or [],
    }
    if coverage_status != "GOOD":
        warnings.append(f"COVERAGE_{coverage_status}")

    pool, deferred = select_probe_pool(candidates, job["incumbent"], job["limits"]["eligibility_pool"])
    metadata = IPMetadataCache(job["limits"]["ip_metadata_budget"])

    eligibility = []
    adaptive_gate = bool(job["profile"].get("adaptive_gate"))
    for candidate in pool:
        row = gate_candidate(
            candidate,
            dns_observations=2,
            tls_samples_per_ip=1 if adaptive_gate else 2,
            timeout=5.0,
            ip_metadata_lookup=metadata.lookup,
        )
        # QUICK mode spends the second cheap TLS sample only on a candidate that
        # would otherwise be rejected solely because one transport attempt failed.
        if adaptive_gate and set(row.get("hard_rejections") or []) == {"HARD:TLS_UNREACHABLE"}:
            row = gate_candidate(candidate, dns_observations=2, tls_samples_per_ip=2, timeout=5.0, ip_metadata_lookup=metadata.lookup)
            row.setdefault("warnings", []).append("INFO:ADAPTIVE_GATE_RETRY")
        if row.get("incumbent") and row.get("hard_rejections"):
            row["eligibility"] = "BASELINE_ONLY"
        eligibility.append(row)
    if metadata.used >= metadata.budget:
        warnings.append("IP_METADATA_BUDGET_EXHAUSTED")
    if metadata.errors:
        warnings.append("IP_METADATA_PARTIAL_FAILURE")

    benchmarkable = [r for r in eligibility if not r.get("hard_rejections") or r.get("incumbent")]
    benchmarkable.sort(key=gate_selection_key)
    incumbent_gate = next((r for r in benchmarkable if r.get("incumbent")), None)
    non_inc_gate = [r for r in benchmarkable if not r.get("incumbent")]
    fast_input = []
    if incumbent_gate:
        fast_input.append(incumbent_gate)
    fast_input.extend(non_inc_gate[: max(0, job["limits"]["fast_pool"] - len(fast_input))])
    fast = benchmark_candidates(fast_input, samples=job["limits"]["fast_samples"], timeout=5.0, deep=False)
    fast.sort(key=fast_rank_key)

    incumbent_fast = next((r for r in fast if r.get("incumbent")), None)
    non_inc_fast = [r for r in fast if not r.get("incumbent")]
    deep_seed = []
    if incumbent_fast:
        deep_seed.append(incumbent_fast)
    deep_seed.extend(non_inc_fast[: max(0, job["limits"]["deep_pool"] - len(deep_seed))])
    deep = benchmark_candidates(
        deep_seed,
        samples=job["limits"]["deep_samples"],
        timeout=5.0,
        deep=True,
        prior_results=fast,
    )
    deep = [apply_deep_policy(r, incumbent=bool(r.get("incumbent"))) for r in deep]
    target_asn = (pre.get("location") or {}).get("asn")
    enrich_deep_asn(deep, target_asn, metadata)
    deep.sort(key=deep_rank_key)

    ranked_survivors = [r for r in deep if not r.get("incumbent") and not r.get("hard_rejections")]
    prelim = ranked_survivors[: job["limits"]["top_n"]]
    reality_queue = ranked_survivors[: job["limits"]["reality_candidate_cap"]]

    reality_env = reality_environment()
    reality: dict[str, Any] = {"environment": reality_env, "status": "NOT_RUN", "control": None, "candidates": []}
    final_top: list[dict[str, Any]] = []
    status = "SUCCESS"
    incumbent_deep = next((r for r in deep if r.get("incumbent")), None)
    incumbent_p50 = incumbent_deep.get("p50_ms") if incumbent_deep else None

    if not reality_queue:
        reality["status"] = "NOT_RUN_NO_DEEP_SURVIVORS"
        status = "NO_DEEP_SURVIVORS"
    elif not reality_env.get("ready"):
        reality["status"] = "UNAVAILABLE"
        warnings.append(f"REALITY_UNAVAILABLE:{reality_env.get('reason')}")
        status = "PARTIAL_REALITY_UNAVAILABLE"
    else:
        incumbent_gate_any = next((r for r in eligibility if r["hostname"] == job["incumbent"]), None)
        incumbent_ips = (incumbent_gate_any or {}).get("current_ipv4") or (incumbent_gate_any or {}).get("initial_ipv4") or []
        if not incumbent_ips:
            incumbent_ips = resolve_ipv4_observations(job["incumbent"], observations=2).get("common_ipv4") or []
        control = _run_reality_control(job["incumbent"], incumbent_ips, reality_env)
        reality["control"] = control
        if control.get("retried") and control.get("passed"):
            warnings.append("WARN:REALITY_CONTROL_TRANSIENT_FAILURE")
        if not control.get("passed"):
            reality["status"] = "INVALID:REALITY_CONTROL_FAILED"
            status = "INVALID_REALITY_CONTROL"
        else:
            reality["status"] = "RUNNING"
            target_selectable = int(job["limits"]["selectable_target"])
            for row in reality_queue:
                if len(final_top) >= target_selectable:
                    break
                test = run_candidate(
                    row["hostname"],
                    row.get("current_ipv4") or [],
                    attempts=job["limits"]["reality_attempts"],
                    env=reality_env,
                    fail_fast=True,
                )
                reality["candidates"].append(test)
                if test.get("dirty"):
                    reality["status"] = "TARGET_DIRTY_STATE"
                    status = "TARGET_DIRTY_STATE"
                    errors.append("TARGET_DIRTY_STATE")
                    break
                if test.get("passed") and row.get("eligibility") == "ELIGIBLE":
                    final = dict(row)
                    final["policy_eligibility"] = row.get("eligibility")
                    final["benchmark_eligibility"] = "PASS"
                    final["reality_compatibility"] = "PASS"
                    final["reality"] = test
                    final["final"] = "SELECTABLE"
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
                elif len(final_top) < target_selectable:
                    status = "SUCCESS_PARTIAL_CHOICES"
                    warnings.append("FEWER_THAN_TARGET_SELECTABLE")
                else:
                    status = "SUCCESS"

    incumbent_assessment = assess_incumbent(
        job["incumbent"],
        next((r for r in eligibility if r.get("incumbent")), None),
        incumbent_deep,
        reality.get("control"),
        final_top,
        latency_target_ms=float(job["profile"]["latency_target_ms"]),
        coverage_status=coverage_status,
    )

    comparison = build_comparison(
        deep,
        fast,
        reality,
        job["incumbent"],
        job["limits"]["comparison_min_domains"],
        incumbent_p50,
    )
    if len({r["hostname"] for r in comparison}) < 5:
        warnings.append("INSUFFICIENT_COMPARISON_DOMAINS")

    hard_rejected = sum(1 for r in eligibility if r.get("hard_rejections") and not r.get("incumbent"))
    review_required = sum(1 for r in eligibility if not r.get("hard_rejections") and r.get("review"))
    eligible_count = sum(1 for r in eligibility if r.get("eligibility") == "ELIGIBLE")
    deferred_diversity = sum(1 for r in deferred if r.get("status_code") == "DEFERRED:DIVERSITY_BUDGET")
    counts = {
        "discovered": len(candidates),
        "eligibility_selected": len(pool),
        "deferred_budget": len(deferred),
        "deferred_diversity": deferred_diversity,
        "eligible": eligible_count,
        "hard_rejected": hard_rejected,
        "review_required": review_required,
        "fast_benchmarked": len(fast),
        "deep_benchmarked": len(deep),
        "deep_reused_samples": sum(int(r.get("reused_samples") or 0) for r in deep),
        "deep_new_samples": sum(int(r.get("new_samples") or 0) for r in deep),
        "reality_tested": len(reality.get("candidates") or []),
        "reality_passed": sum(1 for r in reality.get("candidates", []) if r.get("passed")),
        "selectable": len(final_top),
        "selectable_target": int(job["limits"]["selectable_target"]),
        "comparison_domains": len({r["hostname"] for r in comparison}),
    }
    rejections = _rejection_rows(eligibility, deep, reality)
    return {
        "schema_version": JOB_SCHEMA_VERSION,
        "worker": identity,
        "status": status,
        "frozen_run": job,
        "preflight": pre,
        "coverage": coverage,
        "regional_candidates": {
            "coverage": discovery.get("coverage"),
            "counts": discovery.get("counts"),
            "errors": discovery.get("errors"),
            "source_records": discovery.get("source_records"),
        },
        "candidates": candidates,
        "probe_pool": pool + deferred,
        "eligibility": eligibility,
        "fast_benchmark": fast,
        "deep_benchmark": deep,
        "reality": reality,
        "preliminary_top5": prelim,
        "top5": final_top[: job["limits"]["top_n"]],
        "comparison": comparison,
        "incumbent_assessment": incumbent_assessment,
        "rejections": rejections,
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
        "counts": counts,
    }


def main() -> int:
    identity = worker_identity()
    if sys.argv[1:] != ["run"]:
        print(json.dumps({"schema_version": JOB_SCHEMA_VERSION, "worker": identity, "status": "BLOCKED", "reason": "FIXED_COMMAND_REQUIRED"}))
        return 2
    try:
        job = validate_job(read_json_stdin())
        if identity["manifest"] != job["expected_worker_manifest"]:
            result = _empty_result(job, identity, "TARGET_WORKER_BUILD_MISMATCH")
        else:
            result = run(job, identity)
    except Exception as exc:
        result = {
            "schema_version": JOB_SCHEMA_VERSION,
            "worker": identity,
            "status": "WORKER_FAILED",
            "reason": type(exc).__name__,
            "top5": [],
            "preliminary_top5": [],
            "comparison": [],
        }
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    sys.stdout.write("\n")
    bad = {"WORKER_FAILED", "TARGET_WORKER_BUILD_MISMATCH", "TARGET_DIRTY_STATE", "TARGET_EGRESS_UNAVAILABLE"}
    return 0 if result.get("status") not in bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
