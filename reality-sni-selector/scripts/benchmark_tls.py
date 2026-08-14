#!/usr/bin/env python3
"""Rotating TCP/TLS-only benchmark for REALITY target finalists."""

from __future__ import annotations

import argparse
import json
import math
import socket
import ssl
import statistics
import time
from datetime import datetime, timezone


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("empty values")
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def resolve(domain: str, port: int, family_name: str) -> tuple[int, tuple, str]:
    family = socket.AF_INET if family_name == "ipv4" else socket.AF_INET6
    infos = socket.getaddrinfo(domain, port, family=family, type=socket.SOCK_STREAM)
    if not infos:
        raise OSError("no address returned")
    af, socktype, proto, _, sockaddr = infos[0]
    return af, sockaddr, sockaddr[0]


def handshake(domain: str, af: int, sockaddr: tuple, timeout: float) -> dict[str, object]:
    raw = socket.socket(af, socket.SOCK_STREAM)
    raw.settimeout(timeout)
    try:
        tcp_started = time.perf_counter()
        raw.connect(sockaddr)
        tcp_ms = (time.perf_counter() - tcp_started) * 1000

        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.set_alpn_protocols(["h2"])
        tls_started = time.perf_counter()
        with context.wrap_socket(raw, server_hostname=domain) as tls_sock:
            tls_ms = (time.perf_counter() - tls_started) * 1000
            version = tls_sock.version() or "unknown"
            alpn = tls_sock.selected_alpn_protocol() or "none"
            if version != "TLSv1.3" or alpn != "h2":
                raise ssl.SSLError(f"unexpected profile: {version}, ALPN={alpn}")
            return {
                "ok": True,
                "tcp_ms": round(tcp_ms, 3),
                "tls_ms": round(tls_ms, 3),
                "tls_version": version,
                "alpn": alpn,
            }
    except Exception as exc:
        try:
            raw.close()
        except OSError:
            pass
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500]}


def summarize(rows: list[dict[str, object]], remote_ip: str) -> dict[str, object]:
    good = [row for row in rows if row.get("ok") is True]
    tcp = [float(row["tcp_ms"]) for row in good]
    tls = [float(row["tls_ms"]) for row in good]
    result: dict[str, object] = {
        "attempts": len(rows),
        "successes": len(good),
        "success_rate": round(len(good) / len(rows), 4) if rows else 0.0,
        "remote_ip": remote_ip,
    }
    if good:
        result.update({
            "tcp_p50_ms": round(statistics.median(tcp), 3),
            "tcp_p95_ms": round(percentile(tcp, 0.95), 3),
            "tls_p50_ms": round(statistics.median(tls), 3),
            "tls_p95_ms": round(percentile(tls, 0.95), 3),
            "tls_max_ms": round(max(tls), 3),
        })
    errors = [str(row.get("error")) for row in rows if row.get("ok") is not True]
    if errors:
        result["errors"] = errors[:5]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark fresh TCP and TLS handshakes without HTTP page downloads.")
    parser.add_argument("domains", nargs="+")
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--pace", type=float, default=0.25)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--family", choices=("ipv4", "ipv6"), default="ipv4")
    args = parser.parse_args()
    if not 2 <= args.rounds <= 30:
        parser.error("rounds must be 2..30")
    if not 0 <= args.pace <= 5:
        parser.error("pace must be 0..5 seconds")

    domains = list(dict.fromkeys(d.strip().lower().rstrip(".") for d in args.domains if d.strip()))
    if len(domains) < 2:
        parser.error("provide at least two unique domains")

    resolved: dict[str, tuple[int, tuple, str] | None] = {}
    resolve_errors: dict[str, str] = {}
    for domain in domains:
        try:
            resolved[domain] = resolve(domain, args.port, args.family)
        except Exception as exc:
            resolved[domain] = None
            resolve_errors[domain] = f"{type(exc).__name__}: {exc}"[:500]

    rows: dict[str, list[dict[str, object]]] = {domain: [] for domain in domains}
    for round_no in range(args.rounds):
        for step in range(len(domains)):
            domain = domains[(round_no + step) % len(domains)]
            target = resolved[domain]
            if target is None:
                rows[domain].append({"ok": False, "error": resolve_errors[domain]})
            else:
                af, sockaddr, _ = target
                row = handshake(domain, af, sockaddr, args.timeout)
                row["round"] = round_no + 1
                rows[domain].append(row)
            if args.pace:
                time.sleep(args.pace)

    summary: dict[str, object] = {}
    for domain in domains:
        target = resolved[domain]
        remote_ip = target[2] if target else ""
        summary[domain] = summarize(rows[domain], remote_ip)

    print(json.dumps({
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "mode": "TCP connect + TLS handshake only; no HTTP request",
            "family": args.family,
            "rounds": args.rounds,
            "pace_seconds": args.pace,
        },
        "summary": summary,
    }, ensure_ascii=False, indent=2))

    return 0 if all(int(item["successes"]) == args.rounds for item in summary.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
