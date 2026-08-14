#!/usr/bin/env python3
"""Observe approximate TCP activity for a REALITY listener on Linux."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def tcp_passive_opens() -> int:
    lines = Path("/proc/net/snmp").read_text(encoding="ascii").splitlines()
    for index in range(len(lines) - 1):
        if lines[index].startswith("Tcp:") and lines[index + 1].startswith("Tcp:"):
            headers = lines[index].split()[1:]
            values = lines[index + 1].split()[1:]
            return int(dict(zip(headers, values))["PassiveOpens"])
    raise RuntimeError("Tcp PassiveOpens not found in /proc/net/snmp")


def established_on_port(port: int) -> int | None:
    try:
        completed = subprocess.run(
            ["ss", "-Htn", "state", "established", f"sport = :{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except FileNotFoundError:
        return None
    if completed.returncode != 0:
        return None
    return sum(1 for line in completed.stdout.splitlines() if line.strip())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Observe system passive opens and established connections on a port."
    )
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be 1..65535")
    if not 1 <= args.seconds <= 300:
        parser.error("seconds must be 1..300")
    if not 0.2 <= args.interval <= args.seconds:
        parser.error("interval must be 0.2..seconds")

    before = tcp_passive_opens()
    started = time.monotonic()
    samples: list[dict[str, object]] = []
    while True:
        elapsed = time.monotonic() - started
        samples.append(
            {
                "elapsed_seconds": round(elapsed, 3),
                "established_on_port": established_on_port(args.port),
            }
        )
        remaining = args.seconds - elapsed
        if remaining <= 0:
            break
        time.sleep(min(args.interval, remaining))
    after = tcp_passive_opens()
    actual_seconds = time.monotonic() - started
    delta = after - before
    print(
        json.dumps(
            {
                "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                "port": args.port,
                "seconds": round(actual_seconds, 3),
                "system_tcp_passive_opens_delta": delta,
                "system_tcp_passive_opens_per_second": round(
                    delta / actual_seconds, 6
                ),
                "established_samples": samples,
                "caveat": (
                    "PassiveOpens is system-wide and not an exact REALITY connection "
                    "rate; corroborate with per-service or per-port counters."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
