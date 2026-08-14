#!/usr/bin/env python3
"""Minimal REALITY target gate with strict direct/non-CDN classification."""

from __future__ import annotations

import argparse
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
    ("cloudflare.net", "Cloudflare"),
    ("cloudfront.net", "Amazon CloudFront"),
    ("elb.amazonaws.com", "AWS shared front door"),
    ("execute-api.amazonaws.com", "AWS shared front door"),
    ("edgekey.net", "Akamai"),
    ("edgesuite.net", "Akamai"),
    ("akamaiedge.net", "Akamai"),
    ("akamai.net", "Akamai"),
    ("fastly.net", "Fastly"),
    ("fastlylb.net", "Fastly"),
    ("azurefd.net", "Azure Front Door"),
    ("azureedge.net", "Azure CDN"),
    ("trafficmanager.net", "Azure shared front door"),
    ("azurewebsites.net", "Azure shared platform"),
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

HYPERSCALER_ASN_RULES = (
    "amazon",
    "amazon.com",
    "microsoft",
    "google",
    "google cloud",
    "oracle cloud",
    "alibaba",
    "tencent",
)

HIGH_RISK_TARGET_PARTS = ("apple", "icloud", "microsoft")
HIGH_RISK_TLDS = (".cn", ".ru", ".ir")


def family_value(name: str) -> socket.AddressFamily:
    return socket.AF_INET if name == "ipv4" else socket.AF_INET6


def host_port(ip: str, port: int) -> str:
    return f"[{ip}]:{port}" if ":" in ip else f"{ip}:{port}"


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
    for _ in range(6):
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


def cymru_query_name(ip: str) -> str:
    address = ipaddress.ip_address(ip)
    if address.version == 4:
        return ".".join(reversed(ip.split("."))) + ".origin.asn.cymru.com"
    nibbles = address.exploded.replace(":", "")
    return ".".join(reversed(nibbles)) + ".origin6.asn.cymru.com"


def cymru_asn(ip: str, timeout: float) -> tuple[bool, str, str]:
    try:
        query = cymru_query_name(ip)
    except ValueError:
        return False, "", ""

    ok, lines = run_dig(["TXT", query], timeout)
    if not ok or not lines:
        return False, "", ""
    fields = [field.strip() for field in lines[0].split("|")]
    if not fields:
        return False, "", ""
    asn = fields[0].replace("AS", "").strip().split()[0]
    if not asn.isdigit():
        return False, "", ""

    ok_name, name_lines = run_dig(["TXT", f"AS{asn}.asn.cymru.com"], timeout)
    asn_name = ""
    if ok_name and name_lines:
        name_fields = [field.strip() for field in name_lines[0].split("|")]
        if name_fields:
            asn_name = name_fields[-1]
    return True, asn, asn_name


def high_risk_target(domain: str) -> tuple[bool, str]:
    lowered = domain.lower()
    if lowered.endswith(HIGH_RISK_TLDS):
        return True, "high-risk TLD warning pattern"
    for part in HIGH_RISK_TARGET_PARTS:
        if part in lowered:
            return True, f"high-risk hostname warning pattern: {part}"
    return False, ""


def classify_front_door(domain: str, remote_ip: str, timeout: float) -> dict[str, object]:
    cname_ok, chain = cname_chain(domain, timeout)

    for name in [domain, *chain]:
        lowered = name.lower()
        for suffix, provider in CDN_CNAME_RULES:
            if lowered == suffix or lowered.endswith("." + suffix):
                return {
                    "status": "cdn",
                    "provider": provider,
                    "cname_chain": chain,
                    "asn": "",
                    "asn_name": "",
                    "evidence": [f"shared edge CNAME: {name}"],
                }
        if lowered.endswith("amazonaws.com"):
            return {
                "status": "unknown",
                "provider": "AWS",
                "cname_chain": chain,
                "asn": "",
                "asn_name": "",
                "evidence": [f"AWS service CNAME requires manual origin-vs-edge verification: {name}"],
            }

    asn_ok, asn, asn_name = cymru_asn(remote_ip, timeout) if remote_ip else (False, "", "")
    evidence: list[str] = []
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
        if any(keyword in lowered_name for keyword in HYPERSCALER_ASN_RULES):
            return {
                "status": "unknown",
                "provider": asn_name or "hyperscaler",
                "cname_chain": chain,
                "asn": asn,
                "asn_name": asn_name,
                "evidence": evidence + ["hyperscaler ASN requires manual origin-vs-edge verification"],
            }

    if cname_ok and asn_ok:
        return {
            "status": "direct",
            "provider": "",
            "cname_chain": chain,
            "asn": asn,
            "asn_name": asn_name,
            "evidence": evidence + ["no known shared CDN/front-door signal in CNAME or ASN checks"],
        }

    missing: list[str] = []
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


def resolve_addresses(domain: str, port: int, family_name: str, max_ips: int) -> list[tuple[int, int, int, tuple, str]]:
    family = family_value(family_name)
    infos = socket.getaddrinfo(domain, port, family=family, type=socket.SOCK_STREAM)
    unique: list[tuple[int, int, int, tuple, str]] = []
    seen: set[str] = set()
    for af, socktype, proto, _, sockaddr in infos:
        ip = sockaddr[0]
        if ip in seen:
            continue
        seen.add(ip)
        unique.append((af, socktype, proto, sockaddr, ip))
        if len(unique) >= max_ips:
            break
    if not unique:
        raise OSError("no address returned")
    return unique


def tls_probe_address(domain: str, target: tuple[int, int, int, tuple, str], timeout: float) -> dict[str, object]:
    af, socktype, proto, sockaddr, ip = target
    result: dict[str, object] = {
        "remote_ip": ip,
        "tls_ok": False,
        "tls_version": "unknown",
        "alpn": "unknown",
        "certificate_identity": "unknown",
        "certificate_days_remaining": None,
        "certificate_sans": [],
    }
    raw = socket.socket(af, socktype, proto)
    raw.settimeout(timeout)
    try:
        tcp_started = time.perf_counter()
        raw.connect(sockaddr)
        result["tcp_ms"] = round((time.perf_counter() - tcp_started) * 1000, 3)

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
        try:
            raw.close()
        except OSError:
            pass
        result["tls_error"] = f"{type(exc).__name__}: {exc}"[:500]
    return result


def x25519_probe(domain: str, ip: str, port: int, timeout: float) -> dict[str, object]:
    if shutil.which("openssl") is None:
        return {"x25519_ok": None, "x25519_error": "openssl not found"}
    command = [
        "openssl", "s_client",
        "-connect", host_port(ip, port),
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


def redirect_probe(domain: str, ip: str, port: int, timeout: float) -> dict[str, object]:
    if shutil.which("curl") is None:
        return {"redirect_class": "unknown", "http_error": "curl not found"}
    resolve_ip = f"[{ip}]" if ":" in ip else ip
    command = [
        "curl",
        "--head",
        "--silent",
        "--show-error",
        "--max-time", str(timeout),
        "--max-redirs", "0",
        "--resolve", f"{domain}:{port}:{resolve_ip}",
        "--output", "/dev/null",
        "--write-out", "%{http_code}\t%{redirect_url}",
        f"https://{domain}:{port}/",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout + 2)
    except Exception as exc:
        return {"redirect_class": "unknown", "http_error": f"{type(exc).__name__}: {exc}"[:500]}
    if completed.returncode != 0:
        return {
            "redirect_class": "unknown",
            "http_error": (completed.stderr or completed.stdout)[-500:].strip(),
        }
    fields = completed.stdout.strip().split("\t", 1)
    status = int(fields[0]) if fields and fields[0].isdigit() else None
    location = fields[1].strip() if len(fields) > 1 else ""
    if not location:
        return {"http_status": status, "location": "", "redirect_class": "none"}
    host = (urlparse(location).hostname or "").lower()
    if not host or host == domain:
        return {"http_status": status, "location": location[:500], "redirect_class": "none"}
    if host == f"www.{domain}":
        return {"http_status": status, "location": location[:500], "redirect_class": "apex-to-www"}
    return {"http_status": status, "location": location[:500], "redirect_class": "reject", "redirect_host": host}


def probe(domain: str, port: int, timeout: float, family: str, max_ips: int, skip_http: bool) -> dict[str, object]:
    domain = domain.strip().lower().rstrip(".")
    result: dict[str, object] = {"domain": domain, "port": port, "family": family}

    risky, reason = high_risk_target(domain)
    result["high_risk_target"] = risky
    result["high_risk_reason"] = reason
    if risky:
        result["target_gate"] = "reject"
        result["risk_flags"] = ["high-risk-target"]
        result["addresses"] = []
        return result

    try:
        targets = resolve_addresses(domain, port, family, max_ips)
    except Exception as exc:
        result["target_gate"] = "reject"
        result["risk_flags"] = ["resolve-failed"]
        result["resolve_error"] = f"{type(exc).__name__}: {exc}"[:500]
        result["addresses"] = []
        return result

    address_results: list[dict[str, object]] = []
    for target in targets:
        tls_result = tls_probe_address(domain, target, timeout)
        ip = str(tls_result.get("remote_ip") or "")
        if tls_result.get("tls_ok") is True:
            tls_result.update(x25519_probe(domain, ip, port, timeout))
            if tls_result.get("x25519_ok") is True:
                tls_result["front_door"] = classify_front_door(domain, ip, timeout)
            else:
                tls_result["front_door"] = {"status": "unknown", "provider": "", "evidence": ["X25519 probe failed"]}
        else:
            tls_result["x25519_ok"] = None
            tls_result["front_door"] = {"status": "unknown", "provider": "", "evidence": ["TLS profile failed"]}
        address_results.append(tls_result)

    result["addresses"] = address_results
    all_tls = all(item.get("tls_ok") is True for item in address_results)
    all_x25519 = all(item.get("x25519_ok") is True for item in address_results)
    front_statuses = [str(item.get("front_door", {}).get("status", "unknown")) for item in address_results]
    if "cdn" in front_statuses:
        front_status = "cdn"
    elif "unknown" in front_statuses:
        front_status = "unknown"
    else:
        front_status = "direct"

    result["tls_ok"] = all_tls
    result["x25519_ok"] = all_x25519
    result["front_door_status"] = front_status

    if not skip_http and all_tls and all_x25519 and front_status == "direct":
        result.update(redirect_probe(domain, str(address_results[0]["remote_ip"]), port, timeout))
    else:
        result["redirect_class"] = "unknown" if not skip_http else "skipped"

    risks: list[str] = []
    if not all_tls:
        risks.append("tls-profile-failed")
    if not all_x25519:
        risks.append("x25519-failed")
    if front_status == "cdn":
        risks.append("cdn/shared-front-door")
    elif front_status == "unknown":
        risks.append("cdn-unknown")
    if any(item.get("certificate_identity") == "wildcard" for item in address_results):
        risks.append("wildcard-cert")
    redirect_class = str(result.get("redirect_class"))
    if redirect_class == "reject":
        risks.append("redirect")
    elif redirect_class == "apex-to-www":
        risks.append("apex-to-www")
    elif redirect_class == "unknown" and not skip_http:
        risks.append("redirect-unknown")

    result["risk_flags"] = risks
    result["target_gate"] = "pass" if (
        all_tls
        and all_x25519
        and front_status == "direct"
        and redirect_class in ("none", "apex-to-www", "skipped")
    ) else "reject"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe REALITY target compatibility with strict GFW-oriented gates.")
    parser.add_argument("domains", nargs="+")
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--family", choices=("ipv4", "ipv6"), default="ipv4")
    parser.add_argument("--max-ips", type=int, default=4)
    parser.add_argument("--skip-http", action="store_true", help="skip redirect check")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be 1..65535")
    if not 1 <= args.timeout <= 60:
        parser.error("timeout must be 1..60 seconds")
    if not 1 <= args.max_ips <= 8:
        parser.error("max-ips must be 1..8")

    unique = list(dict.fromkeys(d.strip().lower().rstrip(".") for d in args.domains if d.strip()))
    results = [probe(domain, args.port, args.timeout, args.family, args.max_ips, args.skip_http) for domain in unique]
    print(json.dumps({
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "strict_no_cdn": True,
        "family": args.family,
        "results": results,
    }, ensure_ascii=False, indent=2))
    return 0 if all(item.get("target_gate") == "pass" for item in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
