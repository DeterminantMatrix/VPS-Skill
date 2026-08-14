#!/usr/bin/env python3
"""Minimal REALITY target probe with a strict direct/non-CDN gate."""

from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import shutil
import socket
import ssl
import subprocess
import time
from datetime import datetime, timezone
from urllib.parse import urlparse


CDN_CNAME_RULES = (
    ("cloudfront.net", "Amazon CloudFront"),
    ("elb.amazonaws.com", "AWS shared front door"),
    ("edgekey.net", "Akamai"),
    ("edgesuite.net", "Akamai"),
    ("akamaiedge.net", "Akamai"),
    ("akamai.net", "Akamai"),
    ("fastly.net", "Fastly"),
    ("fastlylb.net", "Fastly"),
    ("azurefd.net", "Azure Front Door"),
    ("azureedge.net", "Azure CDN"),
    ("trafficmanager.net", "Azure shared front door"),
    ("b-cdn.net", "Bunny CDN"),
    ("cdn77.org", "CDN77"),
    ("cdn77.com", "CDN77"),
    ("kxcdn.com", "KeyCDN"),
    ("quic.cloud", "QUIC.cloud"),
    ("vercel-dns.com", "Vercel shared front door"),
    ("netlify.app", "Netlify shared front door"),
    ("googlehosted.com", "Google shared front door"),
    ("googleusercontent.com", "Google shared front door"),
)

STRONG_CDN_ASN_RULES = (
    ("cloudflare", "Cloudflare"),
    ("akamai", "Akamai"),
    ("fastly", "Fastly"),
    ("cdn77", "CDN77"),
    ("bunny", "Bunny CDN"),
    ("stackpath", "StackPath"),
    ("edgecast", "Edgecast"),
)


def certificate_identity(cert: dict, domain: str) -> tuple[str, list[str]]:
    sans = [value.lower() for kind, value in cert.get("subjectAltName", []) if kind == "DNS"]
    domain = domain.lower()
    if domain in sans:
        return "exact", sans
    for san in sans:
        if san.startswith("*."):
            suffix = san[1:]
            if domain.endswith(suffix) and domain.count(".") == san.count("."):
                return "wildcard", sans
    return "verified-other", sans


def run_dig(args: list[str], timeout: float) -> tuple[bool, list[str]]:
    if shutil.which("dig") is None:
        return False, []
    command = ["dig", "+time=2", "+tries=1", "+short", *args]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return False, []
    if completed.returncode != 0:
        return False, []
    lines = [line.strip().strip('"') for line in completed.stdout.splitlines() if line.strip()]
    return True, lines


def cname_chain(domain: str, timeout: float) -> tuple[bool, list[str]]:
    chain: list[str] = []
    current = domain.rstrip(".").lower()
    for _ in range(5):
        ok, lines = run_dig(["CNAME", current], timeout)
        if not ok:
            return False, chain
        if not lines:
            return True, chain
        target = lines[0].rstrip(".").lower()
        if not target or target == current or target in chain:
            return True, chain
        chain.append(target)
        current = target
    return True, chain


def cymru_asn(ip: str, timeout: float) -> tuple[bool, str, str]:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False, "", ""
    if address.version != 4:
        return False, "", ""

    query = ".".join(reversed(ip.split("."))) + ".origin.asn.cymru.com"
    ok, lines = run_dig(["TXT", query], timeout)
    if not ok or not lines:
        return False, "", ""
    fields = [field.strip() for field in lines[0].split("|")]
    if not fields:
        return False, "", ""
    asn = fields[0].replace("AS", "").strip()
    if not asn.isdigit():
        return False, "", ""

    ok_name, name_lines = run_dig(["TXT", f"AS{asn}.asn.cymru.com"], timeout)
    asn_name = ""
    if ok_name and name_lines:
        name_fields = [field.strip() for field in name_lines[0].split("|")]
        if name_fields:
            asn_name = name_fields[-1]
    return True, asn, asn_name


def classify_front_door(domain: str, remote_ip: str, timeout: float) -> dict[str, object]:
    cname_ok, chain = cname_chain(domain, timeout)
    evidence: list[str] = []
    for name in [domain, *chain]:
        lowered = name.lower()
        if lowered.endswith("amazonaws.com") and (".s3" in lowered or "s3-website" in lowered):
            return {
                "status": "cdn",
                "provider": "AWS shared front door",
                "cname_chain": chain,
                "asn": "",
                "asn_name": "",
                "evidence": [f"CNAME/shared service: {name}"],
            }
        for suffix, provider in CDN_CNAME_RULES:
            if lowered == suffix or lowered.endswith("." + suffix):
                return {
                    "status": "cdn",
                    "provider": provider,
                    "cname_chain": chain,
                    "asn": "",
                    "asn_name": "",
                    "evidence": [f"CNAME/shared edge: {name}"],
                }

    asn_ok, asn, asn_name = cymru_asn(remote_ip, timeout) if remote_ip else (False, "", "")
    if asn_ok:
        evidence.append(f"ASN AS{asn} {asn_name}".strip())
        lowered_name = asn_name.lower()
        for keyword, provider in STRONG_CDN_ASN_RULES:
            if keyword in lowered_name:
                return {
                    "status": "cdn",
                    "provider": provider,
                    "cname_chain": chain,
                    "asn": asn,
                    "asn_name": asn_name,
                    "evidence": evidence,
                }

    if cname_ok and asn_ok:
        return {
            "status": "direct",
            "provider": "",
            "cname_chain": chain,
            "asn": asn,
            "asn_name": asn_name,
            "evidence": evidence or ["CNAME and ASN inspected; no known shared CDN/front door detected"],
        }

    missing = []
    if not cname_ok:
        missing.append("CNAME lookup unavailable")
    if not asn_ok:
        missing.append("ASN lookup unavailable")
    return {
        "status": "unknown",
        "provider": "",
        "cname_chain": chain,
        "asn": asn,
        "asn_name": asn_name,
        "evidence": evidence + missing,
    }


def python_tls_probe(domain: str, port: int, timeout: float) -> dict[str, object]:
    result: dict[str, object] = {
        "tls_ok": False,
        "tls_version": "unknown",
        "alpn": "unknown",
        "remote_ip": "",
        "certificate_identity": "unknown",
        "certificate_days_remaining": None,
        "certificate_sans": [],
    }
    try:
        dns_started = time.perf_counter()
        infos = socket.getaddrinfo(domain, port, type=socket.SOCK_STREAM)
        result["dns_ms"] = round((time.perf_counter() - dns_started) * 1000, 3)
        if not infos:
            raise OSError("no address returned")

        family, socktype, proto, _, sockaddr = infos[0]
        raw = socket.socket(family, socktype, proto)
        raw.settimeout(timeout)
        tcp_started = time.perf_counter()
        raw.connect(sockaddr)
        result["tcp_ms"] = round((time.perf_counter() - tcp_started) * 1000, 3)
        result["remote_ip"] = raw.getpeername()[0]

        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.set_alpn_protocols(["h2"])
        tls_started = time.perf_counter()
        with context.wrap_socket(raw, server_hostname=domain) as tls_sock:
            result["tls_handshake_ms"] = round((time.perf_counter() - tls_started) * 1000, 3)
            result["tls_version"] = tls_sock.version() or "unknown"
            result["alpn"] = tls_sock.selected_alpn_protocol() or "none"
            cert = tls_sock.getpeercert()
            identity, sans = certificate_identity(cert, domain)
            result["certificate_identity"] = identity
            result["certificate_sans"] = sans[:30]
            not_after = cert.get("notAfter")
            if not_after:
                remaining = ssl.cert_time_to_seconds(not_after) - time.time()
                result["certificate_days_remaining"] = int(remaining // 86400)
            result["tls_ok"] = result["tls_version"] == "TLSv1.3" and result["alpn"] == "h2"
    except Exception as exc:
        result["tls_error"] = f"{type(exc).__name__}: {exc}"[:500]
    return result


def x25519_probe(domain: str, port: int, timeout: float) -> dict[str, object]:
    if shutil.which("openssl") is None:
        return {"x25519_ok": None, "x25519_error": "openssl not found"}
    command = [
        "openssl", "s_client",
        "-connect", f"{domain}:{port}",
        "-servername", domain,
        "-tls1_3",
        "-groups", "X25519",
        "-alpn", "h2",
        "-verify_hostname", domain,
        "-verify_return_error",
        "-brief",
    ]
    try:
        completed = subprocess.run(command, input="", capture_output=True, text=True, timeout=timeout)
    except Exception as exc:
        return {"x25519_ok": False, "x25519_error": f"{type(exc).__name__}: {exc}"[:500]}
    raw = f"{completed.stdout}\n{completed.stderr}"
    return {
        "x25519_ok": completed.returncode == 0,
        "x25519_error": "" if completed.returncode == 0 else raw[-500:].strip(),
    }


def head_probe(domain: str, port: int, timeout: float) -> dict[str, object]:
    try:
        context = ssl.create_default_context()
        conn = http.client.HTTPSConnection(domain, port=port, timeout=timeout, context=context)
        conn.request("HEAD", "/", headers={"User-Agent": "RealitySNISelector/2"})
        response = conn.getresponse()
        location = response.getheader("Location") or ""
        response.read()
        conn.close()
        redirect_host = (urlparse(location).hostname or "").lower() if location else ""
        return {
            "http_status": response.status,
            "location": location[:500],
            "redirect_host": redirect_host,
        }
    except Exception as exc:
        return {"http_status": None, "http_head_error": f"{type(exc).__name__}: {exc}"[:500]}


def probe(domain: str, port: int, timeout: float, skip_http: bool) -> dict[str, object]:
    domain = domain.strip().lower().rstrip(".")
    item: dict[str, object] = {"domain": domain, "port": port}
    item.update(python_tls_probe(domain, port, timeout))

    if item.get("tls_ok") is not True:
        item["x25519_ok"] = None
        item["x25519_error"] = "skipped: TLS profile failed"
        item["front_door"] = {
            "status": "unknown", "provider": "", "cname_chain": [],
            "asn": "", "asn_name": "", "evidence": ["skipped: TLS profile failed"],
        }
    else:
        item.update(x25519_probe(domain, port, timeout))
        if item.get("x25519_ok") is True:
            item["front_door"] = classify_front_door(
                domain, str(item.get("remote_ip") or ""), timeout
            )
        else:
            item["front_door"] = {
                "status": "unknown", "provider": "", "cname_chain": [],
                "asn": "", "asn_name": "", "evidence": ["skipped: X25519 probe failed"],
            }

    front_status = str(item["front_door"].get("status"))
    if not skip_http and front_status == "direct":
        item.update(head_probe(domain, port, timeout))

    risks: list[str] = []
    if front_status == "cdn":
        risks.append("cdn/shared-front-door")
    elif front_status == "unknown":
        risks.append("cdn-unknown")
    if item.get("certificate_identity") == "wildcard":
        risks.append("wildcard-cert")
    redirect_host = str(item.get("redirect_host") or "")
    if redirect_host and redirect_host != domain:
        risks.append("redirect")
    item["risk_flags"] = risks
    item["recommended_profile"] = bool(
        item.get("tls_ok") is True
        and item.get("x25519_ok") is True
        and front_status == "direct"
    )
    return item


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe REALITY target TLS compatibility with a strict no-CDN gate.")
    parser.add_argument("domains", nargs="+")
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--skip-http", action="store_true", help="skip the single HEAD request")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be 1..65535")
    if not 1 <= args.timeout <= 60:
        parser.error("timeout must be 1..60 seconds")

    unique = list(dict.fromkeys(d.strip().lower().rstrip(".") for d in args.domains if d.strip()))
    results = [probe(domain, args.port, args.timeout, args.skip_http) for domain in unique]
    print(json.dumps({
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "strict_no_cdn": True,
        "results": results,
    }, ensure_ascii=False, indent=2))
    return 0 if all(item["recommended_profile"] for item in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
