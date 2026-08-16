#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "unknown"
    return f"{value}{suffix}"


def render_report(result: dict[str, Any]) -> str:
    counts = result.get("counts") or {}
    preflight = result.get("preflight") or {}
    lines = [
        "# Reality SNI selection report",
        "",
        f"- Status: `{result.get('status', 'UNKNOWN')}`",
        f"- Target egress IPv4: `{preflight.get('observed_egress_ip') or 'unknown'}`",
        f"- Region: `{(result.get('frozen_run') or {}).get('region') or 'unknown'}`",
        f"- Incumbent: `{(result.get('frozen_run') or {}).get('incumbent') or 'unknown'}`",
        "",
        "## Counts",
        "",
        f"- Discovered IPv4 hostnames: {counts.get('discovered', 0)}",
        f"- Eligibility selected: {counts.get('eligibility_selected', 0)}",
        f"- Deferred by budget: {counts.get('deferred_budget', 0)}",
        f"- Hard rejected: {counts.get('hard_rejected', 0)}",
        f"- Review required: {counts.get('review_required', 0)}",
        f"- Fast benchmarked: {counts.get('fast_benchmarked', 0)}",
        f"- Deep benchmarked: {counts.get('deep_benchmarked', 0)}",
        f"- Reality tested: {counts.get('reality_tested', 0)}",
        f"- Selectable: {counts.get('selectable', 0)}",
        "",
        "## Top candidates",
        "",
    ]
    top = result.get("top5") or []
    if not top:
        lines.append("No fully final candidate is available. See preliminary/deep results and run status.")
    for index, row in enumerate(top, 1):
        lines.extend([
            f"### {index}. `{row.get('hostname')}`",
            "",
            f"- Final state: `{row.get('final')}`",
            f"- P50: {_fmt(row.get('p50_ms'), ' ms')}",
            f"- P95: {_fmt(row.get('p95_ms'), ' ms')}",
            f"- Success rate: {_fmt(row.get('success_rate'))}",
            f"- Reality: `{(row.get('reality') or {}).get('code', 'unknown')}`",
            f"- Front door: `{((row.get('front_door') or {}).get('class') or 'unknown')}`",
            f"- Incumbent P50 improvement: {_fmt(row.get('incumbent_p50_improvement_pct'), '%')}",
            "",
        ])
    prelim = result.get("preliminary_top5") or []
    if prelim and not top:
        lines.extend(["## Preliminary deep ranking", ""])
        for index, row in enumerate(prelim, 1):
            lines.append(f"{index}. `{row.get('hostname')}` — P50 {_fmt(row.get('p50_ms'), ' ms')}, P95 {_fmt(row.get('p95_ms'), ' ms')}, state `{row.get('eligibility')}`")
        lines.append("")
    warnings = result.get("warnings") or []
    if warnings:
        lines.extend(["## Run warnings", ""])
        for item in warnings:
            lines.append(f"- `{item}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_rejections_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["hostname", "stage", "class", "code"])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in writer.fieldnames})
