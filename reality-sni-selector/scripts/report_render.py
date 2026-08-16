#!/usr/bin/env python3
from __future__ import annotations
from typing import Any

from decision_view import build_decision_view
from report_format import (
    _asn_org,
    _assessment_metrics,
    _confidence_zh,
    _fmt,
    _front,
    _network_affinity,
    _pct,
    _policy_label,
    _protocol_details,
    _protocol_label,
    _reality,
    _reality_label,
    _risk_zh,
    _tls_versions,
)


def _current_card_row(assessment: dict[str, Any]) -> dict[str, Any]:
    metrics = assessment.get("metrics") or {}
    return {
        "protocol_compliance": metrics.get("protocol_compliance") or {},
        "tls_versions": metrics.get("tls_versions") or [],
        "alpn_protocols": metrics.get("alpn_protocols") or [],
        "network_affinity": metrics.get("network_affinity") or {},
    }


def _best_by(top: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    candidates = [row for row in top if row.get(key) is not None]
    if not candidates:
        return None
    return min(candidates, key=lambda row: float(row[key]))


def _best_network(top: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not top:
        return None
    return min(top, key=lambda row: int((row.get("network_affinity") or {}).get("rank", 9)))


def render_report(result: dict[str, Any]) -> str:
    counts = result.get("counts") or {}
    preflight = result.get("preflight") or {}
    coverage = result.get("coverage") or {}
    frozen = result.get("frozen_run") or {}
    view = build_decision_view(result)
    comparison = view["comparison"]
    assessment = view["incumbent_assessment"]
    decision = view["decision_summary"]
    top = view["top5"]
    current_row = _current_card_row(assessment)
    refill = (result.get("reality") or {}).get("adaptive_refill") or {}

    best = top[0] if top else None
    current_host = assessment.get("hostname") or frozen.get("incumbent") or "unknown"
    current_verdict = assessment.get("verdict", "暂无法评估")
    keep_current = current_verdict in {"继续使用", "可继续使用，但有优化空间", "暂可继续使用，建议复核"}

    lines = [
        "# Reality SNI 优选决策报告",
        "",
        "## A. 一句话结论",
        "",
        f"- Run 状态：`{result.get('status', 'UNKNOWN')}`",
        f"- 当前 SNI：`{current_host}` → **{current_verdict}**",
        f"- 最佳新候选：`{decision.get('recommended_sni') or '无'}` — `{decision.get('recommended_grade') or 'N/A'}` {decision.get('recommended_label') or ''}",
        f"- 当前 SNI 与首选取舍：{assessment.get('tradeoff_text') or '无足够比较证据'}",
        f"- 最终 SELECTABLE：**{counts.get('selectable', len(top))} / {counts.get('selectable_target', 5)}**",
        f"- 候选自身置信度：**{_confidence_zh(decision.get('candidate_confidence'))}**；搜索覆盖置信度：**{_confidence_zh(decision.get('search_confidence'))}**；综合推荐置信度：**{_confidence_zh(decision.get('overall_recommendation_confidence'))}**",
        "",
        "## B. 当前 SNI 健康卡",
        "",
        "| 项目 | 当前结果 |",
        "|---|---|",
        f"| SNI | `{current_host}` |",
        f"| 最终评价 | **{current_verdict}** (`{assessment.get('code', 'UNABLE_TO_ASSESS')}`) |",
        f"| REALITY Protocol | `{(assessment.get('metrics') or {}).get('protocol_compliance', {}).get('state', 'UNKNOWN')}` — {_protocol_details(current_row)} |",
        f"| TLS / ALPN | `{_tls_versions(current_row)}` |",
        f"| Policy hard reject | {', '.join(f'`{v}`' for v in ((assessment.get('metrics') or {}).get('hard_rejections') or [])) or '无'} |",
        f"| Reality control | `{((assessment.get('metrics') or {}).get('reality_control') or 'NOT_RUN')}` |",
        f"| TLS / P50 / P95 / MAD | {_assessment_metrics(assessment)} |",
        f"| Network affinity | `{_network_affinity(current_row)}` |",
        f"| 与最佳候选 | {assessment.get('tradeoff_text') or '无足够比较证据'} |",
        "",
    ]

    reasons = assessment.get("reasons") or []
    if reasons:
        lines.append("判断依据：" + ", ".join(f"`{item}`" for item in reasons))
        lines.append("")

    lines.extend([
        "## C. Top 5 核心决策表",
        "",
        "有 5 个 `SELECTABLE` 时必须完整显示 5 个；不足 5 个时只显示真实通过者，不伪造候选。",
        "",
        "| # | SNI | 推荐 | Protocol | TLS / ALPN | Policy | Reality | P50 / P95 | TLS可靠性 / 稳定性 | Network | Front Door | 风险 | 综合置信度 |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|",
    ])
    for row in top:
        lines.append(
            "| {rank} | `{host}` | **{grade} {label}** | `{protocol}` | `{tlsver}` | `{policy}` | `{reality}` | {p50} / {p95} | `{tls_rel}` / `{stability}` | `{network}` | `{front}` | `{risk}` | `{confidence}` |".format(
                rank=row.get("recommendation_rank", "?"),
                host=row.get("hostname", "unknown"),
                grade=row.get("recommendation_grade", "?"),
                label=row.get("recommendation_label", ""),
                protocol=_protocol_label(row),
                tlsver=_tls_versions(row),
                policy=_policy_label(row),
                reality=_reality_label(row),
                p50=_fmt(row.get("p50_ms"), " ms"),
                p95=_fmt(row.get("p95_ms"), " ms"),
                tls_rel=row.get("tls_reliability_grade", row.get("tls_grade", "unknown")),
                stability=row.get("runtime_stability_grade", "unknown"),
                network=_network_affinity(row),
                front=_front(row),
                risk=_risk_zh(row.get("durability_risk")),
                confidence=_confidence_zh(row.get("overall_recommendation_confidence")),
            )
        )
    lines.append("")
    if len(top) < 5:
        lines.append(f"> `FEWER_THAN_FIVE_SELECTABLE`: 本轮只确认 **{len(top)}** 个完整 SELECTABLE 候选。")
        lines.append("")

    lines.extend(["## D. 候选详细卡与模型评语事实", ""])
    for row in top:
        improve = row.get("incumbent_p50_improvement_pct")
        relation = "unknown"
        if improve is not None:
            relation = f"相对当前 P50 改善 {improve}%" if float(improve) >= 0 else f"相对当前 P50 慢 {abs(float(improve))}%"
        lines.extend([
            f"### {row.get('recommendation_rank', '?')}. `{row.get('hostname')}` — {row.get('recommendation_grade', '?')} {row.get('recommendation_label', '')}",
            "",
            f"- **Protocol**：`{_protocol_label(row)}` — {_protocol_details(row)}；观测 TLS/ALPN：`{_tls_versions(row)}`。",
            f"- **Safety / Policy**：`{_policy_label(row)}`；Front Door：`{_front(row)}`；ASN/组织：`{_asn_org(row)}`。",
            f"- **Reality**：`{_reality_label(row)}`；Final：`{row.get('final_state') or row.get('final')}`。",
            f"- **Reliability**：TLS `{_pct(row.get('success_rate'))}` / grade `{row.get('tls_reliability_grade', row.get('tls_grade', 'unknown'))}`；运行稳定性 `{row.get('runtime_stability_grade', 'unknown')}`。",
            f"- **Performance**：P50 `{_fmt(row.get('p50_ms'), ' ms')}`；P95 `{_fmt(row.get('p95_ms'), ' ms')}`；MAD `{_fmt(row.get('mad_ms'), ' ms')}`；等级 `{row.get('performance_grade', 'unknown')}`。",
            f"- **Network affinity**：`{_network_affinity(row)}`。",
            f"- **Operational risk**：`{row.get('durability_risk', 'unknown')}`；这是基于本轮可观察证据的启发式风险，不代表未来可用性保证。",
            f"- **与当前 SNI**：{relation}。",
            f"- **排名理由**：{row.get('ranking_rationale') or '无'}",
            f"- **置信度**：Candidate `{row.get('candidate_confidence', 'LOW')}` / Search `{row.get('search_confidence', 'LOW')}` / Overall `{row.get('overall_recommendation_confidence', 'LOW')}`。",
            f"- **模型评语事实集**：`{row.get('model_commentary_facts')}`",
            "- **模型评语规则**：大模型只能解释上述事实，写 1–3 句中文点评；不得发明历史 uptime、未来稳定性、未测 ASN/CDN 关系或真实客户端链路表现。",
            "",
        ])

    lowest_tail = _best_by(top, "p95_ms")
    best_network = _best_network(top)
    lines.extend([
        "## E. 怎么选",
        "",
        f"- **如果只选一个**：`{current_host if keep_current else (best or {}).get('hostname', '无')}`。" + (" 当前 SNI 已通过核心门槛，暂无足够收益要求切换。" if keep_current else " 当前 SNI 需要更换时优先使用首选 SELECTABLE。"),
        f"- **最佳备用 SNI**：`{(best or {}).get('hostname', '无')}`。",
        f"- **如果更重视最低尾延迟 P95**：`{(lowest_tail or {}).get('hostname', '无')}`。",
        f"- **如果更重视网络亲和性**：`{(best_network or {}).get('hostname', '无')}`（`{_network_affinity(best_network) if best_network else 'unknown'}`）。",
        f"- **本轮可选数量**：{len(top)} / {counts.get('selectable_target', 5)}。",
        "",
        "## F. 搜索质量与范围",
        "",
        f"- Target egress IPv4：`{preflight.get('observed_egress_ip') or 'unknown'}`",
        f"- Region：`{frozen.get('region') or 'unknown'}`",
        f"- Profile：`{coverage.get('profile') or (frozen.get('profile') or {}).get('run_mode') or 'unknown'}`",
        f"- Coverage：`{coverage.get('status', 'unknown')}` — **{coverage.get('validated', 0)} / {coverage.get('goal', 'unknown')}**",
        f"- Selection maturity：`{coverage.get('selection_maturity', 'unknown')}`",
        f"- Search confidence：**{_confidence_zh(decision.get('search_confidence'))}**",
        "",
        "> Candidate confidence 回答“这个域名自身是否被充分验证”；Search confidence 回答“本轮搜索是否足够广”。Search LOW 不等于已经通过完整测试的候选本身不可靠。",
        "",
        "## G. 自适应流水线统计",
        "",
        f"- Discovered / validated：**{counts.get('discovered', 0)}**",
        f"- Eligibility：**{counts.get('eligibility_selected', 0)}** — Eligible {counts.get('eligible', 0)} / Review {counts.get('review_required', 0)} / Hard reject {counts.get('hard_rejected', 0)}",
        f"- Fast benchmark：**{counts.get('fast_benchmarked', 0)}**",
        f"- Initial Deep：**{counts.get('deep_initial_benchmarked', counts.get('deep_benchmarked', 0))}**",
        f"- Deep refill：**{counts.get('deep_refill_benchmarked', 0)}** candidates / **{counts.get('deep_refill_rounds', 0)}** rounds",
        f"- Deep total：**{counts.get('deep_benchmarked', 0)}** — reused {counts.get('deep_reused_samples', 0)} / new {counts.get('deep_new_samples', 0)} samples",
        f"- Reality tested：**{counts.get('reality_tested', 0)}** — passed {counts.get('reality_passed', 0)}",
        f"- Adaptive stop reason：`{counts.get('adaptive_refill_stop_reason') or refill.get('stop_reason') or 'unknown'}`",
        f"- Final selectable：**{counts.get('selectable', 0)} / {counts.get('selectable_target', 5)}**",
        "",
    ])

    source_errors = coverage.get("source_errors") or []
    if source_errors:
        lines.extend(["### 数据源限制", ""])
        for item in source_errors:
            lines.append(f"- `{item}`")
        lines.append("")

    lines.extend([
        "## H. 全部比较证据",
        "",
        "该表用于审计；非 SELECTABLE 项只作为对照，不得被模型包装成推荐候选。",
        "",
        "| Rank | Domain | Final / Policy | Protocol | TLS/ALPN | Reality | P50 | P95 | MAD | Network | Front door | ASN / org | vs current P50 |",
        "|---:|---|---|---|---|---|---:|---:|---:|---|---|---|---:|",
    ])
    for row in comparison:
        lines.append(
            "| {rank} | `{host}` | `{final}` / `{policy}` | `{protocol}` | `{tlsver}` | `{reality}` | {p50} | {p95} | {mad} | `{network}` | `{front}` | `{asn}` | {improve} |".format(
                rank=row.get("recommendation_rank", "?"),
                host=row.get("hostname", "unknown"),
                final=row.get("final_state", "unknown"),
                policy=row.get("policy_eligibility", row.get("eligibility", "unknown")),
                protocol=_protocol_label(row),
                tlsver=_tls_versions(row),
                reality=_reality(row),
                p50=_fmt(row.get("p50_ms"), " ms"),
                p95=_fmt(row.get("p95_ms"), " ms"),
                mad=_fmt(row.get("mad_ms"), " ms"),
                network=_network_affinity(row),
                front=_front(row),
                asn=_asn_org(row).replace("|", "/"),
                improve=_fmt(row.get("incumbent_p50_improvement_pct"), "%"),
            )
        )
    if len({r.get("hostname") for r in comparison if r.get("hostname")}) < 5:
        lines.extend(["", "> `INSUFFICIENT_COMPARISON_DOMAINS`: 少于五个不同的已测域名；未伪造表格行。"])

    warnings = result.get("warnings") or []
    if warnings:
        lines.extend(["", "## I. Run warnings", ""])
        for item in warnings:
            lines.append(f"- `{item}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
