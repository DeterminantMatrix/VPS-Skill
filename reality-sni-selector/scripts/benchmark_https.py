#!/usr/bin/env python3
"""Run a paced, rotating HTTPS tournament from the target VPS."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
import subprocess
import time
from datetime import datetime, timezone


DISTRESS_CODES = {403, 429, 500, 502, 503, 504}


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def curl_once(domain: str, family: str, timeout: float) -> dict[str, object]:
    command = [
        "curl",
        "-4" if family == "ipv4" else "-6",
        "-L",
        "-o",
        "/dev/null",
        "-sS",
        "--connect-timeout",
        str(min(5.0, timeout)),
        "--max-time",
        str(timeout),
        "-w",
        "%{http_code}\t%{time_connect}\t%{time_appconnect}\t%{time_total}\t%{remote_ip}\t%{url_effective}",
        f"https://{domain}/",
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout + 3
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "code": "FAIL",
            "connect_ms": 0.0,
            "tls_ms": 0.0,
            "total_ms": 0.0,
            "remote_ip": "",
            "final_url": "",
            "error": f"curl process timeout after {exc.timeout} seconds",
        }
    parts = completed.stdout.strip().split("\t", 5)
    if completed.returncode != 0 or len(parts) != 6:
        return {
            "code": "FAIL",
            "connect_ms": 0.0,
            "tls_ms": 0.0,
            "total_ms": 0.0,
            "remote_ip": "",
            "final_url": "",
            "error": completed.stderr.strip()[:500],
        }
    code, connect, tls, total, remote_ip, final_url = parts
    return {
        "code": code,
        "connect_ms": float(connect) * 1000,
        "tls_ms": float(tls) * 1000,
        "total_ms": float(total) * 1000,
        "remote_ip": remote_ip,
        "final_url": final_url,
        "error": "",
    }


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    tls = [float(row["tls_ms"]) for row in rows if row["code"] != "FAIL"]
    total = [float(row["total_ms"]) for row in rows if row["code"] != "FAIL"]
    result: dict[str, object] = {
        "samples": len(rows),
        "success_200": sum(row["code"] == "200" for row in rows),
        "statuses": sorted({str(row["code"]) for row in rows}),
        "remote_ips": sorted(
            {str(row["remote_ip"]) for row in rows if row["remote_ip"]}
        ),
    }
    if tls:
        result.update(
            {
                "tls_p50_ms": round(statistics.median(tls), 3),
                "tls_p95_ms": round(percentile(tls, 0.95), 3),
                "tls_max_ms": round(max(tls), 3),
                "tls_over_200ms": sum(value > 200 for value in tls),
                "total_p50_ms": round(statistics.median(total), 3),
                "total_p95_ms": round(percentile(total, 0.95), 3),
                "total_max_ms": round(max(total), 3),
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Paced rotating HTTPS benchmark for REALITY SNI finalists."
    )
    parser.add_argument("domains", nargs="+")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--pace", type=float, default=0.5)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--family", choices=("ipv4", "ipv6"), default="ipv4")
    args = parser.parse_args()
    if shutil.which("curl") is None:
        parser.error("curl is required")
    if not 1 <= args.rounds <= 50:
        parser.error("rounds must be 1..50")
    if not 0.1 <= args.pace <= 10:
        parser.error("pace must be 0.1..10 seconds")
    domains = list(dict.fromkeys(item.strip().lower().rstrip(".") for item in args.domains))
    if len(domains) < 2:
        parser.error("provide at least two unique domains")

    rows: dict[str, list[dict[str, object]]] = {domain: [] for domain in domains}
    distress: dict[str, int] = {domain: 0 for domain in domains}
    aborted: dict[str, str] = {}

    for round_no in range(args.rounds):
        for step in range(len(domains)):
            domain = domains[(round_no + step) % len(domains)]
            if domain in aborted:
                continue
            row = curl_once(domain, args.family, args.timeout)
            row["round"] = round_no
            rows[domain].append(row)
            code_text = str(row["code"])
            code = int(code_text) if code_text.isdigit() else 0
            if code in DISTRESS_CODES:
                distress[domain] += 1
                if code == 429 or distress[domain] >= 2:
                    aborted[domain] = f"distress status {code}"
            time.sleep(args.pace)

    output = {
        "window_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "request": "document-only HTTPS GET; browser subresources not fetched",
            "family": args.family,
            "rounds": args.rounds,
            "pace_seconds_between_candidates": args.pace,
            "redirects_followed": True,
        },
        "aborted": aborted,
        "summary": {domain: summarize(domain_rows) for domain, domain_rows in rows.items()},
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 2 if aborted else 0


if __name__ == "__main__":
    raise SystemExit(main())
