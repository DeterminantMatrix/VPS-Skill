#!/usr/bin/env python3
"""Controller-only orchestration for target-measured Reality SNI selection."""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from common import atomic_write_json, validate_hostname
from report import render_report, write_rejections_csv

ALIAS_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
DEFAULT_INVENTORY = Path("/opt/vps-control/inventory/hosts.yaml")
REMOTE_COMMAND = ["reality-sni-target-worker", "run"]


def _walk_inventory(value: Any, key_hint: str | None = None):
    if isinstance(value, dict):
        yield value, key_hint
        for key, child in value.items():
            yield from _walk_inventory(child, str(key))
    elif isinstance(value, list):
        for child in value:
            yield from _walk_inventory(child, key_hint)


def _direct_ips(node: dict[str, Any]) -> set[str]:
    found = set()
    for key in ("ipv4", "public_ipv4", "ip", "address", "public_ip"):
        value = node.get(key)
        if isinstance(value, str):
            found.add(value)
    return found


def _all_ips(node: dict[str, Any]) -> set[str]:
    found = _direct_ips(node)
    access = node.get("access")
    if isinstance(access, dict):
        value = access.get("host")
        if isinstance(value, str):
            found.add(value)
    return found


def _node_score(node: dict[str, Any], target_ip: str) -> int:
    score = 0
    if target_ip in _direct_ips(node):
        score += 10
    if isinstance(node.get("access"), dict):
        score += 4
    if isinstance(node.get("capabilities"), dict):
        score += 3
    if "active" in node or "status" in node:
        score += 2
    if "region" in node or "country" in node or "country_code" in node:
        score += 1
    return score


def _extract_alias(node: dict[str, Any], key_hint: str | None) -> str | None:
    access = node.get("access") if isinstance(node.get("access"), dict) else {}
    values = [access.get("alias"), access.get("ssh_alias"), node.get("ssh_alias"), node.get("alias"), key_hint]
    for value in values:
        if isinstance(value, str) and ALIAS_RE.fullmatch(value) and value not in {"hosts", "access", "capabilities"}:
            return value
    return None


def _extract_region(node: dict[str, Any]) -> str | None:
    for key in ("region", "country_code", "country"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    location = node.get("location")
    if isinstance(location, dict):
        for key in ("region", "country_code", "country"):
            value = location.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def inventory_guard(path: Path, target_ip: str) -> dict[str, Any]:
    try:
        ip = ipaddress.ip_address(target_ip)
        if ip.version != 4 or not ip.is_global:
            raise ValueError("target must be a public IPv4")
    except ValueError as exc:
        raise ValueError("invalid target IPv4") from exc
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"inventory unavailable: {type(exc).__name__}") from exc
    matches: list[tuple[int, dict[str, Any], str | None]] = []
    for node, hint in _walk_inventory(data):
        if target_ip in _all_ips(node):
            matches.append((_node_score(node, target_ip), node, hint))
    if not matches:
        raise ValueError("inventory target missing")
    matches.sort(key=lambda item: item[0], reverse=True)
    best_score = matches[0][0]
    best = [item for item in matches if item[0] == best_score]
    if len(best) != 1:
        raise ValueError("inventory target ambiguous")
    _, node, hint = best[0]
    status = str(node.get("status") or "").lower()
    if node.get("active") is False or node.get("retired") is True or node.get("forbidden") is True or status in {"retired", "forbidden", "inactive", "disabled"}:
        raise ValueError("inventory target inactive/retired/forbidden")
    access = node.get("access") if isinstance(node.get("access"), dict) else {}
    method = str(access.get("method") or node.get("access_method") or "ssh").lower()
    if method != "ssh":
        raise ValueError("inventory access method is not ssh")
    capabilities = node.get("capabilities") if isinstance(node.get("capabilities"), dict) else {}
    if capabilities.get("ssh") is False:
        raise ValueError("inventory ssh capability disabled")
    alias = _extract_alias(node, hint)
    if not alias:
        raise ValueError("inventory SSH alias missing")
    return {"alias": alias, "target_ip": target_ip, "region": _extract_region(node), "inventory_path": str(path)}


def load_seeds(path: Path | None) -> list[str]:
    if path is None:
        return []
    seeds = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.split("#", 1)[0].strip()
        if not raw:
            continue
        host = validate_hostname(raw)
        if host not in seeds:
            seeds.append(host)
    if len(seeds) > 1200:
        raise ValueError("seed file exceeds fixed cap")
    return seeds


def auto_seed_file(root: Path, region: str | None) -> Path | None:
    if not region:
        return None
    candidate = root / "references" / "seeds" / f"{region.strip().lower()}.txt"
    return candidate if candidate.is_file() else None


def build_job(guard: dict[str, Any], seeds: list[str], incumbent: str | None, incumbent_mode: str) -> dict[str, Any]:
    return {
        "schema_version": 3,
        "profile_name": "target-measured-v3",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "target": {"alias": guard["alias"], "inventory_ipv4": guard["target_ip"]},
        "region": guard.get("region"),
        "incumbent_mode": incumbent_mode,
        "incumbent": incumbent,
        "seed_domains": seeds,
        "port": 443,
        "limits": {
            "source_pool_cap": 1200,
            "discovered_cap": 600,
            "eligibility_pool": 120,
            "fast_pool": 50,
            "deep_pool": 10,
            "top_n": 5,
            "fast_samples": 5,
            "deep_samples": 20,
            "reality_attempts": 5,
            "ct_base_cap": 40,
            "ct_max_per_domain": 20,
            "dns_workers": 12,
        },
        "profile": {
            "coverage_goal": 400,
            "primary_radius_km": 75,
            "expanded_radius_km": 150,
            "ct_failure_budget": 3,
            "latency_target_ms": 60.0,
        },
    }


def run_remote(alias: str, job: dict[str, Any], timeout: int) -> tuple[dict[str, Any] | None, str]:
    payload = json.dumps(job, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    proc = subprocess.Popen(["ssh", "-T", alias, *REMOTE_COMMAND], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = proc.communicate(payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return None, "SSH_TIMEOUT"
    try:
        parsed = json.loads(stdout.decode("utf-8", errors="strict"))
        if isinstance(parsed, dict):
            return parsed, "OK" if proc.returncode == 0 else "REMOTE_NONZERO_WITH_RESULT"
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    if proc.returncode != 0:
        text = stderr.decode("utf-8", errors="replace").lower()
        category = "TARGET_WORKER_UNAVAILABLE" if "not found" in text or "command not found" in text else "SSH_REMOTE_FAILED"
        return None, category
    return None, "TARGET_RESULT_INVALID"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target_ip", help="inventory public IPv4; inventory resolves alias and region")
    ap.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    ap.add_argument("--seed-file", type=Path)
    ap.add_argument("--incumbent", default="auto", help="hostname or 'auto' for target-side read-only discovery")
    ap.add_argument("--ssh-timeout", type=int, default=2400)
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    run_dir = Path.cwd()
    stage_path = run_dir / "stage-status.tsv"
    stage_path.write_text("stage\tstatus\tdetail\n", encoding="utf-8")

    try:
        guard = inventory_guard(args.inventory, args.target_ip)
        seed_path = args.seed_file or auto_seed_file(root, guard.get("region"))
        seeds = load_seeds(seed_path)
        if str(args.incumbent).lower() == "auto":
            incumbent, incumbent_mode = None, "auto"
        else:
            incumbent, incumbent_mode = validate_hostname(args.incumbent), "explicit"
            if incumbent not in seeds:
                seeds.append(incumbent)
        job = build_job(guard, seeds, incumbent, incumbent_mode)
    except Exception as exc:
        stage_path.write_text(f"stage\tstatus\tdetail\ninventory_or_input\tFAILED\t{type(exc).__name__}\n", encoding="utf-8")
        atomic_write_json(run_dir / "top5.json", {"status": "BLOCKED", "reason": "INVENTORY_OR_INPUT_FAILED", "top5": []})
        return 2

    atomic_write_json(run_dir / "frozen-run.json", job)
    with stage_path.open("a", encoding="utf-8") as handle:
        handle.write("freeze\tOK\tcontroller profile frozen before target evaluation\n")

    result, remote_status = run_remote(guard["alias"], job, max(60, args.ssh_timeout))
    with stage_path.open("a", encoding="utf-8") as handle:
        handle.write(f"target_worker\t{remote_status}\tone fixed command over one SSH process\n")
    if result is None:
        blocked = {"status": "BLOCKED", "reason": remote_status, "top5": [], "preliminary_top5": []}
        atomic_write_json(run_dir / "target-result.json", blocked)
        atomic_write_json(run_dir / "top5.json", blocked)
        atomic_write_json(run_dir / "run-metadata.json", {"status": remote_status, "guard": guard, "frozen_run": job})
        return 3

    atomic_write_json(run_dir / "target-result.json", result)
    mapping = {
        "target-frozen-run.json": result.get("frozen_run", {}),
        "target-preflight.json": result.get("preflight", {}),
        "regional-candidates.json": result.get("regional_candidates", {}),
        "candidates.json": result.get("candidates", []),
        "probe-pool.json": result.get("probe_pool", []),
        "eligibility.json": result.get("eligibility", []),
        "fast-benchmark.json": result.get("fast_benchmark", []),
        "deep-benchmark.json": result.get("deep_benchmark", []),
        "reality-results.json": result.get("reality", {}),
        "top5.json": {"status": result.get("status"), "top5": result.get("top5", []), "preliminary_top5": result.get("preliminary_top5", [])},
        "run-metadata.json": {"status": result.get("status"), "guard": guard, "controller_frozen_run": job,
                              "target_frozen_run": result.get("frozen_run", {}), "counts": result.get("counts", {}), "warnings": result.get("warnings", [])},
    }
    for name, payload in mapping.items():
        atomic_write_json(run_dir / name, payload)
    write_rejections_csv(run_dir / "rejections.csv", result.get("rejections", []))
    (run_dir / "report.md").write_text(render_report(result), encoding="utf-8")
    with stage_path.open("a", encoding="utf-8") as handle:
        handle.write(f"artifacts\tOK\t{result.get('status', 'UNKNOWN')}\n")
    print(f"TARGET_MEASURED_RUN_STATUS:{result.get('status', 'UNKNOWN')}")
    return 0 if result.get("status") in {"SUCCESS", "SUCCESS_WITH_REVIEW", "PARTIAL_REALITY_UNAVAILABLE", "INVALID_REALITY_CONTROL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
