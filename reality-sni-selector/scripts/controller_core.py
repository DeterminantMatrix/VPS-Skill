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

from common import (
    IMPLEMENTATION_VERSION,
    JOB_SCHEMA_VERSION,
    PROFILE_NAME,
    WORKER_PROTOCOL,
    atomic_write_json,
    compute_worker_manifest,
    validate_hostname,
)
from report import render_report, write_rejections_csv

ALIAS_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
DEFAULT_INVENTORY_CANDIDATES = (Path("inventory/hosts.yaml"), Path("/opt/vps-control/inventory/hosts.yaml"))
REMOTE_COMMAND = ["/usr/local/bin/reality-sni-target-worker", "run"]


def resolve_inventory_path(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    for candidate in DEFAULT_INVENTORY_CANDIDATES:
        if candidate.is_file():
            return candidate
    return DEFAULT_INVENTORY_CANDIDATES[0]


def inventory_guard(path: Path, target_ip: str) -> dict[str, Any]:
    """Resolve one host using the local vps-control inventory contract only."""
    try:
        ip = ipaddress.ip_address(target_ip)
        if ip.version != 4 or not ip.is_global:
            raise ValueError
    except ValueError as exc:
        raise ValueError("invalid target public IPv4") from exc

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"inventory unavailable: {type(exc).__name__}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("hosts"), dict):
        raise ValueError("inventory local hosts schema missing")

    matches: list[tuple[str, dict[str, Any]]] = []
    for canonical, node in data["hosts"].items():
        if not isinstance(canonical, str) or not isinstance(node, dict):
            continue
        access = node.get("access") if isinstance(node.get("access"), dict) else {}
        facts = {access.get("address"), access.get("hostname")}
        if target_ip in {v for v in facts if isinstance(v, str)}:
            matches.append((canonical, node))
    if not matches:
        raise ValueError("inventory target missing")
    if len(matches) != 1:
        raise ValueError("inventory target ambiguous")

    canonical, node = matches[0]
    inventory_id = node.get("inventory_id")
    if inventory_id is not None and str(inventory_id) != canonical:
        raise ValueError("inventory_id does not match canonical host key")

    alias = node.get("alias")
    region = node.get("region")
    access = node.get("access") if isinstance(node.get("access"), dict) else {}
    capabilities = node.get("capabilities") if isinstance(node.get("capabilities"), dict) else {}
    state = node.get("state") if isinstance(node.get("state"), dict) else {}

    if not isinstance(alias, str) or not ALIAS_RE.fullmatch(alias):
        raise ValueError("inventory SSH alias missing/invalid")
    if not isinstance(region, str) or not region.strip():
        raise ValueError("inventory region missing")
    if access.get("method") != "ssh":
        raise ValueError("inventory access.method must be ssh")
    if access.get("address") != target_ip and access.get("hostname") != target_ip:
        raise ValueError("inventory target address mismatch")
    if capabilities.get("ssh") is not True:
        raise ValueError("inventory capabilities.ssh must be true")
    if state.get("retired") is True or state.get("forbidden") is True:
        raise ValueError("inventory target retired/forbidden")
    status = str(state.get("status") or "").lower()
    if status in {"retired", "forbidden", "inactive", "disabled"}:
        raise ValueError("inventory target inactive")

    return {
        "inventory_id": canonical,
        "alias": alias,
        "target_ip": target_ip,
        "region": region.strip(),
        "inventory_path": str(path),
        "access_facts": {
            "address": access.get("address"),
            "hostname": access.get("hostname"),
            "port": access.get("port"),
            "user": access.get("user"),
            "proxy_jump": access.get("proxy_jump"),
            "identity_ref": access.get("identity_ref"),
        },
    }


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


def _profile_settings(mode: str) -> tuple[dict[str, int], dict[str, Any]]:
    if mode == "audit":
        return (
            {
                "source_pool_cap": 1200,
                "discovered_cap": 600,
                "eligibility_pool": 120,
                "fast_pool": 50,
                "deep_pool": 10,
                "top_n": 5,
                "comparison_min_domains": 5,
                "fast_samples": 5,
                "deep_samples": 20,
                "reality_attempts": 5,
                "reality_candidate_cap": 9,
                "selectable_target": 5,
                "ct_base_cap": 40,
                "ct_max_per_domain": 20,
                "dns_workers": 12,
                "ip_metadata_budget": 128,
            },
            {
                "run_mode": "audit",
                "coverage_goal": 400,
                "source_stop_target": 1200,
                "primary_radius_km": 75,
                "expanded_radius_km": 150,
                "ct_failure_budget": 3,
                "latency_target_ms": 60.0,
                "strict_shared_edge": True,
                "adaptive_gate": False,
            },
        )
    if mode != "quick":
        raise ValueError("unsupported profile mode")
    return (
        {
            "source_pool_cap": 400,
            "discovered_cap": 180,
            "eligibility_pool": 60,
            "fast_pool": 30,
            "deep_pool": 10,
            "top_n": 5,
            "comparison_min_domains": 5,
            "fast_samples": 3,
            "deep_samples": 20,
            "reality_attempts": 5,
            "reality_candidate_cap": 8,
            "selectable_target": 5,
            "ct_base_cap": 20,
            "ct_max_per_domain": 10,
            "dns_workers": 12,
            "ip_metadata_budget": 96,
        },
        {
            "run_mode": "quick",
            "coverage_goal": 150,
            "source_stop_target": 220,
            "primary_radius_km": 75,
            "expanded_radius_km": 150,
            "ct_failure_budget": 3,
            "latency_target_ms": 60.0,
            "strict_shared_edge": True,
            "adaptive_gate": True,
        },
    )


def build_job(
    guard: dict[str, Any],
    seeds: list[str],
    incumbent: str | None,
    incumbent_mode: str,
    *,
    worker_manifest: str,
    profile_mode: str = "quick",
) -> dict[str, Any]:
    limits, profile = _profile_settings(profile_mode)
    return {
        "schema_version": JOB_SCHEMA_VERSION,
        "worker_protocol": WORKER_PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "expected_worker_manifest": worker_manifest,
        "profile_name": PROFILE_NAME,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "target": {
            "inventory_id": guard["inventory_id"],
            "alias": guard["alias"],
            "inventory_ipv4": guard["target_ip"],
        },
        "region": guard.get("region"),
        "incumbent_mode": incumbent_mode,
        "incumbent": incumbent,
        "seed_domains": seeds,
        "port": 443,
        "limits": limits,
        "profile": profile,
    }


def run_remote(alias: str, job: dict[str, Any], timeout: int) -> tuple[dict[str, Any] | None, str]:
    payload = json.dumps(job, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    proc = subprocess.Popen(
        ["ssh", "-T", alias, *REMOTE_COMMAND],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = proc.communicate(payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return None, "SSH_TIMEOUT"

    try:
        parsed = json.loads(stdout.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None

    if isinstance(parsed, dict):
        worker = parsed.get("worker") if isinstance(parsed.get("worker"), dict) else {}
        if parsed.get("schema_version") != JOB_SCHEMA_VERSION or worker.get("protocol") != WORKER_PROTOCOL or worker.get("implementation_version") != IMPLEMENTATION_VERSION:
            return None, "TARGET_WORKER_VERSION_MISMATCH"
        if worker.get("manifest") != job.get("expected_worker_manifest"):
            return None, "TARGET_WORKER_BUILD_MISMATCH"
        return parsed, "OK" if proc.returncode == 0 else "REMOTE_NONZERO_WITH_RESULT"

    if proc.returncode != 0:
        text = stderr.decode("utf-8", errors="replace").lower()
        category = "TARGET_WORKER_UNAVAILABLE" if "not found" in text or "command not found" in text else "SSH_REMOTE_FAILED"
        return None, category
    return None, "TARGET_RESULT_INVALID"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target_ip", help="inventory public IPv4; local inventory resolves alias and region")
    ap.add_argument("--inventory", type=Path, default=None)
    ap.add_argument("--seed-file", type=Path)
    ap.add_argument("--incumbent", default="auto", help="hostname or 'auto' for target-side read-only discovery")
    ap.add_argument("--profile", choices=("quick", "audit"), default="quick", help="quick is the default adaptive selection profile; audit restores broad coverage")
    ap.add_argument("--ssh-timeout", type=int, default=2400)
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    run_dir = Path.cwd()
    stage_path = run_dir / "stage-status.tsv"
    stage_path.write_text("stage\tstatus\tdetail\n", encoding="utf-8")

    try:
        inventory_path = resolve_inventory_path(args.inventory)
        guard = inventory_guard(inventory_path, args.target_ip)
        seed_path = args.seed_file or auto_seed_file(root, guard.get("region"))
        seeds = load_seeds(seed_path)
        if str(args.incumbent).lower() == "auto":
            incumbent, incumbent_mode = None, "auto"
        else:
            incumbent, incumbent_mode = validate_hostname(args.incumbent), "explicit"
            if incumbent not in seeds:
                seeds.append(incumbent)
        manifest = compute_worker_manifest(root / "scripts")
        job = build_job(guard, seeds, incumbent, incumbent_mode, worker_manifest=manifest, profile_mode=args.profile)
    except Exception as exc:
        stage_path.write_text(f"stage\tstatus\tdetail\ninventory_or_input\tFAILED\t{type(exc).__name__}\n", encoding="utf-8")
        atomic_write_json(run_dir / "top5.json", {"status": "BLOCKED", "reason": "INVENTORY_OR_INPUT_FAILED", "top5": [], "comparison": []})
        return 2

    atomic_write_json(run_dir / "frozen-run.json", job)
    with stage_path.open("a", encoding="utf-8") as handle:
        handle.write(f"freeze\tOK\tv4.1 {args.profile} profile and expected worker manifest frozen before target evaluation\n")

    result, remote_status = run_remote(guard["alias"], job, max(60, args.ssh_timeout))
    with stage_path.open("a", encoding="utf-8") as handle:
        handle.write(f"target_worker\t{remote_status}\tone fixed absolute command over one SSH process\n")
    if result is None:
        blocked = {"schema_version": JOB_SCHEMA_VERSION, "status": "BLOCKED", "reason": remote_status, "top5": [], "preliminary_top5": [], "comparison": []}
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
        "comparison.json": result.get("comparison", []),
        "incumbent-assessment.json": result.get("incumbent_assessment", {}),
        "top5.json": {
            "status": result.get("status"),
            "coverage": result.get("coverage", {}),
            "top5": result.get("top5", []),
            "preliminary_top5": result.get("preliminary_top5", []),
            "comparison": result.get("comparison", []),
        },
        "run-metadata.json": {
            "status": result.get("status"),
            "worker": result.get("worker", {}),
            "guard": guard,
            "controller_frozen_run": job,
            "target_frozen_run": result.get("frozen_run", {}),
            "coverage": result.get("coverage", {}),
            "counts": result.get("counts", {}),
            "warnings": result.get("warnings", []),
        },
    }
    for name, payload in mapping.items():
        atomic_write_json(run_dir / name, payload)
    write_rejections_csv(run_dir / "rejections.csv", result.get("rejections", []))
    (run_dir / "report.md").write_text(render_report(result), encoding="utf-8")
    with stage_path.open("a", encoding="utf-8") as handle:
        handle.write(f"artifacts\tOK\t{result.get('status', 'UNKNOWN')}\n")
    print(f"TARGET_MEASURED_RUN_STATUS:{result.get('status', 'UNKNOWN')}")
    ok_status = {"SUCCESS", "SUCCESS_WITH_REVIEW", "SUCCESS_PARTIAL_CHOICES", "PARTIAL_REALITY_UNAVAILABLE", "INVALID_REALITY_CONTROL"}
    return 0 if result.get("status") in ok_status else 1


if __name__ == "__main__":
    raise SystemExit(main())
