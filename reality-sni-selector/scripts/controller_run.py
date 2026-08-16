#!/usr/bin/env python3
"""Resilient v4.2 controller entrypoint for target-measured Reality SNI selection."""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import secrets
import subprocess
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml

import controller_core as core
import worker_lifecycle as lifecycle
from common import (
    IMPLEMENTATION_VERSION,
    JOB_SCHEMA_VERSION,
    WORKER_PROTOCOL,
    atomic_write_json,
    validate_hostname,
)
from report import render_report, write_rejections_csv

build_job = core.build_job
load_seeds = core.load_seeds
auto_seed_file = core.auto_seed_file
resolve_inventory_path = core.resolve_inventory_path

ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _identifiers(canonical: str, node: dict[str, Any]) -> list[str]:
    values = [canonical, node.get("inventory_id"), node.get("alias"), node.get("name"), node.get("display_name"), node.get("label")]
    out: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        raw = value.strip()
        if raw not in out:
            out.append(raw)
        for token in re.findall(r"[A-Za-z0-9]+", raw):
            if len(token) >= 4 and token not in out:
                out.append(token)
    return out


def _public_ipv4_facts(node: dict[str, Any]) -> list[str]:
    access = node.get("access") if isinstance(node.get("access"), dict) else {}
    out: list[str] = []
    for key in ("address", "hostname"):
        value = access.get(key)
        if not isinstance(value, str):
            continue
        try:
            ip = ipaddress.ip_address(value)
        except ValueError:
            continue
        if ip.version == 4 and ip.is_global and str(ip) not in out:
            out.append(str(ip))
    return out


def inventory_guard(path: Path, selector: str) -> dict[str, Any]:
    """Resolve IPv4/exact name or one high-confidence fuzzy inventory match."""
    selector = str(selector or "").strip()
    if not selector:
        raise ValueError("empty target selector")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"inventory unavailable: {type(exc).__name__}") from exc
    hosts = data.get("hosts") if isinstance(data, dict) else None
    if not isinstance(hosts, dict) or not hosts:
        raise ValueError("inventory local hosts schema missing")

    records: list[tuple[str, dict[str, Any], list[str]]] = []
    for canonical, node in hosts.items():
        if isinstance(canonical, str) and isinstance(node, dict):
            records.append((canonical, node, _identifiers(canonical, node)))

    input_ip: str | None = None
    try:
        ip = ipaddress.ip_address(selector)
        if ip.version != 4 or not ip.is_global:
            raise ValueError
        input_ip = str(ip)
    except ValueError:
        if re.fullmatch(r"[0-9A-Fa-f:.]+", selector) and any(ch in selector for ch in ".:"):
            raise ValueError("invalid target public IPv4")

    resolution = {"input": selector, "mode": None, "matched_identifier": None, "score": None, "warning": None}
    selected: tuple[str, dict[str, Any], list[str]] | None = None
    if input_ip:
        matches = [rec for rec in records if input_ip in _public_ipv4_facts(rec[1])]
        if len(matches) != 1:
            raise ValueError("inventory target missing" if not matches else "inventory target ambiguous")
        selected = matches[0]
        resolution.update(mode="EXACT_IPV4", matched_identifier=input_ip, score=1.0)
    else:
        wanted = _norm(selector)
        exact = [rec for rec in records if any(_norm(value) == wanted for value in rec[2])]
        if len(exact) == 1:
            selected = exact[0]
            matched = next(value for value in selected[2] if _norm(value) == wanted)
            resolution.update(mode="EXACT_NAME", matched_identifier=matched, score=1.0)
        elif len(exact) > 1:
            raise ValueError("inventory target ambiguous")
        else:
            ranked: list[tuple[float, str, str | None, tuple[str, dict[str, Any], list[str]]]] = []
            for rec in records:
                best_score, best_name = 0.0, None
                for name in rec[2]:
                    score = SequenceMatcher(None, wanted, _norm(name)).ratio()
                    if score > best_score:
                        best_score, best_name = score, name
                ranked.append((best_score, rec[0], best_name, rec))
            ranked.sort(key=lambda row: (-row[0], row[1]))
            best_score, _, best_name, best_rec = ranked[0]
            second = ranked[1][0] if len(ranked) > 1 else 0.0
            if best_score < 0.84:
                raise ValueError("inventory target missing")
            if second >= best_score - 0.08:
                raise ValueError("inventory target ambiguous")
            selected = best_rec
            resolution.update(
                mode="FUZZY_UNIQUE",
                matched_identifier=best_name,
                score=round(best_score, 4),
                warning="TARGET_SELECTOR_FUZZY_MATCH",
            )

    canonical, node, _ = selected
    if node.get("inventory_id") is not None and str(node.get("inventory_id")) != canonical:
        raise ValueError("inventory_id does not match canonical host key")
    alias, region = node.get("alias"), node.get("region")
    access = node.get("access") if isinstance(node.get("access"), dict) else {}
    capabilities = node.get("capabilities") if isinstance(node.get("capabilities"), dict) else {}
    state = node.get("state") if isinstance(node.get("state"), dict) else {}
    if not isinstance(alias, str) or not ALIAS_RE.fullmatch(alias):
        raise ValueError("inventory SSH alias missing/invalid")
    if not isinstance(region, str) or not region.strip():
        raise ValueError("inventory region missing")
    if access.get("method") != "ssh" or capabilities.get("ssh") is not True:
        raise ValueError("inventory target is not explicitly SSH-capable")
    if state.get("retired") is True or state.get("forbidden") is True or str(state.get("status") or "").lower() in {"retired", "forbidden", "inactive", "disabled"}:
        raise ValueError("inventory target inactive/retired/forbidden")
    ip_facts = _public_ipv4_facts(node)
    target_ip = input_ip if input_ip else ip_facts[0] if len(ip_facts) == 1 else None
    if not target_ip:
        raise ValueError("inventory target public IPv4 missing" if not ip_facts else "inventory target public IPv4 ambiguous")
    return {
        "inventory_id": canonical,
        "alias": alias,
        "target_ip": target_ip,
        "region": region.strip(),
        "inventory_path": str(path),
        "selector_resolution": resolution,
        "access_facts": {key: access.get(key) for key in ("address", "hostname", "port", "user", "proxy_jump", "identity_ref")},
    }


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-._")[:64] or "target"


def prepare_run_dir(explicit: Path | None, label: str) -> Path:
    if explicit is not None:
        path = explicit.expanduser().resolve()
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise ValueError("run directory must be absent or empty")
        path.mkdir(parents=True, exist_ok=True)
        return path
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = Path.cwd() / f"sni-{_slug(label)}-{stamp}-{secrets.token_hex(3)}"
    path.mkdir()
    return path.resolve()


def sanitize_remote_stderr(stderr: bytes, max_chars: int = 600) -> str:
    return lifecycle.sanitize_stderr(stderr, max_chars=max_chars)


def classify_remote_failure(returncode: int | None, stderr_summary: str) -> tuple[str, str]:
    text = stderr_summary.casefold()
    missing = ("no such file or directory", "command not found", "not found", "bad interpreter", "required file not found")
    if returncode in {126, 127} and any(marker in text for marker in missing):
        return "TARGET_WORKER_UNAVAILABLE", "WORKER_PATH_OR_INTERPRETER_MISSING"
    if returncode == 126 and "permission denied" in text:
        return "TARGET_WORKER_UNAVAILABLE", "WORKER_NOT_EXECUTABLE"
    if returncode == 255 and "permission denied" in text:
        return "SSH_REMOTE_FAILED", "SSH_AUTH_OR_POLICY_FAILURE"
    if returncode == 255 and any(marker in text for marker in ("connection refused", "connection timed out", "could not resolve hostname", "no route to host")):
        return "SSH_REMOTE_FAILED", "SSH_TRANSPORT_FAILURE"
    return "SSH_REMOTE_FAILED", "REMOTE_COMMAND_FAILED"


def run_remote(alias: str, job: dict[str, Any], timeout: int) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    payload = json.dumps(job, ensure_ascii=False, separators=(",", ":")).encode()
    proc = subprocess.Popen(["ssh", "-T", alias, *core.REMOTE_COMMAND], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = proc.communicate(payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        _, stderr = proc.communicate()
        return None, "SSH_TIMEOUT", {"returncode": proc.returncode, "failure_detail": "SSH_TIMEOUT", "stderr_summary": sanitize_remote_stderr(stderr)}
    diagnostics = {"returncode": proc.returncode, "failure_detail": None, "stderr_summary": sanitize_remote_stderr(stderr)}
    try:
        parsed = json.loads(stdout.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        worker = parsed.get("worker") if isinstance(parsed.get("worker"), dict) else {}
        if parsed.get("schema_version") != JOB_SCHEMA_VERSION or worker.get("protocol") != WORKER_PROTOCOL or worker.get("implementation_version") != IMPLEMENTATION_VERSION:
            diagnostics["failure_detail"] = "WORKER_PROTOCOL_OR_VERSION_MISMATCH"
            return None, "TARGET_WORKER_VERSION_MISMATCH", diagnostics
        if worker.get("manifest") != job.get("expected_worker_manifest"):
            diagnostics["failure_detail"] = "WORKER_MANIFEST_MISMATCH"
            return None, "TARGET_WORKER_BUILD_MISMATCH", diagnostics
        return parsed, "OK" if proc.returncode == 0 else "REMOTE_NONZERO_WITH_RESULT", diagnostics
    if proc.returncode != 0:
        status, detail = classify_remote_failure(proc.returncode, diagnostics["stderr_summary"])
        diagnostics["failure_detail"] = detail
        return None, status, diagnostics
    diagnostics["failure_detail"] = "STDOUT_NOT_VALID_WORKER_JSON"
    return None, "TARGET_RESULT_INVALID", diagnostics


def _write_blocked(run_dir: Path, stage_path: Path, reason: str, *, guard: dict[str, Any], controller_meta: dict[str, Any], lifecycle_meta: dict[str, Any] | None = None, frozen_run: dict[str, Any] | None = None) -> None:
    blocked = {
        "schema_version": JOB_SCHEMA_VERSION,
        "status": "BLOCKED",
        "reason": reason,
        "controller": controller_meta,
        "top5": [],
        "preliminary_top5": [],
        "comparison": [],
    }
    atomic_write_json(run_dir / "target-result.json", blocked)
    atomic_write_json(run_dir / "top5.json", blocked)
    if lifecycle_meta is not None:
        atomic_write_json(run_dir / "worker-lifecycle.json", lifecycle_meta)
    metadata = {"status": reason, "guard": guard, "controller": controller_meta}
    if lifecycle_meta is not None:
        metadata["worker_lifecycle"] = lifecycle_meta
    if frozen_run is not None:
        metadata["frozen_run"] = frozen_run
    atomic_write_json(run_dir / "run-metadata.json", metadata)
    with stage_path.open("a", encoding="utf-8") as handle:
        handle.write(f"blocked\t{reason}\tselection did not start candidate evaluation\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="inventory public IPv4, exact alias/name, or uniquely matched local inventory name")
    ap.add_argument("--inventory", type=Path)
    ap.add_argument("--seed-file", type=Path)
    ap.add_argument("--incumbent", default="auto")
    ap.add_argument("--profile", choices=("quick", "audit"), default="quick")
    ap.add_argument("--run-dir", type=Path, help="dedicated output directory; absent/empty only")
    ap.add_argument("--ssh-timeout", type=int, default=2400)
    ap.add_argument("--worker-bootstrap", choices=("auto", "never"), default="auto", help="auto installs/upgrades only the managed fixed worker before freeze; never fails closed instead")
    ap.add_argument("--worker-ready-only", action="store_true", help="ensure exact worker readiness, write lifecycle metadata, then stop before freezing or candidate traffic")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    scripts_dir = root / "scripts"
    run_dir: Path | None = None
    stage_path: Path | None = None
    guard: dict[str, Any] | None = None
    try:
        inventory_path = core.resolve_inventory_path(args.inventory)
        guard = inventory_guard(inventory_path, args.target)
        run_dir = prepare_run_dir(args.run_dir, guard["inventory_id"])
        stage_path = run_dir / "stage-status.tsv"
        stage_path.write_text("stage\tstatus\tdetail\n", encoding="utf-8")
        print(f"RUN_DIR:{run_dir}")
    except Exception as exc:
        if run_dir is None:
            try:
                run_dir = prepare_run_dir(args.run_dir, args.target)
                stage_path = run_dir / "stage-status.tsv"
                print(f"RUN_DIR:{run_dir}")
            except Exception:
                pass
        if stage_path:
            stage_path.write_text(f"stage\tstatus\tdetail\ninventory_or_input\tFAILED\t{type(exc).__name__}\n", encoding="utf-8")
        if run_dir:
            atomic_write_json(run_dir / "top5.json", {"status": "BLOCKED", "reason": "INVENTORY_OR_INPUT_FAILED", "top5": [], "comparison": []})
        return 2

    assert run_dir and stage_path and guard
    resolution = guard.get("selector_resolution") or {}
    if resolution.get("warning"):
        with stage_path.open("a", encoding="utf-8") as handle:
            handle.write(f"inventory_resolution\tREVIEW\t{resolution['warning']}:{resolution.get('matched_identifier')}:{resolution.get('score')}\n")

    # v4.2 deliberately makes worker readiness a pre-freeze control-plane step.
    worker_lifecycle = lifecycle.ensure_worker_ready(
        guard["alias"],
        scripts_dir,
        bootstrap_mode=args.worker_bootstrap,
        probe_timeout=20,
        bootstrap_timeout=180,
    )
    atomic_write_json(run_dir / "worker-lifecycle.json", worker_lifecycle)
    with stage_path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"worker_readiness\t{'OK' if worker_lifecycle.get('ready') else 'FAILED'}\t"
            f"{worker_lifecycle.get('status')}:{worker_lifecycle.get('action')}\n"
        )
    controller_meta: dict[str, Any] = {
        "run_dir": str(run_dir),
        "target_resolution": resolution,
        "worker_lifecycle": worker_lifecycle,
    }
    if not worker_lifecycle.get("ready"):
        _write_blocked(run_dir, stage_path, str(worker_lifecycle.get("status") or "TARGET_WORKER_NOT_READY"), guard=guard, controller_meta=controller_meta, lifecycle_meta=worker_lifecycle)
        return 3
    if args.worker_ready_only:
        atomic_write_json(run_dir / "run-metadata.json", {"status": "WORKER_READY_ONLY", "guard": guard, "controller": controller_meta, "worker_lifecycle": worker_lifecycle})
        with stage_path.open("a", encoding="utf-8") as handle:
            handle.write("complete\tWORKER_READY_ONLY\tno frozen job or candidate traffic\n")
        print("TARGET_MEASURED_RUN_STATUS:WORKER_READY_ONLY")
        return 0

    try:
        seed_path = args.seed_file or core.auto_seed_file(root, guard.get("region"))
        seeds = core.load_seeds(seed_path)
        if str(args.incumbent).lower() == "auto":
            incumbent, incumbent_mode = None, "auto"
        else:
            incumbent, incumbent_mode = validate_hostname(args.incumbent), "explicit"
            if incumbent not in seeds:
                seeds.append(incumbent)
        manifest = str(worker_lifecycle["expected_manifest"])
        job = core.build_job(guard, seeds, incumbent, incumbent_mode, worker_manifest=manifest, profile_mode=args.profile)
    except Exception as exc:
        with stage_path.open("a", encoding="utf-8") as handle:
            handle.write(f"freeze_input\tFAILED\t{type(exc).__name__}\n")
        _write_blocked(run_dir, stage_path, "FREEZE_INPUT_FAILED", guard=guard, controller_meta=controller_meta, lifecycle_meta=worker_lifecycle)
        return 2

    atomic_write_json(run_dir / "frozen-run.json", job)
    with stage_path.open("a", encoding="utf-8") as handle:
        handle.write(f"freeze\tOK\tv4.2 {args.profile} profile frozen only after exact worker readiness\n")

    result, remote_status, diagnostics = run_remote(guard["alias"], job, max(60, args.ssh_timeout))
    with stage_path.open("a", encoding="utf-8") as handle:
        handle.write(f"target_worker\t{remote_status}\t{diagnostics.get('failure_detail') or 'fixed absolute worker run command'}\n")
    controller_meta["remote_diagnostics"] = diagnostics
    if result is None:
        _write_blocked(run_dir, stage_path, remote_status, guard=guard, controller_meta=controller_meta, lifecycle_meta=worker_lifecycle, frozen_run=job)
        return 3

    result = dict(result)
    result["controller"] = controller_meta
    if resolution.get("warning"):
        result["warnings"] = sorted(set(list(result.get("warnings") or []) + [resolution["warning"]]))
    atomic_write_json(run_dir / "target-result.json", result)
    mapping = {
        "target-frozen-run.json": result.get("frozen_run", {}),
        "target-preflight.json": result.get("preflight", {}),
        "regional-candidates.json": result.get("regional_candidates", {}),
        "candidates.json": result.get("candidates", []),
        "probe-pool.json": result.get("probe_pool", []),
        "eligibility.json": result.get("eligibility", []),
        "fast-benchmark.json": result.get("fast_benchmark", []),
        "deep-benchmark.json": result.get("deep_benchmark", []),
        "reality-results.json": result.get("reality", {}),
        "comparison.json": result.get("comparison", []),
        "incumbent-assessment.json": result.get("incumbent_assessment", {}),
        "top5.json": {"status": result.get("status"), "coverage": result.get("coverage", {}), "top5": result.get("top5", []), "preliminary_top5": result.get("preliminary_top5", []), "comparison": result.get("comparison", [])},
        "run-metadata.json": {"status": result.get("status"), "worker": result.get("worker", {}), "guard": guard, "controller": controller_meta, "worker_lifecycle": worker_lifecycle, "controller_frozen_run": job, "target_frozen_run": result.get("frozen_run", {}), "coverage": result.get("coverage", {}), "counts": result.get("counts", {}), "warnings": result.get("warnings", [])},
    }
    for name, payload in mapping.items():
        atomic_write_json(run_dir / name, payload)
    write_rejections_csv(run_dir / "rejections.csv", result.get("rejections", []))
    (run_dir / "report.md").write_text(render_report(result), encoding="utf-8")
    with stage_path.open("a", encoding="utf-8") as handle:
        handle.write(f"artifacts\tOK\t{result.get('status', 'UNKNOWN')}\n")
    print(f"TARGET_MEASURED_RUN_STATUS:{result.get('status', 'UNKNOWN')}")
    ok = {"SUCCESS", "SUCCESS_WITH_REVIEW", "SUCCESS_PARTIAL_CHOICES", "PARTIAL_REALITY_UNAVAILABLE", "INVALID_REALITY_CONTROL"}
    return 0 if result.get("status") in ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
