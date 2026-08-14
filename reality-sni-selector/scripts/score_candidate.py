#!/usr/bin/env python3
"""Apply the fixed REALITY SNI evidence rubric and hard-grade gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CERTIFICATE = {"exact": 18, "wildcard": 6, "shared": 10, "mismatch": 0}
NETWORK_FIT = {
    "same-provider": 20,
    "same-metro": 18,
    "same-region": 16,
    "nearby": 12,
    "mismatch": 4,
}
ORGANIZATION_PREFERENCE = {
    "same-asn-preferred-institution": 4,
    "same-asn-other": 2,
    "preferred-institution": 2,
    "commercial": 0,
    "unknown": 0,
}
FRONT_DOOR_PENALTY = {
    "direct": 0,
    "dedicated-cdn": 1,
    "shared-cdn": 4,
    "hyperscale": 6,
}
FOOTPRINT = {
    "substantial": 16,
    "small-active": 12,
    "uncertain": 6,
    "placeholder": 0,
}
TRAFFIC = {"fit": 4, "unknown": 1, "mismatch": 0}
DURABILITY = {"strong": 5, "normal": 3, "weak": 1}
EXAMPLE = {
    "domain": "www.example.org",
    "selection_mode": "strict_no_cdn",
    "compatibility_pass": True,
    "certificate": {"identity": "exact", "days_remaining": 185},
    "network": {
        "fit": "same-region",
        "front_door": "direct",
        "inspected": True,
        "cdn_evidence": False,
        "organization": "same-asn-preferred-institution",
    },
    "website": {"footprint": "substantial", "traffic": "fit"},
    "https": {
        "attempts": 20,
        "successes": 20,
        "status_ok": True,
        "tls_version": "TLSv1.3",
        "alpn": "h2",
        "redirect_count": 0,
        "final_host_relation": "none",
        "tls_p95_ms": 80.0,
        "tls_max_ms": 120.0,
        "latency_within_baseline": True,
    },
    "reality": {
        "level": "production",
        "external_endpoints": 2,
        "consecutive_successes": 10,
    },
    "operations": {
        "durability": "normal",
        "dependencies_synchronized": True,
        "service_active": True,
        "recent_errors": 0,
        "rollback_available": True,
    },
}


def require_enum(value: str, mapping: dict[str, int], field: str) -> str:
    if value not in mapping:
        raise ValueError(f"{field} must be one of {sorted(mapping)}")
    return value


def score_one(item: dict) -> dict[str, object]:
    domain = str(item["domain"])
    selection_mode = str(item.get("selection_mode", "strict_no_cdn"))
    if selection_mode not in {"balanced", "strict_no_cdn", "production"}:
        raise ValueError("selection_mode must be balanced, strict_no_cdn, or production")
    cert = item["certificate"]
    network = item["network"]
    website = item["website"]
    https = item["https"]
    reality = item["reality"]
    operations = item["operations"]

    identity = require_enum(cert["identity"], CERTIFICATE, "certificate.identity")
    network_fit = require_enum(network["fit"], NETWORK_FIT, "network.fit")
    organization = require_enum(
        network.get("organization", "unknown"),
        ORGANIZATION_PREFERENCE,
        "network.organization",
    )
    front_door = require_enum(
        network["front_door"], FRONT_DOOR_PENALTY, "network.front_door"
    )
    footprint = require_enum(
        website["footprint"], FOOTPRINT, "website.footprint"
    )
    traffic = require_enum(website["traffic"], TRAFFIC, "website.traffic")
    durability = require_enum(
        operations["durability"], DURABILITY, "operations.durability"
    )
    reality_level = str(reality["level"])
    if reality_level not in {"production", "isolated", "none"}:
        raise ValueError("reality.level must be production, isolated, or none")

    days = int(cert["days_remaining"])
    certificate_score = CERTIFICATE[identity] + (2 if days >= 30 else 0)
    certificate_score = min(20, certificate_score)
    network_score = max(0, NETWORK_FIT[network_fit] - FRONT_DOOR_PENALTY[front_door])
    network_score = min(20, network_score + ORGANIZATION_PREFERENCE[organization])
    website_score = min(20, FOOTPRINT[footprint] + TRAFFIC[traffic])

    attempts = int(https["attempts"])
    successes = int(https["successes"])
    tls_version = str(https.get("tls_version", "unknown"))
    alpn = str(https.get("alpn", "unknown"))
    redirect_count = int(https.get("redirect_count", 0))
    final_host_relation = str(https.get("final_host_relation", "none"))
    ratio = successes / attempts if attempts > 0 else 0
    https_score = round(ratio * 10)
    if bool(https["status_ok"]):
        https_score += 4
    p95 = float(https["tls_p95_ms"])
    maximum = float(https["tls_max_ms"])
    https_score += 3 if p95 <= 100 else 2 if p95 <= 200 else 0
    https_score += 3 if maximum <= 200 else 1 if maximum <= 400 else 0
    https_score = min(20, https_score)

    endpoints = int(reality["external_endpoints"])
    consecutive = int(reality["consecutive_successes"])
    if reality_level == "production":
        reality_score = 15 if endpoints >= 2 and consecutive >= 5 else 12
    elif reality_level == "isolated":
        reality_score = 10
    else:
        reality_score = 0

    durability_score = DURABILITY[durability]
    components = {
        "certificate": certificate_score,
        "network": network_score,
        "website_traffic": website_score,
        "https": https_score,
        "reality": reality_score,
        "durability": durability_score,
    }

    manual_failures: list[str] = []
    if identity != "exact":
        manual_failures.append("certificate hostname is not an exact explicit SAN")
    if days < 30:
        manual_failures.append("certificate has less than 30 days remaining")
    if not bool(network["inspected"]):
        manual_failures.append("DNS/ASN/region/CDN evidence not inspected")
    if tls_version != "TLSv1.3":
        manual_failures.append("TLS version is not explicitly TLS 1.3")
    if alpn != "h2":
        manual_failures.append("ALPN is not explicitly h2")
    if redirect_count > 1:
        manual_failures.append("redirect chain has more than one hop")
    if redirect_count > 0 and final_host_relation not in {"same-host", "same-organization"}:
        manual_failures.append("redirect leaves the same host or organization")
    if selection_mode == "strict_no_cdn" and (
        bool(network.get("cdn_evidence", False))
        or front_door in {"dedicated-cdn", "shared-cdn"}
    ):
        manual_failures.append("known CDN or shared front door is disallowed in strict_no_cdn mode")
    if footprint not in {"substantial", "small-active"}:
        manual_failures.append("website footprint is not production-suitable")
    if traffic != "fit":
        manual_failures.append("target traffic plausibility is not confirmed")
    if attempts < 5 or successes != attempts:
        manual_failures.append("direct HTTPS did not pass at least five of five")
    if not bool(https["status_ok"]):
        manual_failures.append("HTTP status/redirect behavior is not acceptable")
    if not bool(https["latency_within_baseline"]):
        manual_failures.append("TLS latency exceeds the documented regional baseline")

    production_failures: list[str] = []
    if reality_level != "production" or endpoints < 2 or consecutive < 5:
        production_failures.append("actual production REALITY path is incomplete")
    if not bool(operations["dependencies_synchronized"]):
        production_failures.append("dependent configurations are not synchronized")
    if not bool(operations["service_active"]):
        production_failures.append("service/listener state is not healthy")
    if int(operations["recent_errors"]) != 0:
        production_failures.append("recent relevant service errors are nonzero")
    if not bool(operations["rollback_available"]):
        production_failures.append("rollback is unavailable")

    compatibility_pass = bool(item["compatibility_pass"])
    explicit_protocol_failure = (
        tls_version not in {"TLSv1.3", "unknown"}
        or alpn not in {"h2", "unknown"}
    )
    total_https_failure = attempts > 0 and successes == 0
    if (
        not compatibility_pass
        or identity == "mismatch"
        or total_https_failure
        or explicit_protocol_failure
    ):
        grade = "D"
    elif manual_failures:
        grade = "C"
    elif production_failures:
        grade = "B"
    else:
        grade = "A"

    return {
        "domain": domain,
        "grade": grade,
        "total": sum(components.values()),
        "components": components,
        "manual_gate_failures": manual_failures,
        "production_gate_failures": production_failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score REALITY SNI evidence using fixed weights and hard gates."
    )
    parser.add_argument("evidence", nargs="?", type=Path)
    parser.add_argument(
        "--example", action="store_true", help="print an example evidence object"
    )
    args = parser.parse_args()
    if args.example:
        print(json.dumps(EXAMPLE, ensure_ascii=False, indent=2))
        return 0
    if args.evidence is None:
        parser.error("evidence is required unless --example is used")
    payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    items = payload if isinstance(payload, list) else [payload]
    results = [score_one(item) for item in items]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
