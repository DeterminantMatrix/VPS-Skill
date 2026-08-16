#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from decision_view import build_decision_view
from report_render import render_report

__all__ = ["build_decision_view", "render_report", "write_rejections_csv"]


def write_rejections_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["hostname", "stage", "class", "code"])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in writer.fieldnames})
