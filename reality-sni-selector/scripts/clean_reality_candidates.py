#!/usr/bin/env python3
"""Clean RealiTLScanner CSV output or plain domain lists for REALITY SNI tests."""

from __future__ import annotations

import argparse
import csv
import ipaddress
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


DOMAIN_COLUMNS = (
    "CERT_DOMAIN",
    "cert_domain",
    "domain",
    "Domain",
    "server_name",
    "SNI",
    "sni",
)

HEADER_VALUES = {name.lower() for name in DOMAIN_COLUMNS}

BAD_SUBSTRINGS = (
    "cloudflare origin certificate",
    "common name",
    "localhost",
    "x-ui",
    "3x-ui",
    "clash",
    "sub",
    "api",
    "node",
    "proxy",
    "vless",
    "vmess",
    "trojan",
    "hysteria",
    "hy2",
    "airport",
    "panel",
    "admin",
    "login",
    "test",
    "grafana",
    "bt",
    "status",
)

STRICT_BAD_SUBSTRINGS = (
    "cloudflare",
    "myqcloud",
    "cdn",
    "akamai",
    "fastly",
    "edgekey",
    "apple",
    "amazon",
    "google",
    "microsoft",
    "github",
    "paypal",
    "slack",
    "mozilla",
    "python",
)

LOW_REPUTATION_TLDS = {
    "xyz",
    "top",
    "shop",
    "fun",
    "icu",
    "cyou",
    "buzz",
    "sbs",
    "lol",
    "bond",
}

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")


def normalize(raw: str) -> str:
    value = (raw or "").strip().strip('"').strip("'").strip()
    if not value:
        return ""
    if "://" in value:
        parsed = urlparse(value)
        value = parsed.hostname or value
    value = value.split("/")[0].split(":")[0].strip().lower().rstrip(".")
    return value


def is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def reject_reason(domain: str, strict: bool) -> str | None:
    if not domain:
        return "empty"
    if domain.startswith("*."):
        return "wildcard"
    if is_ip(domain):
        return "ip-address"
    if not DOMAIN_RE.match(domain):
        return "malformed"
    lowered = domain.lower()
    for text in BAD_SUBSTRINGS:
        if text in lowered:
            return f"bad-substring:{text}"
    if re.search(r"\d{5,}", lowered):
        return "many-digits"
    if strict:
        for text in STRICT_BAD_SUBSTRINGS:
            if text in lowered:
                return f"strict-substring:{text}"
        tld = lowered.rsplit(".", 1)[-1]
        if tld in LOW_REPUTATION_TLDS:
            return f"strict-tld:{tld}"
    return None


def read_candidates(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    sample = text[:4096]
    candidates: list[str] = []

    try:
        dialect = csv.Sniffer().sniff(sample)
        has_header = csv.Sniffer().has_header(sample)
    except csv.Error:
        dialect = None
        has_header = False

    if dialect and has_header:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle, dialect=dialect)
            columns = reader.fieldnames or []
            selected = [name for name in DOMAIN_COLUMNS if name in columns]
            fallback = columns
            for row in reader:
                source_columns = selected or fallback
                for name in source_columns:
                    value = normalize(row.get(name, ""))
                    if value:
                        candidates.append(value)
                        if selected:
                            break
        return candidates

    for line in text.splitlines():
        for part in re.split(r"[\s,;]+", line):
            value = normalize(part)
            if value in HEADER_VALUES:
                continue
            if value:
                candidates.append(value)
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean REALITY SNI candidate domains.")
    parser.add_argument("input", type=Path, help="RealiTLScanner CSV or plain domain list")
    parser.add_argument("--out", type=Path, help="Output candidate text file")
    parser.add_argument("--strict", action="store_true", help="Filter CDN/famous/low-reputation patterns")
    parser.add_argument("--show-rejects", action="store_true", help="Print rejected values and reasons to stderr")
    args = parser.parse_args()

    raw_candidates = read_candidates(args.input)
    accepted: set[str] = set()
    rejects: list[tuple[str, str]] = []

    for item in raw_candidates:
        reason = reject_reason(item, args.strict)
        if reason:
            rejects.append((item, reason))
            continue
        accepted.add(item)

    lines = sorted(accepted)
    output = "\n".join(lines)
    if output:
        output += "\n"

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)

    if args.show_rejects:
        for item, reason in rejects:
            print(f"reject\t{reason}\t{item}", file=sys.stderr)
        print(f"accepted={len(lines)} rejected={len(rejects)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
