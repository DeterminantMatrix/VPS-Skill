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
                "deep_pool_cap": 24,
                "deep_refill_batch": 4,
                "top_n": 5,
                "comparison_min_domains": 5,
                "fast_samples": 5,
                "deep_samples": 20,
                "reality_attempts": 5,
                "reality_candidate_cap": 22,
                "selectable_target": 5,
                "ct_base_cap": 40,
                "ct_max_per_domain": 20,
                "dns_workers": 12,
                "ip_metadata_budget": 160,
                "affinity_prefix_cap": 6,
                "affinity_passive_ip_cap": 48,
                "general_osm_record_cap": 1500,
                "general_regional_ingest_cap": 760,
                "ct_sufficient_base_cap": 12,
                "quality_extension_probe_cap": 32,
                "discovery_extension_cap": 160,
                "ct_extension_base_cap": 24,
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
                "eligible_survivor_goal": 25,
                "probe_lane_reserves": {"network_affinity": 16, "general_regional": 24, "institutional": 12},
                "source_lane_reserves": {"network_affinity": 60, "institutional": 120, "general_regional": 300, "passive_expansion": 100},
                "validated_lane_reserves": {"network_affinity": 30, "institutional": 80, "general_regional": 220, "passive_expansion": 50},
                "quality_target_required": True,
                "quality_p50_multiplier": 1.25,
                "quality_p95_multiplier": 1.60,
                "quality_mad_max_ms": 7.5,
                "fast_affinity_reserve": 8,
                "deep_affinity_reserve": 3,
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
            "deep_pool_cap": 22,
            "deep_refill_batch": 4,
            "top_n": 5,
            "comparison_min_domains": 5,
            "fast_samples": 3,
            "deep_samples": 20,
            "reality_attempts": 5,
            "reality_candidate_cap": 20,
            "selectable_target": 5,
            "ct_base_cap": 28,
            "ct_max_per_domain": 12,
            "dns_workers": 14,
            "ip_metadata_budget": 160,
            "affinity_prefix_cap": 4,
            "affinity_passive_ip_cap": 24,
            "general_osm_record_cap": 1100,
            "general_regional_ingest_cap": 340,
            "ct_sufficient_base_cap": 8,
            "quality_extension_probe_cap": 20,
            "discovery_extension_cap": 80,
            "ct_extension_base_cap": 16,
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
            "eligible_survivor_goal": 15,
            "probe_lane_reserves": {"network_affinity": 12, "general_regional": 20, "institutional": 10},
            "source_lane_reserves": {"network_affinity": 40, "institutional": 60, "general_regional": 180, "passive_expansion": 40},
            "validated_lane_reserves": {"network_affinity": 20, "institutional": 40, "general_regional": 120, "passive_expansion": 20},
            "quality_target_required": True,
            "quality_p50_multiplier": 1.25,
            "quality_p95_multiplier": 1.60,
            "quality_mad_max_ms": 7.5,
            "fast_affinity_reserve": 6,
            "deep_affinity_reserve": 2,
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
