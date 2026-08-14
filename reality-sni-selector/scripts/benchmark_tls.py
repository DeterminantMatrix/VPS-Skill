#!/usr/bin/env python3
"""Small rotating TCP/TLS stability benchmark for REALITY target finalists."""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import statistics
import time
from datetime import datetime, timezone


def family_value(name: str) -> socket.AddressFamily:
    return socket.AF_INET if name == "ipv4" else socket.AF_INET6


def resolve_all(domain: str, port: int, family_name: str) -> list[tuple[int, int, int, tuple, str]]:
    infos = socket.getaddrinfo(domain, port, family=family_value(family_name), type=socket.SOCK_STREAM)
    unique: list[tuple[int, int, int, tuple, str]] = []
    seen: set[str] = set()
    for af, socktype, proto, _, sockaddr in infos:
        ip = sockaddr[0]
        if ip in seen:
            continue
        seen.add(ip)
        unique.append((af, socktype, proto, sockaddr, ip))
    if not unique:
        raise OSError("no address returned")
    return unique


def handshake(domain: str, target: tuple[int, int, int, tuple, str], timeout: float) -> dict[str, object]:
    af, socktype, proto, sockaddr, ip = target
    raw = socket.socket(af, socktype, proto)
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
                "remote_ip": ip,
                "tcp_ms": round(tcp_ms, 3),
                "tls_ms": round(tls_ms, 3),
            }
    except Exception as exc:
        try:
            raw.close()
        except OSError:
            pass
        return {"ok": False, "remote_ip": ip, "error": f"{type(exc).__name__}: {exc}"[:500]}


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    good = [row for row in rows if row.get("ok") is True]
    tcp = [float(row["tcp_ms"]) for row in good]
    tls = [float(row["tls_ms"]) for row in good]
    result: dict[str, object] = {
        "attempts": len(rows),
        "successes": len(good),
        "success_rate": round(len(good) / len(rows), 4) if rows else 0.0,
        "remote_ips": sorted({str(row.get("remote_ip") or "") for row in rows if row.get("remote_ip")}),
    }
    if good:
        result.update({
            "tcp_p50_ms": round(statistics.median(tcp), 3),
            "tcp_worst_ms": round(max(tcp), 3),
            "tls_p50_ms": round(statistics.median(tls), 3),
            "tls_worst_ms": round(max(tls), 3),
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
    if not 3 <= args.rounds <= 30:
        parser.error("rounds must be 3..30")
    if not 0 <= args.pace <= 5:
        parser.error("pace must be 0..5 seconds")

    domains = list(dict.fromkeys(d.strip().lower().rstrip(".") for d in args.domains if d.strip()))
    if len(domains) < 2:
        parser.error("provide at least two unique domains")

    resolved: dict[str, list[tuple[int, int, int, tuple, str]] | None] = {}
    resolve_errors: dict[str, str] = {}
    for domain in domains:
        try:
            resolved[domain] = resolve_all(domain, args.port, args.family)
        except Exception as exc:
            resolved[domain] = None
            resolve_errors[domain] = f"{type(exc).__name__}: {exc}"[:500]

    rows: dict[str, list[dict[str, object]]] = {domain: [] for domain in domains}
    for round_no in range(args.rounds):
        for step in range(len(domains)):
            domain = domains[(round_no + step) % len(domains)]
            targets = resolved[domain]
            if not targets:
                row = {"ok": False, "remote_ip": "", "error": resolve_errors[domain]}
            else:
                target = targets[round_no % len(targets)]
                row = handshake(domain, target, args.timeout)
            row["round"] = round_no + 1
            rows[domain].append(row)
            if args.pace:
                time.sleep(args.pace)

    summary = {domain: summarize(rows[domain]) for domain in domains}
    print(json.dumps({
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "mode": "TCP connect + TLS handshake only; no HTTP request",
            "family": args.family,
            "rounds": args.rounds,
            "pace_seconds": args.pace,
            "statistics": "success rate, median, worst; no p95 from small sample",
        },
        "summary": summary,
    }, ensure_ascii=False, indent=2))

    return 0 if all(int(item["successes"]) == args.rounds for item in summary.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
