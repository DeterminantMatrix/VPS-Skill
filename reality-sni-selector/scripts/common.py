#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import os
import re
import statistics
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HOST_RE = re.compile(r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
SERVICE_LABELS = {"smtp", "imap", "mail", "mx", "ns", "ftp", "vpn", "admin", "cpanel", "autodiscover", "pop", "pop3"}
TWO_LEVEL_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "org.au", "edu.au", "gov.au",
    "co.jp", "ac.jp", "go.jp", "com.sg", "org.sg", "edu.sg", "gov.sg", "com.hk",
    "org.hk", "edu.hk", "gov.hk", "co.nz", "org.nz", "ac.nz", "com.br", "org.br",
}

JOB_SCHEMA_VERSION = 4
WORKER_PROTOCOL = 4
PROFILE_NAME = "target-measured-v4"
TARGET_WORKER_FILES = (
    "common.py",
    "target_discovery.py",
    "target_probe.py",
    "benchmark.py",
    "reality_selftest.py",
    "target_worker.py",
)


def validate_hostname(value: str) -> str:
    value = (value or "").strip().rstrip(".").lower()
    try:
        ascii_value = value.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("invalid hostname") from exc
    if not HOST_RE.fullmatch(ascii_value):
        raise ValueError(f"invalid hostname: {value!r}")
    return ascii_value


def is_service_hostname(hostname: str) -> bool:
    return hostname.split(".", 1)[0].lower() in SERVICE_LABELS


def is_public_ipv4(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return isinstance(ip, ipaddress.IPv4Address) and ip.is_global


def registrable_domain(hostname: str) -> str:
    labels = validate_hostname(hostname).split(".")
    if len(labels) <= 2:
        return ".".join(labels)
    last2 = ".".join(labels[-2:])
    if last2 in TWO_LEVEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return last2


def same_site(a: str, b: str) -> bool:
    try:
        return registrable_domain(a) == registrable_domain(b)
    except ValueError:
        return False


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    data = sorted(float(v) for v in values)
    if len(data) == 1:
        return data[0]
    pos = (len(data) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return data[lo]
    return data[lo] + (data[hi] - data[lo]) * (pos - lo)


def mad(values: list[float]) -> float | None:
    if not values:
        return None
    med = statistics.median(values)
    return statistics.median(abs(v - med) for v in values)


def stats(values: list[float], include_tail: bool = True) -> dict[str, float | None]:
    if not values:
        return {"p50_ms": None, "p90_ms": None, "p95_ms": None, "max_ms": None, "mad_ms": None}
    result: dict[str, float | None] = {
        "p50_ms": round(percentile(values, 0.50) or 0.0, 3),
        "p90_ms": None,
        "p95_ms": None,
        "max_ms": round(max(values), 3),
        "mad_ms": round(mad(values) or 0.0, 3),
    }
    if include_tail:
        result["p90_ms"] = round(percentile(values, 0.90) or 0.0, 3)
        result["p95_ms"] = round(percentile(values, 0.95) or 0.0, 3)
    return result


def atomic_write_json(path: Path, payload: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def read_json_stdin(max_bytes: int = 2_000_000) -> Any:
    data = os.read(0, max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("job too large")
    return json.loads(data.decode("utf-8", errors="strict"))


def fetch_bytes(url: str, *, timeout: float = 8.0, max_bytes: int = 1_000_000, headers: dict[str, str] | None = None, data: bytes | None = None) -> bytes:
    request = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": "reality-sni-selector/4", **(headers or {})},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        chunk = response.read(max_bytes + 1)
    if len(chunk) > max_bytes:
        raise ValueError("response too large")
    return chunk


def fetch_json(url: str, *, timeout: float = 8.0, max_bytes: int = 1_000_000, headers: dict[str, str] | None = None, data: bytes | None = None) -> Any:
    raw = fetch_bytes(url, timeout=timeout, max_bytes=max_bytes, headers=headers, data=data)
    return json.loads(raw.decode("utf-8", errors="replace"))


def hostname_from_url(value: str) -> str | None:
    try:
        parsed = urllib.parse.urlparse(value.strip())
        host = parsed.hostname
        return validate_hostname(host) if host else None
    except (ValueError, AttributeError):
        return None


def source_priority(sources: list[str]) -> int:
    order = {"incumbent": 0, "seed": 1, "wikidata": 2, "osm": 3, "openalex": 4, "ct": 5}
    return min((order.get(s, 9) for s in sources), default=9)


def policy_priority(state: str | None) -> int:
    return {
        "ELIGIBLE": 0,
        "REVIEW_REQUIRED": 1,
        "BASELINE_ONLY": 2,
        "HARD_REJECTED": 9,
    }.get(str(state or ""), 8)


def edge_priority(front_door: str) -> int:
    return {
        "DIRECT_CONFIRMED": 0,
        "DIRECT_LIKELY": 1,
        "UNKNOWN_EDGE_EVIDENCE": 2,
        "UNKNOWN_TOOLING": 3,
        "SHARED_PLATFORM_CONFIRMED": 9,
        "PUBLIC_CDN_CONFIRMED": 10,
        "PUBLIC_CDN": 10,
    }.get(front_door, 8)


def compute_worker_manifest(directory: Path) -> str:
    """Hash the fixed target-worker file set in a stable order."""
    digest = hashlib.sha256()
    for name in TARGET_WORKER_FILES:
        path = directory / name
        if not path.is_file():
            raise FileNotFoundError(name)
        data = path.read_bytes()
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(data)).encode("ascii"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()
