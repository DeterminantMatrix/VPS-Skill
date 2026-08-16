#!/usr/bin/env python3
"""Controller-side worker readiness, bootstrap, and fixed-path upgrade logic."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from common import IMPLEMENTATION_VERSION, JOB_SCHEMA_VERSION, WORKER_PROTOCOL, compute_worker_manifest

WORKER_PATH = "/usr/local/bin/reality-sni-target-worker"
IDENTITY_COMMAND = [WORKER_PATH, "identity"]
BOOTSTRAP_SCRIPT_NAME = "worker_bootstrap.py"
WRAPPER_NAME = "reality-sni-target-worker"
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|token|secret|authorization|cookie|private[_ -]?key|api[_ -]?key)\b(\s*[:=]\s*)(\S+)"
)


def sanitize_stderr(stderr: bytes, max_chars: int = 600) -> str:
    text = stderr.decode("utf-8", errors="replace")
    text = SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", text)
    return " ".join(text.split())[:max_chars]


def _run(args: list[str], *, timeout: int, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)


def _json_output(stdout: bytes) -> dict[str, Any] | None:
    try:
        value = json.loads(stdout.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def probe_worker(alias: str, expected_manifest: str, expected_wrapper_sha256: str | None = None, *, timeout: int = 20) -> dict[str, Any]:
    """Read the fixed worker identity without candidate traffic."""
    try:
        proc = _run(["ssh", "-T", alias, *IDENTITY_COMMAND], timeout=max(5, timeout))
    except FileNotFoundError:
        return {"status": "CONTROLLER_SSH_UNAVAILABLE", "ready": False, "returncode": None, "stderr_summary": "ssh executable unavailable"}
    except subprocess.TimeoutExpired:
        return {"status": "WORKER_PROBE_TIMEOUT", "ready": False, "returncode": None, "stderr_summary": ""}

    stderr_summary = sanitize_stderr(proc.stderr)
    parsed = _json_output(proc.stdout)
    base: dict[str, Any] = {
        "ready": False,
        "returncode": proc.returncode,
        "stderr_summary": stderr_summary,
        "worker": None,
    }

    if isinstance(parsed, dict):
        worker = parsed.get("worker") if isinstance(parsed.get("worker"), dict) else {}
        base["worker"] = worker
        if parsed.get("status") == "IDENTITY" and parsed.get("schema_version") == JOB_SCHEMA_VERSION:
            exact = (
                worker.get("protocol") == WORKER_PROTOCOL
                and worker.get("implementation_version") == IMPLEMENTATION_VERSION
                and worker.get("manifest") == expected_manifest
                and (expected_wrapper_sha256 is None or worker.get("wrapper_sha256") == expected_wrapper_sha256)
            )
            base.update(status="READY" if exact else "STALE_WORKER", ready=exact)
            return base

    lower = stderr_summary.casefold()
    if proc.returncode in {126, 127} and any(marker in lower for marker in ("no such file or directory", "not found", "command not found", "bad interpreter")):
        base.update(status="WORKER_MISSING")
    elif proc.returncode == 64 and "fixed_command_required" in lower:
        # v4/v4.1 wrapper: recognized later by the fixed-path installer using exact hashes.
        base.update(status="LEGACY_WRAPPER")
    elif proc.returncode == 255:
        base.update(status="SSH_REMOTE_FAILED")
    elif proc.returncode == 126 and "permission denied" in lower:
        base.update(status="WORKER_NOT_EXECUTABLE")
    else:
        base.update(status="WORKER_IDENTITY_UNKNOWN")
    return base


def _add_tar_bytes(tf: tarfile.TarFile, name: str, data: bytes, mode: int) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    import io
    tf.addfile(info, io.BytesIO(data))


def build_payload_archive(scripts_dir: Path, output_path: Path) -> dict[str, str]:
    manifest = compute_worker_manifest(scripts_dir)
    wrapper = scripts_dir / WRAPPER_NAME
    if not wrapper.is_file() or wrapper.is_symlink():
        raise FileNotFoundError(WRAPPER_NAME)
    wrapper_data = wrapper.read_bytes()
    wrapper_sha = hashlib.sha256(wrapper_data).hexdigest()
    with tarfile.open(output_path, "w:gz") as tf:
        from common import TARGET_WORKER_FILES
        for name in TARGET_WORKER_FILES:
            data = (scripts_dir / name).read_bytes()
            _add_tar_bytes(tf, name, data, 0o644)
        _add_tar_bytes(tf, WRAPPER_NAME, wrapper_data, 0o755)
    return {"manifest": manifest, "wrapper_sha256": wrapper_sha}


def _transfer_file(alias: str, local: Path, remote: str, *, timeout: int) -> dict[str, Any]:
    if shutil.which("scp") is None:
        return {"status": "CONTROLLER_SCP_UNAVAILABLE", "returncode": None, "stderr_summary": "scp executable unavailable"}
    try:
        proc = _run(["scp", "-q", str(local), f"{alias}:{remote}"], timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "WORKER_BOOTSTRAP_TRANSFER_TIMEOUT", "returncode": None, "stderr_summary": ""}
    summary = sanitize_stderr(proc.stderr)
    if proc.returncode != 0:
        return {"status": "WORKER_BOOTSTRAP_TRANSFER_FAILED", "returncode": proc.returncode, "stderr_summary": summary}
    return {"status": "OK", "returncode": 0, "stderr_summary": summary}




def _cleanup_remote_temp(alias: str, paths: list[str], *, timeout: int = 15) -> None:
    safe = [p for p in paths if re.fullmatch(r"/tmp/reality-sni-bootstrap-[0-9a-f]{16}\.(?:tar\.gz|py)", p)]
    if not safe or shutil.which("ssh") is None:
        return
    try:
        _run(["ssh", "-T", alias, "/bin/rm", "-f", *safe], timeout=timeout)
    except Exception:
        return

def bootstrap_worker(alias: str, scripts_dir: Path, *, timeout: int = 120) -> dict[str, Any]:
    """Install/upgrade only the reviewed fixed worker paths on the selected VPS."""
    if shutil.which("ssh") is None:
        return {"status": "CONTROLLER_SSH_UNAVAILABLE", "ok": False}
    bootstrap_script = scripts_dir / BOOTSTRAP_SCRIPT_NAME
    if not bootstrap_script.is_file():
        return {"status": "CONTROLLER_BOOTSTRAP_SCRIPT_MISSING", "ok": False}

    with tempfile.TemporaryDirectory(prefix="reality-sni-bootstrap-") as td:
        local_archive = Path(td) / "payload.tar.gz"
        hashes = build_payload_archive(scripts_dir, local_archive)
        manifest = hashes["manifest"]
        wrapper_sha = hashes["wrapper_sha256"]
        if not HEX64_RE.fullmatch(manifest) or not HEX64_RE.fullmatch(wrapper_sha):
            return {"status": "CONTROLLER_BOOTSTRAP_HASH_INVALID", "ok": False}

        token = manifest[:16]
        remote_archive = f"/tmp/reality-sni-bootstrap-{token}.tar.gz"
        remote_script = f"/tmp/reality-sni-bootstrap-{token}.py"
        transfer_archive = _transfer_file(alias, local_archive, remote_archive, timeout=min(timeout, 90))
        if transfer_archive["status"] != "OK":
            return {"status": transfer_archive["status"], "ok": False, "transfer": transfer_archive}
        transfer_script = _transfer_file(alias, bootstrap_script, remote_script, timeout=min(timeout, 90))
        if transfer_script["status"] != "OK":
            _cleanup_remote_temp(alias, [remote_archive, remote_script])
            return {"status": transfer_script["status"], "ok": False, "transfer": transfer_script}

        command = [
            "ssh", "-T", alias,
            "/usr/bin/python3", remote_script, "install", remote_archive,
            manifest, wrapper_sha, IMPLEMENTATION_VERSION, str(WORKER_PROTOCOL),
        ]
        try:
            proc = _run(command, timeout=max(30, timeout))
        except subprocess.TimeoutExpired:
            _cleanup_remote_temp(alias, [remote_archive, remote_script])
            return {"status": "WORKER_BOOTSTRAP_TIMEOUT", "ok": False}
        parsed = _json_output(proc.stdout)
        stderr_summary = sanitize_stderr(proc.stderr)
        if isinstance(parsed, dict) and parsed.get("status") == "READY" and proc.returncode == 0:
            return {
                "status": "READY",
                "ok": True,
                "action": parsed.get("action"),
                "previous_state": parsed.get("previous_state"),
                "backup": parsed.get("backup"),
                "manifest": parsed.get("manifest"),
                "wrapper_sha256": parsed.get("wrapper_sha256"),
                "returncode": proc.returncode,
                "stderr_summary": stderr_summary,
            }
        code = parsed.get("code") if isinstance(parsed, dict) else None
        _cleanup_remote_temp(alias, [remote_archive, remote_script])
        return {
            "status": str(code or "WORKER_BOOTSTRAP_FAILED"),
            "ok": False,
            "returncode": proc.returncode,
            "stderr_summary": stderr_summary,
            "detail": parsed.get("detail") if isinstance(parsed, dict) else "invalid bootstrap result",
        }


def ensure_worker_ready(
    alias: str,
    scripts_dir: Path,
    *,
    bootstrap_mode: str = "auto",
    probe_timeout: int = 20,
    bootstrap_timeout: int = 120,
) -> dict[str, Any]:
    """Ensure the target exposes the exact reviewed worker before freezing a run."""
    expected_manifest = compute_worker_manifest(scripts_dir)
    wrapper_path = scripts_dir / WRAPPER_NAME
    expected_wrapper_sha256 = hashlib.sha256(wrapper_path.read_bytes()).hexdigest()
    before = probe_worker(alias, expected_manifest, expected_wrapper_sha256, timeout=probe_timeout)
    result: dict[str, Any] = {
        "expected_manifest": expected_manifest,
        "expected_wrapper_sha256": expected_wrapper_sha256,
        "implementation_version": IMPLEMENTATION_VERSION,
        "protocol": WORKER_PROTOCOL,
        "before": before,
        "bootstrap": None,
        "after": None,
        "ready": False,
    }
    if before.get("ready"):
        result.update(status="READY", ready=True, action="ALREADY_READY")
        return result
    if before.get("status") in {"SSH_REMOTE_FAILED", "CONTROLLER_SSH_UNAVAILABLE", "WORKER_PROBE_TIMEOUT"}:
        result.update(status=before.get("status"), action="NONE")
        return result
    if bootstrap_mode != "auto":
        result.update(status="TARGET_WORKER_NOT_READY", action="BOOTSTRAP_DISABLED")
        return result

    boot = bootstrap_worker(alias, scripts_dir, timeout=bootstrap_timeout)
    result["bootstrap"] = boot
    if not boot.get("ok"):
        result.update(status=boot.get("status") or "WORKER_BOOTSTRAP_FAILED", action="BOOTSTRAP_FAILED")
        return result

    after = probe_worker(alias, expected_manifest, expected_wrapper_sha256, timeout=probe_timeout)
    result["after"] = after
    if after.get("ready"):
        result.update(status="READY", ready=True, action=boot.get("action") or "BOOTSTRAPPED")
        return result
    result.update(status="WORKER_POST_BOOTSTRAP_VERIFY_FAILED", action="BOOTSTRAP_VERIFY_FAILED")
    return result
