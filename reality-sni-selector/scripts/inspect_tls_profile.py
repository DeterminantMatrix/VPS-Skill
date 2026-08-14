#!/usr/bin/env python3
"""Inspect TLS 1.3 and ALPN h2 support for exact SNI candidates."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone


def inspect(domain: str, timeout: float) -> dict[str, object]:
    command = [
        "openssl",
        "s_client",
        "-connect",
        f"{domain}:443",
        "-servername",
        domain,
        "-tls1_3",
        "-alpn",
        "h2",
        "-brief",
    ]
    try:
        completed = subprocess.run(
            command,
            input="",
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "domain": domain,
            "status": "timeout",
            "tls_version": "unknown",
            "alpn": "unknown",
            "protocol_ok": False,
        }
    except OSError as exc:
        return {
            "domain": domain,
            "status": "error",
            "tls_version": "unknown",
            "alpn": "unknown",
            "protocol_ok": False,
            "error": str(exc)[:300],
        }

    raw = f"{completed.stdout}\n{completed.stderr}"
    tls_match = re.search(r"Protocol version:\s*(TLSv\S+)", raw, re.I)
    alpn_match = re.search(r"ALPN protocol:\s*(\S+)", raw, re.I)
    tls_version = tls_match.group(1) if tls_match else "unknown"
    alpn = alpn_match.group(1) if alpn_match else "none"
    return {
        "domain": domain,
        "status": "ok" if completed.returncode == 0 else "failed",
        "tls_version": tls_version,
        "alpn": alpn,
        "protocol_ok": tls_version == "TLSv1.3" and alpn == "h2",
        "openssl_exit": completed.returncode,
        "error": "" if completed.returncode == 0 else raw[-500:].strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check TLS 1.3 and ALPN h2 for exact SNI candidates."
    )
    parser.add_argument("domains", nargs="+")
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args()
    if shutil.which("openssl") is None:
        parser.error("openssl is required")
    if not 1 <= args.timeout <= 60:
        parser.error("timeout must be 1..60 seconds")

    results = [inspect(domain.strip().lower().rstrip("."), args.timeout) for domain in args.domains]
    print(
        json.dumps(
            {
                "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                "requested_alpn": "h2",
                "requested_tls": "TLSv1.3",
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if all(item["protocol_ok"] for item in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
