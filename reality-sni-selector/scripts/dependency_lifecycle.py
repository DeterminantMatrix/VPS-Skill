#!/usr/bin/env python3
"""Automatic temporary lifecycle for the target-side dig measurement tool."""
from __future__ import annotations

import re
import shlex
import subprocess
from typing import Any


PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._~-]*(:[A-Za-z0-9_.-]+)?$")
DIG_PROBE = (
    'if command -v dig >/dev/null 2>&1; then '
    'dig_path=$(command -v dig); '
    'dig_version=$(dig -v 2>&1 | head -n 1); '
    'if dig -v >/dev/null 2>&1 && dig +time=2 +tries=1 example.com >/dev/null 2>&1; then '
    'echo STATUS=READY; else echo STATUS=BROKEN; fi; '
    'echo DIG_PATH=$dig_path; printf "DIG_VERSION=%s\\n" "$dig_version"; '
    'else echo STATUS=MISSING; fi'
)


def _run(args: list[str], *, timeout: int) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)


def _remote(alias: str, command: str, *, timeout: int) -> tuple[int, str, str]:
    proc = _run(["ssh", "-T", alias, f"LC_ALL=C; {command}"], timeout=max(5, timeout))
    return proc.returncode, proc.stdout.decode("utf-8", errors="replace"), proc.stderr.decode("utf-8", errors="replace")


def _fields(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.strip().partition("=")
        normalized_key = key.casefold()
        if separator and normalized_key and "=" not in normalized_key:
            result[normalized_key] = value
    return result


def _stderr_summary(stderr: str, max_chars: int = 500) -> str:
    return " ".join(stderr.split())[:max_chars]


def _probe(alias: str, *, timeout: int) -> dict[str, Any]:
    returncode, stdout, stderr = _remote(alias, DIG_PROBE, timeout=timeout)
    fields = _fields(stdout)
    status = fields.get("status")
    if returncode == 0 and status in {"READY", "BROKEN", "MISSING"}:
        return {"status": status, **fields}
    return {
        "status": "PROBE_FAILED",
        "returncode": returncode,
        "stderr_summary": _stderr_summary(stderr),
    }


def _prepare_install(alias: str, dig_path: str | None, *, timeout: int) -> dict[str, Any]:
    owner_check = ""
    if dig_path:
        quoted_path = shlex.quote(dig_path)
        owner_check = (
            f'owner=$(dpkg-query -S {quoted_path} 2>/dev/null | cut -d: -f1 || true); '
            'echo OWNER_PACKAGE=$owner; '
            'if [ -n "$owner" ]; then '
            'dpkg-query -W -f="${db:Status-Abbrev}" "$owner" 2>/dev/null | grep -q "^ii" '
            '&& echo MANAGED_EXISTING=yes || echo MANAGED_EXISTING=no; '
            'fi; '
        )
    command = (
        'if command -v apt-get >/dev/null 2>&1; then manager=apt; '
        'elif command -v dnf >/dev/null 2>&1; then manager=unsupported; '
        'elif command -v yum >/dev/null 2>&1; then manager=unsupported; '
        'elif command -v apk >/dev/null 2>&1; then manager=unsupported; '
        'else manager=none; fi; '
        'echo MANAGER=$manager; '
        f'{owner_check}'
        'if [ "$manager" != apt ]; then echo PHASE_STATUS=UNSUPPORTED_MANAGER; exit 0; fi; '
        'if apt-cache show bind9-dnsutils >/dev/null 2>&1; then candidate=bind9-dnsutils; '
        'elif apt-cache show dnsutils >/dev/null 2>&1; then candidate=dnsutils; '
        'else echo PHASE_STATUS=CANDIDATE_UNAVAILABLE; exit 0; fi; '
        'echo CANDIDATE=$candidate; '
        'if [ -n "$dig_path" ] && { [ -z "$owner" ] || [ "$owner" != "$candidate" ]; }; then '
        'echo PHASE_STATUS=BROKEN_UNKNOWN_BINARY; exit 0; fi; '
        'pre_sha=$(dpkg-query -W -f="${binary:Package}\\n" 2>/dev/null | sort | sha256sum | cut -d" " -f1); '
        'echo PRE_PACKAGE_LIST_SHA256=$pre_sha; '
        'installed=no; '
        'dpkg-query -W -f="${db:Status-Abbrev}" "$candidate" 2>/dev/null | grep -q "^ii" && installed=yes; '
        'echo CANDIDATE_INSTALLED=$installed; '
        'if [ "$installed" = yes ] && [ -z "$dig_path" ]; then echo PHASE_STATUS=INCONSISTENT_PACKAGE_STATE; exit 0; fi; '
        'new_packages=$(DEBIAN_FRONTEND=noninteractive apt-get -s --no-install-recommends install "$candidate" 2>/dev/null | '
        'awk \'$1 == "Inst" { print $2 }\' | paste -sd, -); '
        'echo NEW_PACKAGES=$new_packages; '
        'if [ "$installed" = yes ]; then action=REPAIR_EXISTING; elif [ -z "$new_packages" ]; then '
        'echo PHASE_STATUS=NO_INSTALL_PLAN; exit 0; else action=INSTALL_MISSING; fi; '
        'install_output=$(DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$candidate" 2>&1); '
        'install_rc=$?; echo INSTALL_RC=$install_rc; '
        'printf "INSTALL_SUMMARY=%s\\n" "$(printf "%s\\n" "$install_output" | tr "\\n" " " | cut -c1-300)"; '
        'echo PHASE_STATUS=$([ "$install_rc" -eq 0 ] && echo OK || echo FAILED)'
    )
    returncode, stdout, stderr = _remote(alias, command, timeout=timeout)
    fields = _fields(stdout)
    if returncode != 0 or not fields.get("phase_status"):
        return {
            "phase_status": "REMOTE_FAILED",
            "returncode": returncode,
            "stderr_summary": _stderr_summary(stderr),
        }
    return fields


def ensure_dig(alias: str, *, timeout: int = 180) -> dict[str, Any]:
    """Ensure a functional dig, installing only an exact temporary apt package set."""
    before = _probe(alias, timeout=min(timeout, 30))
    result: dict[str, Any] = {"before": before}
    if before.get("status") == "READY":
        result.update(action="NONE", required=False, status="READY", ok=True)
        return result
    if before.get("status") not in {"MISSING", "BROKEN"}:
        result.update(status=str(before.get("status")), action="NONE", ok=False)
        return result

    prepared = _prepare_install(alias, before.get("dig_path"), timeout=timeout)
    result["prepare"] = prepared
    phase_status = prepared.get("phase_status")
    if phase_status == "UNSUPPORTED_MANAGER":
        result.update(status="DIG_AUTO_INSTALL_UNSUPPORTED", action="NONE", ok=False)
        return result
    if phase_status == "CANDIDATE_UNAVAILABLE":
        result.update(status="DIG_PACKAGE_CANDIDATE_UNAVAILABLE", action="NONE", ok=False)
        return result
    if phase_status == "INCONSISTENT_PACKAGE_STATE":
        result.update(status="DIG_INCONSISTENT_PACKAGE_STATE", action="NONE", ok=False)
        return result
    if phase_status == "NO_INSTALL_PLAN":
        result.update(status="DIG_NO_INSTALL_PLAN", action="NONE", ok=False)
        return result
    if phase_status == "BROKEN_UNKNOWN_BINARY":
        result.update(status="DIG_BROKEN_UNKNOWN_BINARY", action="NONE", ok=False)
        return result
    if phase_status != "OK":
        result.update(status=f"DIG_AUTO_INSTALL_{phase_status}", action="NONE", ok=False)
        return result

    raw_packages = str(prepared.get("new_packages") or "")
    packages = sorted({item for item in raw_packages.split(",") if item})
    invalid = [item for item in packages if not PACKAGE_RE.fullmatch(item)]
    if invalid:
        result.update(status="DIG_INSTALL_PLAN_INVALID", action="NONE", ok=False, invalid_packages=invalid)
        return result

    after = _probe(alias, timeout=min(timeout, 30))
    result["after"] = after
    if after.get("status") != "READY":
        result.update(status="DIG_POST_INSTALL_VERIFY_FAILED", action="NONE", ok=False)
        return result

    repaired = prepared.get("candidate_installed") == "yes"
    result.update(
        status="READY",
        action="REPAIRED_EXISTING" if repaired else "INSTALLED",
        required=True,
        cleanup_required=not repaired,
        package_manager=prepared.get("manager"),
        pre_package_list_sha256=prepared.get("pre_package_list_sha256"),
        packages=packages,
        ok=True,
    )
    return result


def restore_dig(alias: str, lifecycle: dict[str, Any], *, timeout: int = 180) -> dict[str, Any]:
    """Remove only packages newly introduced by this run and verify exact restoration."""
    if not lifecycle.get("required") or not lifecycle.get("cleanup_required"):
        return {**lifecycle, "cleanup": {"status": "NOT_REQUIRED", "ok": True}}
    if lifecycle.get("package_manager") != "apt":
        return {**lifecycle, "cleanup": {"status": "UNSUPPORTED_CLEANUP", "ok": False}}

    packages = [str(item) for item in lifecycle.get("packages") or []]
    if not packages or any(not PACKAGE_RE.fullmatch(item) for item in packages):
        return {**lifecycle, "cleanup": {"status": "INVALID_PACKAGE_LIST", "ok": False}}
    expected_sha = str(lifecycle.get("pre_package_list_sha256") or "")
    quoted = " ".join(shlex.quote(item) for item in packages)
    command = (
        f'remove_output=$(DEBIAN_FRONTEND=noninteractive apt-get purge -y {quoted} 2>&1); remove_rc=$?; '
        'echo REMOVE_RC=$remove_rc; '
        'dirty=no; '
        f'for package in {quoted}; do '
        'dpkg-query -W -f="${db:Status-Abbrev}" "$package" 2>/dev/null | grep -q "^ii" && dirty=yes; done; '
        'echo DIRTY=$dirty; '
        'post_sha=$(dpkg-query -W -f="${binary:Package}\\n" 2>/dev/null | sort | sha256sum | cut -d" " -f1); '
        'echo POST_PACKAGE_LIST_SHA256=$post_sha; '
        'echo PHASE_STATUS=$([ "$remove_rc" -eq 0 ] && [ "$dirty" = no ] && [ "$post_sha" = "' + expected_sha + '" ] && echo OK || echo FAILED)'
    )
    returncode, stdout, stderr = _remote(alias, command, timeout=timeout)
    cleanup = _fields(stdout)
    if returncode != 0 or cleanup.get("phase_status") != "OK":
        cleanup.update(
            status="TARGET_DIRTY_STATE",
            ok=False,
            returncode=returncode,
            stderr_summary=_stderr_summary(stderr),
        )
    else:
        cleanup.update(status="RESTORED", ok=True)
    return {**lifecycle, "cleanup": cleanup}
