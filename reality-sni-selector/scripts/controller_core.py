#!/usr/bin/env python3
"""Pure controller helpers for Reality SNI selection profiles and frozen jobs."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import IMPLEMENTATION_VERSION, JOB_SCHEMA_VERSION, PROFILE_NAME, WORKER_PROTOCOL, validate_hostname

DEFAULT_INVENTORY_CANDIDATES = (Path("inventory/hosts.yaml"), Path("/opt/vps-control/inventory/hosts.yaml"))
REMOTE_COMMAND = ["/usr/local/bin/reality-sni-target-worker", "run"]


def resolve_inventory_path(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    for candidate in DEFAULT_INVENTORY_CANDIDATES:
        if candidate.is_file():
            return candidate
    return DEFAULT_INVENTORY_CANDIDATES[0]


def load_seeds(path: Path | None) -> list[str]:
    if path is None:
        return []
    seeds: list[str] = []
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


def profile_settings(mode: str) -> tuple[dict[str, int], dict[str, Any]]:
    if mode == "audit":
        return (
            {
                "source_pool_cap": 1200,
                "discovered_cap": 600,
                "eligibility_pool": 120,
                "fast_pool": 50,
                "deep_pool": 10,
                "deep_pool_cap": 20,
                "deep_refill_batch": 4,
                "top_n": 5,
                "comparison_min_domains": 5,
                "fast_samples": 5,
                "deep_samples": 20,
                "reality_attempts": 5,
                "reality_candidate_cap": 18,
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
                "p50_equivalence_ms": 2.0,
                "strict_shared_edge": True,
                "adaptive_gate": False,
            },
        )
    if mode != "quick":
        raise ValueError("unsupported profile mode")
    return (
        {
            "source_pool_cap": 520,
            "discovered_cap": 240,
            "eligibility_pool": 80,
            "fast_pool": 36,
            "deep_pool": 10,
            "deep_pool_cap": 18,
            "deep_refill_batch": 4,
            "top_n": 5,
            "comparison_min_domains": 5,
            "fast_samples": 3,
            "deep_samples": 20,
            "reality_attempts": 5,
            "reality_candidate_cap": 16,
            "selectable_target": 5,
            "ct_base_cap": 28,
            "ct_max_per_domain": 12,
            "dns_workers": 14,
            "ip_metadata_budget": 128,
        },
        {
            "run_mode": "quick",
            "coverage_goal": 200,
            "source_stop_target": 300,
            "primary_radius_km": 75,
            "expanded_radius_km": 150,
            "ct_failure_budget": 3,
            "latency_target_ms": 60.0,
            "p50_equivalence_ms": 2.0,
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
    limits, profile = profile_settings(profile_mode)
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
