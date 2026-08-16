#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
import socket
import ssl
import subprocess
import time
from collections import Counter
from typing import Any, Callable
from urllib.parse import urlparse

from common import is_public_ipv4, same_site, validate_hostname

PUBLIC_CDN_CNAME_PATTERNS = [
    ("CloudFront", re.compile(r"(?:^|\.)cloudfront\.net$", re.I)),
    ("Akamai", re.compile(r"(?:^|\.)(?:akamaiedge\.net|edgekey\.net|edgesuite\.net|akamaitechnologies\.com)$", re.I)),
    ("Fastly", re.compile(r"(?:^|\.)fastly\.net$", re.I)),
    ("Azure CDN", re.compile(r"(?:^|\.)(?:azureedge\.net|azurefd\.net)$", re.I)),
    ("CDN77", re.compile(r"(?:^|\.)(?:cdn77\.org|cdn77\.com)$", re.I)),
    ("Netlify", re.compile(r"(?:^|\.)(?:netlify\.global|netlify\.app)$", re.I)),
    ("Vercel", re.compile(r"(?:^|\.)vercel-dns(?:-[^.]+)?\.com$", re.I)),
    ("Vercel", re.compile(r"(?:^|\.)vercel\.app$", re.I)),
    ("Imperva", re.compile(r"(?:^|\.)(?:incapdns\.net|impervadns\.net)$", re.I)),
    ("Cloudflare", re.compile(r"(?:^|\.)(?:cloudflare\.net|cdn\.cloudflare\.net)$", re.I)),
]

SHARED_PLATFORM_CNAME_PATTERNS = [
    ("Pantheon", re.compile(r"(?:^|\.)(?:pantheonsite\.io|pantheon\.io|gotpantheon\.com)$", re.I)),
]

PUBLIC_EDGE_ORG_PATTERNS = [
    ("Cloudflare", re.compile(r"\bcloudflare\b", re.I)),
    ("Fastly", re.compile(r"\bfastly\b", re.I)),
    ("Akamai", re.compile(r"\bakamai\b", re.I)),
    ("Imperva", re.compile(r"\b(?:imperva|incapsula)\b", re.I)),
    ("CDN77", re.compile(r"\bcdn77\b", re.I)),
]

SHARED_PLATFORM_ORG_PATTERNS = [
    ("Pantheon", re.compile(r"\bpantheon\b", re.I)),
]

HEADER_ALLOWLIST = {
    "server", "location", "via", "x-cache", "x-served-by", "x-vercel-id", "x-amz-cf-id", "cf-ray", "x-cdn",
    "x-pantheon-styx-hostname", "x-pantheon-endpoint", "x-pantheon-edge-server", "x-varnish", "age",
}


def resolve_ipv4_observations(hostname: str, observations: int = 2, interval: float = 0.15) -> dict[str, Any]:
    observed: list[list[str]] = []
    errors: list[str] = []
    for idx in range(observations):
        try:
            infos = socket.getaddrinfo(hostname, 443, socket.AF_INET, socket.SOCK_STREAM)
            ips = sorted({item[4][0] for item in infos if is_public_ipv4(item[4][0])})
            observed.append(ips)
        except OSError as exc:
            observed.append([])
            errors.append(type(exc).__name__)
        if idx + 1 < observations:
            time.sleep(interval)
    counts = Counter(ip for row in observed for ip in row)
    common = sorted(ip for ip, count in counts.items() if count >= max(1, (observations + 1) // 2))
    union = sorted(counts)
    volatile = len({tuple(row) for row in observed}) > 1
    return {"observations": observed, "common_ipv4": common or union, "union_ipv4": union, "volatile": volatile, "errors": errors}


def dig_cname(hostname: str, timeout: float = 4.0) -> tuple[list[str], str]:
    dig = shutil.which("dig")
    if not dig:
        return [], "missing"
    try:
        proc = subprocess.run(
            [dig, "+time=2", "+tries=1", "+short", "CNAME", hostname],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        names = []
        for line in proc.stdout.splitlines():
            raw = line.strip().rstrip(".")
            if not raw:
                continue
            try:
                names.append(validate_hostname(raw))
            except ValueError:
                continue
        return sorted(set(names)), "dig"
    except (OSError, subprocess.TimeoutExpired):
        return [], "error"


def _flatten_name(parts: Any) -> str:
    if not isinstance(parts, tuple):
        return ""
    values = []
    for rdn in parts:
        for key, value in rdn:
            values.append(f"{key}={value}")
    return ", ".join(values)


def tls_probe_ip(hostname: str, ip: str, timeout: float = 5.0) -> dict[str, Any]:
    start = time.perf_counter()
    context = ssl.create_default_context()
    try:
        context.set_alpn_protocols(["h2", "http/1.1"])
    except NotImplementedError:
        pass
    try:
        with socket.create_connection((ip, 443), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=hostname) as sock:
                elapsed = (time.perf_counter() - start) * 1000.0
                cert = sock.getpeercert() or {}
                not_after = cert.get("notAfter")
                days_remaining = None
                if not_after:
                    try:
                        days_remaining = round((ssl.cert_time_to_seconds(not_after) - time.time()) / 86400.0, 2)
                    except Exception:
                        pass
                return {
                    "success": True,
                    "ip": ip,
                    "elapsed_ms": round(elapsed, 3),
                    "tls_version": sock.version(),
                    "alpn": sock.selected_alpn_protocol(),
                    "certificate": {
                        "subject": _flatten_name(cert.get("subject")),
                        "issuer": _flatten_name(cert.get("issuer")),
                        "san": [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"][:100],
                        "not_before": cert.get("notBefore"),
                        "not_after": not_after,
                        "days_remaining": days_remaining,
                    },
                }
    except ssl.SSLCertVerificationError as exc:
        message = str(exc).lower()
        return {
            "success": False,
            "ip": ip,
            "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3),
            "error": "CERT_IDENTITY" if "hostname mismatch" in message else "CERT_INVALID",
        }
    except ssl.SSLError:
        return {"success": False, "ip": ip, "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3), "error": "TLS_ERROR"}
    except (OSError, TimeoutError):
        return {"success": False, "ip": ip, "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3), "error": "CONNECT_ERROR"}


def http_head_ip(hostname: str, ip: str, timeout: float = 6.0, max_header_bytes: int = 32768) -> dict[str, Any]:
    context = ssl.create_default_context()
    try:
        context.set_alpn_protocols(["http/1.1"])
    except NotImplementedError:
        pass
    start = time.perf_counter()
    try:
        with socket.create_connection((ip, 443), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=hostname) as sock:
                request = f"HEAD / HTTP/1.1\r\nHost: {hostname}\r\nUser-Agent: reality-sni-selector/4\r\nConnection: close\r\n\r\n".encode("ascii")
                sock.sendall(request)
                buf = bytearray()
                while b"\r\n\r\n" not in buf and len(buf) < max_header_bytes:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    buf.extend(chunk)
        text = bytes(buf).decode("iso-8859-1", errors="replace")
        head = text.split("\r\n\r\n", 1)[0]
        lines = head.split("\r\n")
        status = None
        if lines and lines[0].startswith("HTTP/"):
            parts = lines[0].split()
            if len(parts) >= 2 and parts[1].isdigit():
                status = int(parts[1])
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            if key in HEADER_ALLOWLIST:
                headers[key] = value.strip()[:500]
        return {"success": True, "status": status, "headers": headers, "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3)}
    except Exception as exc:
        return {
            "success": False,
            "status": None,
            "headers": {},
            "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3),
            "error": type(exc).__name__,
        }


def classify_network_organization(ip_metadata: dict[str, Any] | None) -> tuple[str | None, str | None, str | None]:
    if not isinstance(ip_metadata, dict):
        return None, None, None
    organization = str(ip_metadata.get("organization") or ip_metadata.get("org") or "")
    for provider, pattern in SHARED_PLATFORM_ORG_PATTERNS:
        if pattern.search(organization):
            return "SHARED_PLATFORM_CONFIRMED", provider, f"network_org:{organization[:160]}"
    for provider, pattern in PUBLIC_EDGE_ORG_PATTERNS:
        if pattern.search(organization):
            return "PUBLIC_CDN_CONFIRMED", provider, f"network_org:{organization[:160]}"
    return None, None, None


def classify_front_door(
    hostname: str,
    cnames: list[str],
    cname_backend: str,
    head: dict[str, Any],
    ip_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence: list[str] = []

    for cname in cnames:
        for provider, pattern in PUBLIC_CDN_CNAME_PATTERNS:
            if pattern.search(cname):
                return {"class": "PUBLIC_CDN_CONFIRMED", "provider": provider, "platform": None, "evidence": [f"cname:{cname}"]}
        for platform, pattern in SHARED_PLATFORM_CNAME_PATTERNS:
            if pattern.search(cname):
                return {"class": "SHARED_PLATFORM_CONFIRMED", "provider": None, "platform": platform, "evidence": [f"cname:{cname}"]}

    for platform, pattern in SHARED_PLATFORM_CNAME_PATTERNS:
        if pattern.search(hostname):
            return {"class": "SHARED_PLATFORM_CONFIRMED", "provider": None, "platform": platform, "evidence": [f"hostname:{hostname}"]}

    headers = head.get("headers") or {}
    server = headers.get("server", "").lower()
    if "x-pantheon-styx-hostname" in headers or "x-pantheon-endpoint" in headers or "x-pantheon-edge-server" in headers:
        pantheon_headers = [f"header:{key}" for key in ("x-pantheon-styx-hostname", "x-pantheon-endpoint", "x-pantheon-edge-server") if key in headers]
        return {"class": "SHARED_PLATFORM_CONFIRMED", "provider": None, "platform": "Pantheon", "evidence": pantheon_headers}
    if "cloudflare" in server or "cf-ray" in headers:
        return {"class": "PUBLIC_CDN_CONFIRMED", "provider": "Cloudflare", "platform": None, "evidence": ["header:cloudflare"]}
    if "vercel" in server or "x-vercel-id" in headers:
        return {"class": "PUBLIC_CDN_CONFIRMED", "provider": "Vercel", "platform": None, "evidence": ["header:vercel"]}
    if "x-amz-cf-id" in headers:
        return {"class": "PUBLIC_CDN_CONFIRMED", "provider": "CloudFront", "platform": None, "evidence": ["header:x-amz-cf-id"]}
    if "fastly" in server or "fastly" in headers.get("via", "").lower():
        return {"class": "PUBLIC_CDN_CONFIRMED", "provider": "Fastly", "platform": None, "evidence": ["header:fastly"]}

    network_class, network_name, network_evidence = classify_network_organization(ip_metadata)
    if network_class == "SHARED_PLATFORM_CONFIRMED":
        return {"class": network_class, "provider": None, "platform": network_name, "evidence": [network_evidence]}
    if network_class == "PUBLIC_CDN_CONFIRMED":
        return {"class": network_class, "provider": network_name, "platform": None, "evidence": [network_evidence]}

    if cname_backend == "missing":
        return {"class": "UNKNOWN_TOOLING", "provider": None, "platform": None, "evidence": ["cname_backend_missing"]}
    if cname_backend == "error":
        return {"class": "UNKNOWN_EDGE_EVIDENCE", "provider": None, "platform": None, "evidence": ["cname_query_error"]}
    if not head.get("success"):
        return {"class": "UNKNOWN_EDGE_EVIDENCE", "provider": None, "platform": None, "evidence": ["http_head_unavailable"]}
    if not cnames:
        return {"class": "DIRECT_LIKELY", "provider": None, "platform": None, "evidence": ["no_cname_observed", "head_observed"]}
    if all(same_site(hostname, cname) for cname in cnames):
        return {"class": "DIRECT_LIKELY", "provider": None, "platform": None, "evidence": ["same_site_cname", "head_observed"]}
    evidence.append("external_unknown_cname")
    return {"class": "UNKNOWN_EDGE_EVIDENCE", "provider": None, "platform": None, "evidence": evidence}


def gate_candidate(
    candidate: dict[str, Any],
    *,
    dns_observations: int = 2,
    tls_samples_per_ip: int = 2,
    timeout: float = 5.0,
    ip_metadata_lookup: Callable[[str], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    hostname = candidate["hostname"]
    dns = resolve_ipv4_observations(hostname, observations=dns_observations)
    hard: list[str] = []
    review: list[str] = []
    warnings: list[str] = []
    ips = dns["common_ipv4"]
    if not ips:
        hard.append("HARD:NO_PUBLIC_IPV4")
        return {
            **candidate,
            "dns": dns,
            "tls": [],
            "http": None,
            "front_door": {"class": "UNKNOWN_TOOLING", "provider": None, "platform": None, "evidence": []},
            "hard_rejections": hard,
            "review": review,
            "warnings": warnings,
            "eligibility": "HARD_REJECTED",
        }
    if dns.get("volatile"):
        review.append("REVIEW:DNS_VOLATILE")

    tls_rows: list[dict[str, Any]] = []
    for ip in ips:
        for _ in range(tls_samples_per_ip):
            tls_rows.append(tls_probe_ip(hostname, ip, timeout=timeout))
            time.sleep(0.05)
    by_ip: dict[str, list[dict[str, Any]]] = {ip: [r for r in tls_rows if r["ip"] == ip] for ip in ips}
    for ip, rows in by_ip.items():
        success = [r for r in rows if r.get("success")]
        errors = {r.get("error") for r in rows if not r.get("success")}
        if "CERT_IDENTITY" in errors:
            hard.append("HARD:CERT_IDENTITY")
        elif "CERT_INVALID" in errors:
            hard.append("HARD:CERT_INVALID")
        elif not success:
            hard.append("HARD:TLS_UNREACHABLE")
        elif len(success) < len(rows):
            review.append("REVIEW:TCP_TLS_UNSTABLE_GATE")

    successes = [r for r in tls_rows if r.get("success")]
    if successes and not any(r.get("tls_version") == "TLSv1.3" for r in successes):
        warnings.append("WARN:TLS12_ONLY")
    if successes and not any(r.get("alpn") == "h2" for r in successes):
        warnings.append("WARN:NO_H2")

    cnames, cname_backend = dig_cname(hostname)
    heads: list[dict[str, Any]] = []
    front_rows: list[dict[str, Any]] = []
    network_metadata: dict[str, Any] = {}
    if successes:
        for ip in ips:
            meta = ip_metadata_lookup(ip) if ip_metadata_lookup else None
            if meta:
                network_metadata[ip] = meta
            head = http_head_ip(hostname, ip, timeout=min(6.0, timeout + 1.0))
            head["ip"] = ip
            heads.append(head)
            front_rows.append(classify_front_door(hostname, cnames, cname_backend, head, meta))
            if head.get("status") == 429:
                break
    else:
        meta = ip_metadata_lookup(ips[0]) if ip_metadata_lookup else None
        if meta:
            network_metadata[ips[0]] = meta
        heads.append({"success": False, "headers": {}, "status": None, "ip": ips[0]})
        front_rows.append(classify_front_door(hostname, cnames, cname_backend, heads[0], meta))

    shared = next((r for r in front_rows if r.get("class") == "SHARED_PLATFORM_CONFIRMED"), None)
    public = next((r for r in front_rows if r.get("class") == "PUBLIC_CDN_CONFIRMED"), None)
    if public:
        front = dict(public)
    elif shared:
        front = dict(shared)
    elif any(r.get("class") == "UNKNOWN_EDGE_EVIDENCE" for r in front_rows):
        front = {
            "class": "UNKNOWN_EDGE_EVIDENCE",
            "provider": None,
            "platform": None,
            "evidence": sorted({e for r in front_rows for e in r.get("evidence", [])}),
        }
    elif any(r.get("class") == "UNKNOWN_TOOLING" for r in front_rows):
        front = {
            "class": "UNKNOWN_TOOLING",
            "provider": None,
            "platform": None,
            "evidence": sorted({e for r in front_rows for e in r.get("evidence", [])}),
        }
    else:
        front = {
            "class": "DIRECT_LIKELY",
            "provider": None,
            "platform": None,
            "evidence": sorted({e for r in front_rows for e in r.get("evidence", [])}),
        }
    front["cnames"] = cnames
    front["cname_backend"] = cname_backend
    front["network_metadata"] = network_metadata

    if front["class"] == "PUBLIC_CDN_CONFIRMED":
        hard.append("HARD:KNOWN_PUBLIC_CDN")
    elif front["class"] == "SHARED_PLATFORM_CONFIRMED":
        hard.append("HARD:KNOWN_SHARED_PLATFORM")
    elif front["class"] in {"UNKNOWN_TOOLING", "UNKNOWN_EDGE_EVIDENCE"}:
        review.append("REVIEW:EDGE_UNKNOWN")

    for head in heads:
        status = head.get("status")
        if status == 403:
            warnings.append("WARN:HTTP_403")
        elif status == 405:
            warnings.append("WARN:HTTP_405")
        elif status == 429:
            warnings.append("WARN:HTTP_429")
        elif isinstance(status, int) and status >= 500:
            warnings.append("WARN:HTTP_5XX")
        location = (head.get("headers") or {}).get("location")
        if location:
            try:
                redirect_host = urlparse(location).hostname
                if redirect_host and not same_site(hostname, redirect_host):
                    review.append("REVIEW:CROSS_SITE_REDIRECT")
            except ValueError:
                pass

    hard = sorted(set(hard))
    review = sorted(set(review))
    warnings = sorted(set(warnings))
    eligibility = "HARD_REJECTED" if hard else "REVIEW_REQUIRED" if review else "ELIGIBLE"
    return {
        **candidate,
        "dns": dns,
        "current_ipv4": ips,
        "tls": tls_rows,
        "http": heads,
        "front_door": front,
        "hard_rejections": hard,
        "review": review,
        "warnings": warnings,
        "eligibility": eligibility,
    }
