#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path
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

def render_report(result: dict[str, Any]) -> str:
    counts = result.get("counts") or {}
    preflight = result.get("preflight") or {}
    coverage = result.get("coverage") or {}
    frozen = result.get("frozen_run") or {}
    comparison = result.get("comparison") or []
    assessment = result.get("incumbent_assessment") or {}
    lines = [
        "# Reality SNI selection report",
        "",
        f"- Status: `{result.get('status', 'UNKNOWN')}`",
        f"- Target egress IPv4: `{preflight.get('observed_egress_ip') or 'unknown'}`",
        f"- Region: `{frozen.get('region') or 'unknown'}`",
        f"- Incumbent: `{frozen.get('incumbent') or 'unknown'}`",
        f"- Run profile: `{coverage.get('profile') or (frozen.get('profile') or {}).get('run_mode') or 'unknown'}`",
        f"- Coverage: `{coverage.get('status', 'unknown')}` ({coverage.get('validated', 0)} / goal {coverage.get('goal', 'unknown')})",
        f"- Selection maturity: `{coverage.get('selection_maturity', 'unknown')}`",
        "",
        "## Current SNI assessment",
        "",
        f"- Verdict: **{assessment.get('verdict', '暂无法评估')}** (`{assessment.get('code', 'UNABLE_TO_ASSESS')}`)",
        f"- Confidence: `{assessment.get('confidence', 'LOW')}`",
        f"- Current metrics: {_assessment_metrics(assessment)}",
        f"- Reality control: `{((assessment.get('metrics') or {}).get('reality_control') or 'NOT_RUN')}`",
        "",
    ]
    alternative = assessment.get("best_alternative") or {}
    if alternative:
        lines.append(
            f"- Best selectable alternative: `{alternative.get('hostname')}` — P50 {_fmt(alternative.get('p50_ms'), ' ms')}, "
            f"P95 {_fmt(alternative.get('p95_ms'), ' ms')}, P50 improvement {_fmt(alternative.get('p50_improvement_pct'), '%')}"
        )
    reasons = assessment.get("reasons") or []
    if reasons:
        lines.append("- Decision reasons: " + ", ".join(f"`{item}`" for item in reasons))
    lines.extend([
        "",
        "## Stage counts",
        "",
        f"- Discovered / validated: **{counts.get('discovered', 0)}**",
        f"  - Selected for eligibility: **{counts.get('eligibility_selected', 0)}**",
        f"    - Eligible: **{counts.get('eligible', 0)}**",
        f"    - Review required: **{counts.get('review_required', 0)}**",
        f"    - Hard rejected: **{counts.get('hard_rejected', 0)}**",
        f"  - Deferred before eligibility: **{counts.get('deferred_budget', 0)}**",
        f"    - Diversity-budget deferred: **{counts.get('deferred_diversity', 0)}**",
        f"- Fast benchmarked: **{counts.get('fast_benchmarked', 0)}**",
        f"  - Deep benchmarked: **{counts.get('deep_benchmarked', 0)}**",
        f"    - Reused Fast samples in Deep: **{counts.get('deep_reused_samples', 0)}**",
        f"    - New Deep samples: **{counts.get('deep_new_samples', 0)}**",
        f"    - Reality tested: **{counts.get('reality_tested', 0)}**",
        f"      - Reality passed: **{counts.get('reality_passed', 0)}**",
        f"      - Final selectable: **{counts.get('selectable', 0)} / target {counts.get('selectable_target', 5)}**",
        "",
        "## Recommendation comparison",
        "",
        "Rows are ordered by recommendation, then reliability/latency. `Reality PASS` does not override a policy rejection.",
        "",
        "| Rank | Domain | Recommendation | Final / policy | Front door / platform | TLS success | P50 | P95 | MAD | Reality | ASN / org | vs incumbent P50 |",
        "|---:|---|---|---|---|---:|---:|---:|---:|---|---|---:|",
    ])
    for row in comparison:
        lines.append(
            "| {rank} | `{host}` | **{rec}** | `{final}` / `{policy}` | `{front}` | {success} | {p50} | {p95} | {mad} | `{reality}` | `{asn}` | {improve} |".format(
                rank=row.get("recommendation_rank", "?"),
                host=row.get("hostname", "unknown"),
                rec=row.get("recommendation", "unknown"),
                final=row.get("final_state", "unknown"),
                policy=row.get("policy_eligibility", row.get("eligibility", "unknown")),
                front=_front(row),
                success=_pct(row.get("success_rate")),
                p50=_fmt(row.get("p50_ms"), " ms"),
                p95=_fmt(row.get("p95_ms"), " ms"),
                mad=_fmt(row.get("mad_ms"), " ms"),
                reality=_reality(row),
                asn=_asn_org(row).replace("|", "/"),
                improve=_fmt(row.get("incumbent_p50_improvement_pct"), "%"),
            )
        )
    if len({r.get("hostname") for r in comparison if r.get("hostname")}) < 5:
        lines.extend([
            "",
            "> `INSUFFICIENT_COMPARISON_DOMAINS`: fewer than five distinct measured domains were available. No rows were fabricated.",
        ])

    lines.extend(["", "## Final selectable candidates", ""])
    top = result.get("top5") or []
    if not top:
        lines.append("No fully selectable candidate is available. Use the comparison table to inspect review, baseline, Reality-failed, or policy-rejected domains.")
    for index, row in enumerate(top, 1):
        lines.extend([
            f"### {index}. `{row.get('hostname')}`",
            "",
            f"- Final state: `{row.get('final')}`",
            f"- Policy eligibility: `{row.get('policy_eligibility') or row.get('eligibility')}`",
            f"- P50 / P95 / MAD: {_fmt(row.get('p50_ms'), ' ms')} / {_fmt(row.get('p95_ms'), ' ms')} / {_fmt(row.get('mad_ms'), ' ms')}",
            f"- Success rate: {_pct(row.get('success_rate'))}",
            f"- Reality: `{_reality({**row, 'reality_compatibility': 'PASS', 'reality_summary': row.get('reality')})}`",
            f"- Front door: `{_front(row)}`",
            f"- Incumbent P50 improvement: {_fmt(row.get('incumbent_p50_improvement_pct'), '%')}",
            "",
        ])

    source_errors = coverage.get("source_errors") or []
    if source_errors:
        lines.extend(["## Coverage limitations", ""])
        for item in source_errors:
            lines.append(f"- `{item}`")
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
