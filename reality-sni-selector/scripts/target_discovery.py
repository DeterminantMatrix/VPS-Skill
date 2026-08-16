#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
import json
import socket
import urllib.parse
from collections import defaultdict
from typing import Any

from common import fetch_json, hostname_from_url, is_public_ipv4, is_service_hostname, registrable_domain, validate_hostname


def resolve_public_ipv4(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, 443, socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        return []
    return sorted({info[4][0] for info in infos if is_public_ipv4(info[4][0])})


def add_record(records: dict[str, dict[str, Any]], hostname: str | None, source: str, organization: str | None = None, distance_km: float | None = None) -> None:
    if not hostname:
        return
    try:
        hostname = validate_hostname(hostname)
    except ValueError:
        return
    record = records.setdefault(hostname, {"hostname": hostname, "sources": [], "organizations": [], "distance_km": None})
    if source not in record["sources"]:
        record["sources"].append(source)
    if organization and organization not in record["organizations"]:
        record["organizations"].append(str(organization)[:200])
    if distance_km is not None:
        old = record.get("distance_km")
        if old is None or distance_km < old:
            record["distance_km"] = round(distance_km, 2)


def wikidata_nearby(lat: float, lon: float, radius_km: int, limit: int = 500) -> tuple[list[tuple[str, str]], str | None]:
    query = f'''SELECT ?item ?itemLabel ?website WHERE {{
      SERVICE wikibase:around {{
        ?item wdt:P625 ?location .
        bd:serviceParam wikibase:center "Point({lon} {lat})"^^geo:wktLiteral .
        bd:serviceParam wikibase:radius "{radius_km}" .
      }}
      ?item wdt:P856 ?website .
      VALUES ?class {{ wd:Q3918 wd:Q875538 wd:Q33506 wd:Q7075 wd:Q15284 wd:Q163740 wd:Q43229 wd:Q327333 wd:Q7278 }}
      ?item wdt:P31/wdt:P279* ?class .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} LIMIT {limit}'''
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": query, "format": "json"})
    try:
        data = fetch_json(url, timeout=15, max_bytes=2_000_000, headers={"Accept": "application/sparql-results+json"})
        out = []
        for row in data.get("results", {}).get("bindings", []):
            host = hostname_from_url(row.get("website", {}).get("value", ""))
            label = row.get("itemLabel", {}).get("value", "")
            if host:
                out.append((host, label))
        return out, None
    except Exception as exc:
        return [], f"wikidata:{type(exc).__name__}"


def osm_nearby(lat: float, lon: float, radius_km: int) -> tuple[list[tuple[str, str]], str | None]:
    radius_m = min(radius_km * 1000, 150_000)
    q = f'''[out:json][timeout:20];(
      nwr(around:{radius_m},{lat},{lon})[amenity~"^(university|college|school|library)$"][website];
      nwr(around:{radius_m},{lat},{lon})[tourism="museum"][website];
      nwr(around:{radius_m},{lat},{lon})[office~"^(government|association|ngo|research)$"][website];
      nwr(around:{radius_m},{lat},{lon})[amenity~"^(university|college|school|library)$"]["contact:website"];
      nwr(around:{radius_m},{lat},{lon})[tourism="museum"]["contact:website"];
    );out tags center 700;'''
    try:
        body = urllib.parse.urlencode({"data": q}).encode()
        data = fetch_json("https://overpass-api.de/api/interpreter", timeout=25, max_bytes=3_000_000,
                          headers={"Content-Type": "application/x-www-form-urlencoded"}, data=body)
        out = []
        for item in data.get("elements", []):
            tags = item.get("tags", {})
            website = tags.get("website") or tags.get("contact:website")
            host = hostname_from_url(website or "")
            label = tags.get("name") or tags.get("operator") or ""
            if host:
                out.append((host, label))
        return out, None
    except Exception as exc:
        return [], f"osm:{type(exc).__name__}"


def openalex_city(city: str, limit: int = 100) -> tuple[list[tuple[str, str]], str | None]:
    if not city:
        return [], None
    url = "https://api.openalex.org/institutions?" + urllib.parse.urlencode({"search": city, "per-page": min(limit, 100)})
    try:
        data = fetch_json(url, timeout=12, max_bytes=2_000_000)
        out = []
        for item in data.get("results", []):
            host = hostname_from_url(item.get("homepage_url") or "")
            if host:
                out.append((host, item.get("display_name") or ""))
        return out, None
    except Exception as exc:
        return [], f"openalex:{type(exc).__name__}"


def ct_names(base: str, max_names: int) -> tuple[list[str], str | None]:
    url = "https://crt.sh/?" + urllib.parse.urlencode({"q": f"%.{base}", "output": "json"})
    try:
        data = fetch_json(url, timeout=12, max_bytes=3_000_000)
        names: list[str] = []
        seen = set()
        for item in data if isinstance(data, list) else []:
            for raw in str(item.get("name_value", "")).splitlines():
                raw = raw.strip().lstrip("*.")
                try:
                    host = validate_hostname(raw)
                except ValueError:
                    continue
                if not host.endswith("." + base) and host != base:
                    continue
                if host not in seen:
                    seen.add(host)
                    names.append(host)
                    if len(names) >= max_names:
                        return names, None
        return names, None
    except Exception as exc:
        return [], f"ct:{type(exc).__name__}"


def discover(job: dict[str, Any], preflight: dict[str, Any]) -> dict[str, Any]:
    limits = job["limits"]
    records: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    incumbent = job["incumbent"]

    for host in job.get("seed_domains", []):
        add_record(records, host, "seed")
    add_record(records, incumbent, "incumbent")

    loc = preflight.get("location") or {}
    lat, lon = loc.get("latitude"), loc.get("longitude")
    region_mismatch = bool(preflight.get("region_mismatch"))

    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and not region_mismatch:
        primary = int(job["profile"]["primary_radius_km"])
        expanded = int(job["profile"]["expanded_radius_km"])
        for source_func, source_name in ((wikidata_nearby, "wikidata"), (osm_nearby, "osm")):
            items, err = source_func(float(lat), float(lon), primary)
            if err:
                errors.append(err)
            for host, org in items:
                add_record(records, host, source_name, org)
        if len(records) < int(job["profile"]["coverage_goal"]):
            for source_func, source_name in ((wikidata_nearby, "wikidata"), (osm_nearby, "osm")):
                items, err = source_func(float(lat), float(lon), expanded)
                if err:
                    errors.append(err)
                for host, org in items:
                    add_record(records, host, source_name, org)
    else:
        errors.append("LOCATION_DEGRADED" if not region_mismatch else "REGION_MISMATCH_REVIEW")

    city = str(loc.get("city") or "")
    if city and not region_mismatch:
        items, err = openalex_city(city)
        if err:
            errors.append(err)
        for host, org in items:
            add_record(records, host, "openalex", org)

    # Passive CT is constrained to known institutional base domains and a fixed failure budget.
    bases = []
    for host, rec in list(records.items()):
        if "seed" in rec["sources"] or "wikidata" in rec["sources"] or "osm" in rec["sources"]:
            try:
                base = registrable_domain(host)
            except ValueError:
                continue
            if base not in bases:
                bases.append(base)
            if len(bases) >= int(limits.get("ct_base_cap", 40)):
                break
    consecutive_failures = 0
    ct_stopped = False
    for base in bases:
        if consecutive_failures >= int(job["profile"]["ct_failure_budget"]):
            ct_stopped = True
            break
        names, err = ct_names(base, int(limits.get("ct_max_per_domain", 20)))
        if err:
            consecutive_failures += 1
            errors.append(err)
            continue
        consecutive_failures = 0
        for host in names:
            add_record(records, host, "ct")
        if len(records) >= int(limits["source_pool_cap"]):
            break
    if ct_stopped:
        errors.append("CT_SKIPPED_AFTER_FAILURE_BUDGET")

    # Apply source cap deterministically, keeping incumbent and direct institutional sources first.
    priority = {"incumbent": 0, "seed": 1, "wikidata": 2, "osm": 3, "openalex": 4, "ct": 5}
    ordered = sorted(records.values(), key=lambda r: (min(priority.get(s, 9) for s in r["sources"]), r["hostname"]))
    ordered = ordered[: int(limits["source_pool_cap"])]

    incumbent_set = {incumbent}
    to_validate = [r for r in ordered if not is_service_hostname(r["hostname"]) or r["hostname"] in incumbent_set]
    validated: list[dict[str, Any]] = []
    workers = min(16, max(1, int(limits.get("dns_workers", 12))))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(resolve_public_ipv4, r["hostname"]): r for r in to_validate}
        for future in concurrent.futures.as_completed(future_map):
            rec = future_map[future]
            try:
                ips = future.result()
            except Exception:
                ips = []
            if ips:
                item = dict(rec)
                item["initial_ipv4"] = ips
                validated.append(item)
    validated.sort(key=lambda r: (0 if r["hostname"] == incumbent else 1, min(priority.get(s, 9) for s in r["sources"]), r["hostname"]))
    validated = validated[: int(limits["discovered_cap"])]
    count = len(validated)
    coverage = "GOOD" if count >= 400 else "LIMITED" if count >= 100 else "SPARSE"
    return {
        "source_records": ordered,
        "validated": validated,
        "coverage": coverage,
        "errors": sorted(set(errors)),
        "counts": {"source_records": len(ordered), "validated_ipv4": count},
    }
