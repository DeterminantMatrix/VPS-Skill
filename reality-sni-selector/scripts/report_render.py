#!/usr/bin/env python3
from __future__ import annotations
from typing import Any

from decision_view import build_decision_view
from report_format import (
    _asn_org,
    _assessment_metrics,
    _certificate_validity,
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
    refill = (result.get("reality") or {}).get("adaptive_refill") or {}

    best = top[0] if top else None
    current_host = assessment.get("hostname") or frozen.get("incumbent") or "unknown"
    current_row = next((row for row in comparison if row.get("hostname") == current_host), _current_card_row(assessment))
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
        f"- 最终 SELECTABLE 独立域名家族：**{counts.get('selectable_families', counts.get('selectable', len(top)))} / {counts.get('selectable_target', 5)}**",
        f"- 质量目标：**{'已达到' if decision.get('quality_target_met') else '未达到'}**（目标 P50 `{(frozen.get('profile') or {}).get('latency_target_ms', 60)} ms`；未达到时仍会继续 bounded refill/search，直到耗尽或命中上限）。",
        f"- 置信度：Candidate **{_confidence_zh(decision.get('candidate_confidence'))}** / Run Coverage **{_confidence_zh(decision.get('run_coverage_confidence', decision.get('search_confidence')))}** / Global Optimality **{_confidence_zh(decision.get('global_optimality_confidence'))}** / Overall **{_confidence_zh(decision.get('overall_recommendation_confidence'))}**",
        "",
        "## B. 当前 SNI 健康卡",
        "",
        "| 项目 | 当前结果 |",
        "|---|---|",
        f"| SNI | `{current_host}` |",
        f"| 最终评价 | **{current_verdict}** (`{assessment.get('code', 'UNABLE_TO_ASSESS')}`) |",
        f"| REALITY Protocol | `{(assessment.get('metrics') or {}).get('protocol_compliance', {}).get('state', 'UNKNOWN')}` — {_protocol_details(current_row)} |",
        f"| TLS / ALPN | `{_tls_versions(current_row)}` |",
        f"| 证书有效期 | {_certificate_validity(current_row)} |",
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
        "Top 5 默认要求 5 个不同 registrable-domain family；同一根域的 `www`/apex 只作为 family alternative，不重复占主表位置。",
        "",
        "| # | SNI / Family | 梯队 | 推荐 | Protocol | TLS / ALPN | 证书有效期 | Policy | Reality | P50 / P95 | TLS可靠性 / 延迟一致性 | Network | Front Door | 风险 | 综合置信度 |",
        "|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ])
    for row in top:
        lines.append(
            "| {rank} | `{host}` | `{tier}` | **{grade} {label}** | `{protocol}` | `{tlsver}` | {cert_validity} | `{policy}` | `{reality}` | {p50} / {p95} | `{tls_rel}` / `{stability}` | `{network}` | `{front}` | `{risk}` | `{confidence}` |".format(
                rank=row.get("recommendation_rank", "?"),
                host=f"{row.get('hostname', 'unknown')} / {row.get('candidate_family') or row.get('hostname', 'unknown')}",
                tier=row.get("recommendation_tier", "unknown"),
                grade=row.get("recommendation_grade", "?"),
                label=row.get("recommendation_label", ""),
                protocol=_protocol_label(row),
                tlsver=_tls_versions(row),
                cert_validity=_certificate_validity(row),
                policy=_policy_label(row),
                reality=_reality_label(row),
                p50=_fmt(row.get("p50_ms"), " ms"),
                p95=_fmt(row.get("p95_ms"), " ms"),
                tls_rel=row.get("tls_reliability_grade", row.get("tls_grade", "unknown")),
                stability=row.get("latency_consistency_grade", row.get("runtime_stability_grade", "unknown")),
                network=_network_affinity(row),
                front=_front(row),
                risk=_risk_zh(row.get("durability_risk")),
                confidence=_confidence_zh(row.get("overall_recommendation_confidence")),
            )
        )
    lines.append("")
    if len(top) < 5:
        lines.append(f"> `FEWER_THAN_FIVE_SELECTABLE_FAMILIES`: 本轮只确认 **{len(top)}** 个完整 SELECTABLE 候选。")
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
            f"- **证书有效期**：{_certificate_validity(row)}。",
            f"- **Safety / Policy**：`{_policy_label(row)}`；Front Door：`{_front(row)}`；ASN/组织：`{_asn_org(row)}`。",
            f"- **Reality**：`{_reality_label(row)}`；Final：`{row.get('final_state') or row.get('final')}`。",
            f"- **Reliability**：TLS transport `{_pct(row.get('success_rate'))}` / grade `{row.get('tls_reliability_grade', row.get('tls_grade', 'unknown'))}`；Reality `{row.get('reality_grade', 'unknown')}`；延迟一致性 `{row.get('latency_consistency_grade', row.get('runtime_stability_grade', 'unknown'))}`。",
            f"- **Performance**：P50 `{_fmt(row.get('p50_ms'), ' ms')}`；P95 `{_fmt(row.get('p95_ms'), ' ms')}`；MAD `{_fmt(row.get('mad_ms'), ' ms')}`；等级 `{row.get('performance_grade', 'unknown')}`。",
            f"- **Network affinity**：`{_network_affinity(row)}`。",
            f"- **Discovery provenance**：lanes `{row.get('lanes') or []}`；sources `{row.get('sources') or []}`。",
            f"- **Operational risk**：`{row.get('durability_risk', 'unknown')}`；这是基于本轮可观察证据的启发式风险，不代表未来可用性保证。",
            f"- **与当前 SNI**：{relation}。",
            f"- **排名理由**：{row.get('ranking_rationale') or '无'}",
            f"- **Family**：`{row.get('candidate_family') or row.get('hostname')}`；同 family 备选 `{row.get('family_alternatives') or []}`。",
            f"- **置信度**：Candidate `{row.get('candidate_confidence', 'LOW')}` / Run Coverage `{row.get('run_coverage_confidence', row.get('search_confidence', 'LOW'))}` / Global Optimality `{row.get('global_optimality_confidence', 'LOW')}` / Overall `{row.get('overall_recommendation_confidence', 'LOW')}`。",
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
        "## F. 搜索质量、来源覆盖与 Network Affinity",
        "",
        f"- Target ingress IPv4：`{(frozen.get('target') or {}).get('inventory_ipv4') or 'unknown'}`；egress IPv4：`{preflight.get('observed_egress_ip') or 'unknown'}`",
        f"- Region：`{frozen.get('region') or 'unknown'}`",
        f"- Profile：`{coverage.get('profile') or (frozen.get('profile') or {}).get('run_mode') or 'unknown'}`",
        f"- Validated breadth：`{coverage.get('breadth_status', coverage.get('status', 'unknown'))}` — **{coverage.get('validated', 0)} / {coverage.get('goal', 'unknown')}**",
        f"- Effective eligible quality：`{coverage.get('quality_status', 'unknown')}` — **{coverage.get('effective_eligible', 0)} / {coverage.get('eligible_goal', 'unknown')}**",
        f"- Combined coverage：`{coverage.get('status', 'unknown')}`；Selection maturity：`{coverage.get('selection_maturity', 'unknown')}`",
        f"- Active discovery lanes：`{coverage.get('active_discovery_lanes') or []}`",
        f"- Validated lane counts：`{coverage.get('lane_counts') or {}}`",
        f"- Run Coverage confidence：**{_confidence_zh(decision.get('run_coverage_confidence', decision.get('search_confidence')))}**",
        f"- Global Optimality confidence：**{_confidence_zh(decision.get('global_optimality_confidence'))}**",
        f"- Search saturation：`{coverage.get('saturation') or {}}`",
        f"- Source lane reserve：`{(coverage.get('source_selection') or {}).get('reserve_actual') or {}}`",
        f"- Validated lane reserve：`{(coverage.get('validated_selection') or {}).get('reserve_actual') or {}}`",
        "",
        "> Institution 是高质量偏好来源，不是候选资格条件。v4.5 同时使用 General Regional、Network Affinity、Institutional 与跨通道 Passive Expansion；最终资格仍由 Protocol / Safety / Reliability / Reality 决定。",
        "",
    ])

    affinity = result.get("network_affinity_search") or {}
    lines.extend([
        "### Network Affinity Search funnel",
        "",
        f"- Target ASN / prefix：`{affinity.get('target_asn') or 'unknown'}` / `{affinity.get('target_prefix') or 'unknown'}`",
        f"- Discovery method：`{affinity.get('method') or 'unknown'}`；active scan：`{affinity.get('active_scan')}`",
        f"- Passive IP sample：**{affinity.get('passive_ips_sampled', 0)}**；affinity discovered：hostnames **{affinity.get('affinity_hostnames_discovered', 0)}** / root domains **{affinity.get('affinity_root_domains_discovered', 0)}**；validated hostnames/families **{affinity.get('affinity_lane_validated', 0)} / {affinity.get('affinity_lane_validated_families', 0)}**",
        f"- SAME_ASN：Gate **{affinity.get('same_asn_gate_seen', 0)} hosts / {affinity.get('same_asn_gate_seen_families', 0)} families** → Eligible **{affinity.get('same_asn_eligible', 0)} / {affinity.get('same_asn_eligible_families', 0)}** → Fast **{affinity.get('same_asn_fast', 0)} / {affinity.get('same_asn_fast_families', 0)}** → Deep **{affinity.get('same_asn_deep', 0)} / {affinity.get('same_asn_deep_families', 0)}** → Reality PASS **{affinity.get('same_asn_reality_passed', 0)} / {affinity.get('same_asn_reality_passed_families', 0)}**",
        f"- SAME_ASN final：SELECTABLE hostnames **{affinity.get('same_asn_selectable_hostnames', affinity.get('same_asn_selectable', 0))}** / families **{affinity.get('same_asn_selectable_families', 0)}** / unique endpoint sets **{affinity.get('same_asn_selectable_endpoints', 0)}**",
        "",
        "> 如果 SAME_ASN 最终为 0，报告必须能区分“被动来源没有发现”与“发现后在 Protocol/Policy/Reality 阶段被淘汰”，不能只显示最终没有同 ASN。",
        "",
        "> Candidate confidence 回答候选自身证据；Run Coverage 回答配置好的 bounded search 是否执行充分；Global Optimality 回答“是否有理由认为已接近整个候选空间的最优解”。命中 hard cap 或来源错误时，Global Optimality 不应轻易为 HIGH。",
        "",
        "## G. 自适应流水线统计",
        "",
        f"- Discovered / validated：**{counts.get('discovered', 0)}**",
        f"- Eligibility：**{counts.get('eligibility_selected', 0)}** — Eligible {counts.get('eligible', 0)} / Review {counts.get('review_required', 0)} / Hard reject {counts.get('hard_rejected', 0)} / Baseline-only {counts.get('baseline_only', 0)}",
        f"- Fast benchmark：**{counts.get('fast_benchmarked', 0)}**",
        f"- Initial Deep：**{counts.get('deep_initial_benchmarked', counts.get('deep_benchmarked', 0))}**",
        f"- Quality extension：Fast **{counts.get('fast_quality_extension_benchmarked', 0)}** / Deep **{counts.get('deep_quality_extension_benchmarked', 0)}**",
        f"- Deep refill：**{counts.get('deep_refill_benchmarked', 0)}** candidates / **{counts.get('deep_refill_rounds', 0)}** rounds",
        f"- Deep total：**{counts.get('deep_benchmarked', 0)}** — reused {counts.get('deep_reused_samples', 0)} / new {counts.get('deep_new_samples', 0)} samples",
        f"- Reality tested：**{counts.get('reality_tested', 0)}** — passed {counts.get('reality_passed', 0)}",
        f"- Adaptive stop reason：`{counts.get('adaptive_refill_stop_reason') or refill.get('stop_reason') or 'unknown'}`",
        f"- Final selectable families：**{counts.get('selectable_families', counts.get('selectable', 0))} / {counts.get('selectable_target', 5)}**",
        f"- Quality target met：`{counts.get('quality_target_met')}`",
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
        "| Rank | Domain | Final / Policy | Protocol | TLS/ALPN | 证书有效期 | Reality | P50 | P95 | MAD | Network | Front door | ASN / org | vs current P50 |",
        "|---:|---|---|---|---|---|---|---:|---:|---:|---|---|---|---:|",
    ])
    for row in comparison:
        lines.append(
            "| {rank} | `{host}` | `{final}` / `{policy}` | `{protocol}` | `{tlsver}` | {cert_validity} | `{reality}` | {p50} | {p95} | {mad} | `{network}` | `{front}` | `{asn}` | {improve} |".format(
                rank=row.get("recommendation_rank", "?"),
                host=f"{row.get('hostname', 'unknown')} / {row.get('candidate_family') or row.get('hostname', 'unknown')}",
                final=row.get("final_state", "unknown"),
                policy=row.get("policy_eligibility", row.get("eligibility", "unknown")),
                protocol=_protocol_label(row),
                tlsver=_tls_versions(row),
                cert_validity=_certificate_validity(row),
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
    families = {r.get("candidate_family") or r.get("hostname") for r in comparison if r.get("hostname")}
    if len(families) < 5:
        lines.extend(["", "> `INSUFFICIENT_COMPARISON_FAMILIES`: 少于五个不同 registrable-domain family 的已测结果；未伪造表格行。"])

    warnings = result.get("warnings") or []
    if warnings:
        lines.extend(["", "## I. Run warnings", ""])
        for item in warnings:
            lines.append(f"- `{item}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
