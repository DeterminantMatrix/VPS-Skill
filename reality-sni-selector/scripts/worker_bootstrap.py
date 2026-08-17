#!/usr/bin/env python3
"""Target-side fixed-path installer for the Reality SNI worker.

This installer is transferred by the controller and may only manage the
reviewed Reality SNI worker paths. It never touches production sing-box or
network configuration.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

MANAGED_BY = "reality-sni-selector"
TARGET_FILES = (
    "common.py",
    "target_discovery.py",
    "target_probe.py",
    "benchmark.py",
    "reality_selftest.py",
    "target_worker.py",
)
AUX_FILES = (
    "target_discovery.py.gz",
    "target_probe.py.gz",
    "target_worker.py.gz",
)
AUX_SHA256 = {
    "target_discovery.py.gz": "83d075c434f4ffcf441cb5ba8921786fdc4a2c7b7470edb4af7cb1a2bf663ff3",
    "target_probe.py.gz": "901418fc2e306f7b5824b46d90587a3125daf2e70a8bb04b7c71eff109d7dcad",
    "target_worker.py.gz": "58c05510c4016dd115b78c47213aaafca5037abaab9a9a15ee73f10ebdbb5fad",
}
WRAPPER_NAME = "reality-sni-target-worker"
DEFAULT_INSTALL_DIR = Path("/opt/reality-sni-selector")
DEFAULT_WRAPPER_PATH = Path("/usr/local/bin/reality-sni-target-worker")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^[0-9]+(?:\.[0-9]+){1,2}$")

# Known installs produced by earlier reviewed v4/v4.1 packages. These builds
# predate .managed.json, so exact manifests allow a one-time managed upgrade.
LEGACY_MANAGED_MANIFESTS = {
    "d47e9943ebbd2959444cfd3e7d519775865a0d0df5f233bf407fa9fd60d395ec",  # v4
    "e636f7bf9e2d840d4adc757ca389391f730fa2596365e78f76243ea3620a13e9",  # v4.1
}
LEGACY_WRAPPER_SHA256 = {
    "1d806627760627203846381d301a9988870446e89629c70a71c15a0d1f012fb7",
}


class BootstrapError(RuntimeError):
    def __init__(self, code: str, detail: str | None = None):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_manifest(directory: Path) -> str:
    digest = hashlib.sha256()
    for name in TARGET_FILES:
        path = directory / name
        if not path.is_file() or path.is_symlink():
            raise BootstrapError("PAYLOAD_INVALID", f"missing/non-regular worker file: {name}")
        data = path.read_bytes()
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(data)).encode("ascii"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


def auxiliary_payloads_ok(directory: Path) -> bool:
    for name in AUX_FILES:
        path = directory / name
        if not path.is_file() or path.is_symlink():
            return False
        if _sha256(path.read_bytes()) != AUX_SHA256[name]:
            return False
    return True


def wrapper_sha(path: Path) -> str | None:
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise BootstrapError("WORKER_PATH_CONFLICT", "wrapper path is not a regular file")
    return _sha256(path.read_bytes())


def _read_marker(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise BootstrapError("WORKER_PATH_CONFLICT", "managed marker is not a regular file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise BootstrapError("WORKER_PATH_CONFLICT", f"managed marker unreadable: {type(exc).__name__}") from exc
    if not isinstance(data, dict) or data.get("managed_by") != MANAGED_BY:
        raise BootstrapError("WORKER_PATH_CONFLICT", "managed marker ownership mismatch")
    return data


def classify_existing(
    install_dir: Path,
    wrapper_path: Path,
    *,
    legacy_manifests: set[str] | None = None,
    legacy_wrapper_hashes: set[str] | None = None,
) -> dict[str, Any]:
    legacy_manifests = LEGACY_MANAGED_MANIFESTS if legacy_manifests is None else legacy_manifests
    legacy_wrapper_hashes = LEGACY_WRAPPER_SHA256 if legacy_wrapper_hashes is None else legacy_wrapper_hashes
    marker_path = install_dir / ".managed.json"

    install_exists = install_dir.exists()
    wrapper_exists = wrapper_path.exists()
    if not install_exists and not wrapper_exists:
        return {"state": "ABSENT", "manifest": None, "wrapper_sha256": None}
    if install_exists and (not install_dir.is_dir() or install_dir.is_symlink()):
        raise BootstrapError("WORKER_PATH_CONFLICT", "install path is not a regular directory")

    marker = _read_marker(marker_path) if install_exists else None
    existing_manifest = None
    if install_exists:
        try:
            existing_manifest = compute_manifest(install_dir)
        except BootstrapError:
            if marker is None:
                raise BootstrapError("WORKER_PATH_CONFLICT", "unmanaged/incomplete worker directory")
    existing_wrapper_sha = wrapper_sha(wrapper_path)

    if marker is not None:
        return {
            "state": "MANAGED",
            "manifest": existing_manifest,
            "wrapper_sha256": existing_wrapper_sha,
            "marker": marker,
        }

    legacy_worker = existing_manifest in legacy_manifests if existing_manifest else False
    legacy_wrapper = existing_wrapper_sha in legacy_wrapper_hashes if existing_wrapper_sha else True
    if legacy_worker and legacy_wrapper:
        return {
            "state": "LEGACY_MANAGED",
            "manifest": existing_manifest,
            "wrapper_sha256": existing_wrapper_sha,
        }
    raise BootstrapError("WORKER_PATH_CONFLICT", "existing worker paths are not a recognized managed installation")


def _read_payload(archive: Path, extract_dir: Path) -> tuple[Path, Path]:
    allowed = set(TARGET_FILES) | set(AUX_FILES) | {WRAPPER_NAME}
    try:
        with tarfile.open(archive, "r:gz") as tf:
            members = tf.getmembers()
            names = [m.name for m in members]
            if set(names) != allowed or len(names) != len(allowed):
                raise BootstrapError("PAYLOAD_INVALID", "payload member set mismatch")
            for member in members:
                if not member.isfile() or member.issym() or member.islnk() or "/" in member.name or member.name.startswith("."):
                    raise BootstrapError("PAYLOAD_INVALID", f"unsafe payload member: {member.name}")
                source = tf.extractfile(member)
                if source is None:
                    raise BootstrapError("PAYLOAD_INVALID", f"unreadable payload member: {member.name}")
                data = source.read(2_000_001)
                if len(data) > 2_000_000:
                    raise BootstrapError("PAYLOAD_INVALID", f"payload member too large: {member.name}")
                target = extract_dir / member.name
                target.write_bytes(data)
                target.chmod(0o755 if member.name == WRAPPER_NAME else 0o644)
    except BootstrapError:
        raise
    except Exception as exc:
        raise BootstrapError("PAYLOAD_INVALID", type(exc).__name__) from exc
    return extract_dir, extract_dir / WRAPPER_NAME


def _copy_worker_files(source_dir: Path, stage_dir: Path) -> None:
    for name in (*TARGET_FILES, *AUX_FILES):
        source = source_dir / name
        target = stage_dir / name
        shutil.copyfile(source, target)
        target.chmod(0o644)


def install_payload(
    archive: Path,
    expected_manifest: str,
    expected_wrapper_sha256: str,
    implementation_version: str,
    worker_protocol: int,
    *,
    install_dir: Path = DEFAULT_INSTALL_DIR,
    wrapper_path: Path = DEFAULT_WRAPPER_PATH,
    legacy_manifests: set[str] | None = None,
    legacy_wrapper_hashes: set[str] | None = None,
) -> dict[str, Any]:
    if not HEX64_RE.fullmatch(expected_manifest) or not HEX64_RE.fullmatch(expected_wrapper_sha256):
        raise BootstrapError("BOOTSTRAP_ARGUMENT_INVALID", "invalid expected hash")
    if not VERSION_RE.fullmatch(implementation_version) or not isinstance(worker_protocol, int) or worker_protocol <= 0:
        raise BootstrapError("BOOTSTRAP_ARGUMENT_INVALID", "invalid protocol/version")
    if os.geteuid() != 0 and install_dir == DEFAULT_INSTALL_DIR and wrapper_path == DEFAULT_WRAPPER_PATH:
        raise BootstrapError("BOOTSTRAP_PERMISSION_DENIED", "root privileges are required for fixed worker paths")

    archive = archive.resolve()
    if not archive.is_file():
        raise BootstrapError("PAYLOAD_INVALID", "bootstrap archive missing")

    with tempfile.TemporaryDirectory(prefix="reality-sni-payload-") as td:
        extracted = Path(td)
        payload_dir, payload_wrapper = _read_payload(archive, extracted)
        payload_manifest = compute_manifest(payload_dir)
        payload_wrapper_sha = _sha256(payload_wrapper.read_bytes())
        if payload_manifest != expected_manifest or payload_wrapper_sha != expected_wrapper_sha256 or not auxiliary_payloads_ok(payload_dir):
            raise BootstrapError("PAYLOAD_HASH_MISMATCH", "payload does not match controller expectation")

        existing = classify_existing(
            install_dir,
            wrapper_path,
            legacy_manifests=legacy_manifests,
            legacy_wrapper_hashes=legacy_wrapper_hashes,
        )
        if existing.get("state") == "MANAGED" and existing.get("manifest") == expected_manifest and existing.get("wrapper_sha256") == expected_wrapper_sha256 and auxiliary_payloads_ok(install_dir):
            return {
                "status": "READY",
                "action": "ALREADY_CURRENT",
                "manifest": expected_manifest,
                "wrapper_sha256": expected_wrapper_sha256,
                "implementation_version": implementation_version,
                "protocol": worker_protocol,
                "backup": None,
            }

        install_parent = install_dir.parent
        wrapper_parent = wrapper_path.parent
        install_parent.mkdir(parents=True, exist_ok=True)
        wrapper_parent.mkdir(parents=True, exist_ok=True)
        stage_dir = Path(tempfile.mkdtemp(prefix=".reality-sni-selector.stage-", dir=str(install_parent)))
        wrapper_fd, wrapper_stage_name = tempfile.mkstemp(prefix=".reality-sni-target-worker.stage-", dir=str(wrapper_parent))
        os.close(wrapper_fd)
        wrapper_stage = Path(wrapper_stage_name)
        backup_root: Path | None = None
        previous_wrapper_existed = wrapper_path.exists()
        old_install_moved = False
        new_install_activated = False
        new_wrapper_activated = False

        try:
            _copy_worker_files(payload_dir, stage_dir)
            marker = {
                "managed_by": MANAGED_BY,
                "protocol": worker_protocol,
                "implementation_version": implementation_version,
                "manifest": expected_manifest,
                "wrapper_sha256": expected_wrapper_sha256,
                "installed_at_unix": int(time.time()),
                "previous_state": existing.get("state"),
                "previous_manifest": existing.get("manifest"),
            }
            marker_path = stage_dir / ".managed.json"
            marker_path.write_text(json.dumps(marker, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            marker_path.chmod(0o600)
            shutil.copyfile(payload_wrapper, wrapper_stage)
            wrapper_stage.chmod(0o755)
            if compute_manifest(stage_dir) != expected_manifest or not auxiliary_payloads_ok(stage_dir) or _sha256(wrapper_stage.read_bytes()) != expected_wrapper_sha256:
                raise BootstrapError("STAGE_VERIFY_FAILED")

            if install_dir.exists() or wrapper_path.exists():
                token = f"{int(time.time())}-{os.getpid()}"
                backup_root = install_parent / f"reality-sni-selector.backup-{token}"
                backup_root.mkdir(mode=0o700)
                if install_dir.exists():
                    os.replace(install_dir, backup_root / "worker")
                    old_install_moved = True
                if wrapper_path.exists():
                    shutil.copy2(wrapper_path, backup_root / WRAPPER_NAME)

            os.replace(stage_dir, install_dir)
            new_install_activated = True
            os.replace(wrapper_stage, wrapper_path)
            new_wrapper_activated = True
            if compute_manifest(install_dir) != expected_manifest or not auxiliary_payloads_ok(install_dir) or wrapper_sha(wrapper_path) != expected_wrapper_sha256:
                raise BootstrapError("POST_INSTALL_VERIFY_FAILED")

            action = "INSTALLED" if existing.get("state") == "ABSENT" else "UPGRADED"
            return {
                "status": "READY",
                "action": action,
                "previous_state": existing.get("state"),
                "manifest": expected_manifest,
                "wrapper_sha256": expected_wrapper_sha256,
                "implementation_version": implementation_version,
                "protocol": worker_protocol,
                "backup": str(backup_root) if backup_root else None,
            }
        except Exception:
            try:
                if new_install_activated and install_dir.exists():
                    shutil.rmtree(install_dir, ignore_errors=True)
                if old_install_moved and backup_root and (backup_root / "worker").exists():
                    os.replace(backup_root / "worker", install_dir)
                if new_wrapper_activated:
                    if backup_root and (backup_root / WRAPPER_NAME).is_file():
                        shutil.copy2(backup_root / WRAPPER_NAME, wrapper_path)
                        wrapper_path.chmod(0o755)
                    elif not previous_wrapper_existed and wrapper_path.exists():
                        wrapper_path.unlink()
            except Exception as rollback_exc:
                raise BootstrapError("BOOTSTRAP_ROLLBACK_FAILED", type(rollback_exc).__name__)
            raise
        finally:
            if stage_dir.exists():
                shutil.rmtree(stage_dir, ignore_errors=True)
            try:
                wrapper_stage.unlink()
            except FileNotFoundError:
                pass


def _cleanup_transferred(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink()
        except OSError:
            pass


def main() -> int:
    transferred: list[Path] = []
    try:
        if len(sys.argv) != 7 or sys.argv[1] != "install":
            raise BootstrapError("FIXED_COMMAND_REQUIRED")
        archive = Path(sys.argv[2])
        transferred = [archive, Path(__file__)]
        expected_manifest = sys.argv[3].lower()
        expected_wrapper = sys.argv[4].lower()
        version = sys.argv[5]
        protocol = int(sys.argv[6])
        result = install_payload(archive, expected_manifest, expected_wrapper, version, protocol)
        sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
        return 0
    except BootstrapError as exc:
        sys.stdout.write(json.dumps({"status": "FAILED", "code": exc.code, "detail": exc.detail}, separators=(",", ":")) + "\n")
        return 2
    except Exception as exc:
        sys.stdout.write(json.dumps({"status": "FAILED", "code": "BOOTSTRAP_FAILED", "detail": type(exc).__name__}, separators=(",", ":")) + "\n")
        return 2
    finally:
        _cleanup_transferred(transferred)


if __name__ == "__main__":
    raise SystemExit(main())
