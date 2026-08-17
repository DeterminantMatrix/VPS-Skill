#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from common import atomic_write_json
from report import build_decision_view, render_report


def postprocess_run(run_dir: Path) -> bool:
    """Derive v4.5 decision artifacts from already target-measured evidence."""
    result_path = run_dir / "target-result.json"
    if not result_path.is_file():
        return False
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        return False
    view = build_decision_view(result)
    atomic_write_json(run_dir / "decision-summary.json", view.get("decision_summary", {}))
    atomic_write_json(
        run_dir / "top5.json",
        {
            "status": result.get("status"),
            "coverage": result.get("coverage", {}),
            "decision_summary": view.get("decision_summary", {}),
            "network_affinity_search": result.get("network_affinity_search", {}),
            "candidate_discovery": result.get("candidate_discovery", {}),
            "top5": view.get("top5", []),
            "preliminary_top5": result.get("preliminary_top5", []),
            "comparison": view.get("comparison", []),
        },
    )
    (run_dir / "report.md").write_text(render_report(result), encoding="utf-8")
    return True
