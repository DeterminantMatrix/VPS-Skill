#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from common import is_public_ipv4, validate_hostname

KEY_RE = re.compile(r"(?i)\b(private|public)(?:\s*key)?\s*[:=]\s*([A-Za-z0-9_-]{20,})")

# Prefer deterministic, reviewed installation paths. PATH is fallback only.
SING_BOX_FIXED_PATHS = (
    "/etc/sing-box/bin/sing-box",
    "/usr/bin/sing-box",
    "/usr/local/lib/sing-box/sing-box",
    "/opt/sing-box/bin/sing-box",
    "/opt/sing-box/sing-box",
)


def _is_executable_elf(path: str) -> bool:
    try:
        real = os.path.realpath(path)
        if not os.path.isfile(real) or not os.access(real, os.X_OK):
            return False
        with open(real, "rb") as handle:
            return handle.read(4) == b"\x7fELF"
    except OSError:
        return False


def find_sing_box() -> str | None:
    candidates = list(SING_BOX_FIXED_PATHS)
    discovered = shutil.which("sing-box")
    if discovered:
        candidates.append(discovered)
    seen: set[str] = set()
    for candidate in candidates:
        real = os.path.realpath(candidate)
        if real in seen:
            continue
        seen.add(real)
        if _is_executable_elf(real):
            return real
    return None


def environment() -> dict[str, Any]:
    discovered = shutil.which("sing-box")
    sing = find_sing_box()
    curl = shutil.which("curl")
    result = {"sing_box": sing or discovered, "curl": curl, "ready": False, "reason": None, "version": None}
    if not sing:
        result["reason"] = "SING_BOX_NOT_ELF" if discovered else "SING_BOX_MISSING"
        return result
    if not curl:
        result["reason"] = "CURL_MISSING"
        return result
    try:
        proc = subprocess.run([sing, "version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5, check=False)
        line = (proc.stdout or proc.stderr or "").splitlines()
        result["version"] = line[0][:200] if line else None
    except Exception:
        pass
    result["ready"] = True
    return result


def _keypair(binary: str) -> tuple[str, str]:
    proc = subprocess.run([binary, "generate", "reality-keypair"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=10, check=False)
    if proc.returncode != 0:
        raise RuntimeError("reality key generation failed")
    found: dict[str, str] = {}
    for kind, value in KEY_RE.findall(proc.stdout + "\n" + proc.stderr):
        found[kind.lower()] = value
    if "private" in found and "public" in found:
        return found["private"], found["public"]
    tokens = [t.strip() for t in re.split(r"\s+", proc.stdout.strip()) if re.fullmatch(r"[A-Za-z0-9_-]{20,}", t.strip())]
    if len(tokens) >= 2:
        return tokens[0], tokens[1]
    raise RuntimeError("unrecognized reality keypair output")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_secret_json(path: Path, payload: dict[str, Any]) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _configs(hostname: str, ip: str, server_port: int, socks_port: int, private_key: str, public_key: str, user_uuid: str, short_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    server = {
        "log": {"disabled": True},
        "inbounds": [{
            "type": "vless", "tag": "reality-in", "listen": "127.0.0.1", "listen_port": server_port,
            "users": [{"uuid": user_uuid, "flow": "xtls-rprx-vision"}],
            "tls": {
                "enabled": True,
                "server_name": hostname,
                "reality": {
                    "enabled": True,
                    "handshake": {"server": ip, "server_port": 443},
                    "private_key": private_key,
                    "short_id": [short_id],
                },
            },
        }],
        "outbounds": [{"type": "direct", "tag": "direct"}],
        "route": {"final": "direct"},
    }
    client = {
        "log": {"disabled": True},
        "inbounds": [{"type": "socks", "tag": "socks-in", "listen": "127.0.0.1", "listen_port": socks_port}],
        "outbounds": [{
            "type": "vless", "tag": "reality-out", "server": "127.0.0.1", "server_port": server_port,
            "uuid": user_uuid, "flow": "xtls-rprx-vision", "network": "tcp",
            "tls": {
                "enabled": True,
                "server_name": hostname,
                "utls": {"enabled": True, "fingerprint": "chrome"},
                "reality": {"enabled": True, "public_key": public_key, "short_id": short_id},
            },
        }],
        "route": {"final": "reality-out"},
    }
    return server, client


def _check(binary: str, config: Path) -> bool:
    try:
        proc = subprocess.run([binary, "check", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=10, check=False)
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.15):
            return True
    except OSError:
        return False


def _wait_port(port: int, proc: subprocess.Popen[bytes], timeout: float = 4.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        if _port_open(port):
            return True
        time.sleep(0.08)
    return False


def _stop_process(proc: subprocess.Popen[bytes] | None) -> bool:
    if proc is None:
        return True
    try:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=2)
        return proc.poll() is not None
    except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
        return proc.poll() is not None


def run_attempt(hostname: str, ip: str, env: dict[str, Any] | None = None) -> dict[str, Any]:
    hostname = validate_hostname(hostname)
    if not is_public_ipv4(ip):
        return {"transport_success": False, "cleanup_success": True, "code": "ERROR:INVALID_REALITY_IPV4", "failure_stage": "INPUT", "http_status": None, "elapsed_ms": None, "curl_exit_code": None}
    env = env or environment()
    if not env.get("ready"):
        return {"transport_success": False, "cleanup_success": True, "code": f"ERROR:{env.get('reason') or 'REALITY_ENV_UNAVAILABLE'}", "failure_stage": "ENVIRONMENT", "http_status": None, "elapsed_ms": None, "curl_exit_code": None}
    binary = str(env["sing_box"])
    curl = str(env["curl"])
    tmp = Path(tempfile.mkdtemp(prefix="reality-sni-test-"))
    os.chmod(tmp, 0o700)
    server_proc: subprocess.Popen[bytes] | None = None
    client_proc: subprocess.Popen[bytes] | None = None
    server_port = _free_port()
    socks_port = _free_port()
    while socks_port == server_port:
        socks_port = _free_port()
    result = {
        "transport_success": False,
        "cleanup_success": False,
        "code": "ERROR:REALITY_UNKNOWN",
        "failure_stage": "UNKNOWN",
        "http_status": None,
        "elapsed_ms": None,
        "curl_exit_code": None,
        "server_port": server_port,
        "socks_port": socks_port,
    }
    try:
        private_key, public_key = _keypair(binary)
        user_uuid = str(uuid.uuid4())
        short_id = secrets.token_hex(8)
        server_cfg, client_cfg = _configs(hostname, ip, server_port, socks_port, private_key, public_key, user_uuid, short_id)
        server_path = tmp / "server.json"
        client_path = tmp / "client.json"
        _write_secret_json(server_path, server_cfg)
        _write_secret_json(client_path, client_cfg)
        if not _check(binary, server_path) or not _check(binary, client_path):
            result["code"] = "ERROR:REALITY_CONFIG_INVALID"
            result["failure_stage"] = "CONFIG_CHECK"
            return result
        server_proc = subprocess.Popen([binary, "run", "-c", str(server_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        if not _wait_port(server_port, server_proc):
            result["code"] = "ERROR:REALITY_SERVER_START"
            result["failure_stage"] = "SERVER_START"
            return result
        client_proc = subprocess.Popen([binary, "run", "-c", str(client_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        if not _wait_port(socks_port, client_proc):
            result["code"] = "ERROR:REALITY_CLIENT_START"
            result["failure_stage"] = "CLIENT_START"
            return result
        start = time.perf_counter()
        proc = subprocess.run([
            curl, "-sS", "-I", "-o", "/dev/null", "--max-time", "8", "--connect-timeout", "5",
            "--socks5", f"127.0.0.1:{socks_port}", "--resolve", f"{hostname}:443:{ip}",
            "-w", "%{http_code}\t%{time_total}", f"https://{hostname}/",
        ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10, check=False)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        status = None
        parts = (proc.stdout or "").strip().split("\t")
        if parts and parts[0].isdigit():
            status = int(parts[0])
        result["http_status"] = status
        result["elapsed_ms"] = round(elapsed_ms, 3)
        result["curl_exit_code"] = int(proc.returncode)
        result["transport_success"] = proc.returncode == 0 and status not in (None, 0)
        if result["transport_success"]:
            result["code"] = "OK"
            result["failure_stage"] = None
        else:
            result["code"] = "ERROR:REALITY_PROXY_HEAD_TRANSPORT"
            result["failure_stage"] = "PROXY_HEAD"
        return result
    except subprocess.TimeoutExpired:
        result["code"] = "ERROR:REALITY_TIMEOUT"
        result["failure_stage"] = "PROXY_HEAD"
        return result
    except Exception as exc:
        result["code"] = f"ERROR:REALITY_{type(exc).__name__.upper()}"
        result["failure_stage"] = "INTERNAL"
        return result
    finally:
        client_ok = _stop_process(client_proc)
        server_ok = _stop_process(server_proc)
        time.sleep(0.05)
        ports_closed = not _port_open(server_port) and not _port_open(socks_port)
        try:
            shutil.rmtree(tmp)
            files_removed = not tmp.exists()
        except OSError:
            files_removed = False
        result["cleanup_success"] = bool(client_ok and server_ok and ports_closed and files_removed)
        if not result["cleanup_success"]:
            result["code"] = "TARGET_DIRTY_STATE"
            result["failure_stage"] = "CLEANUP"


def run_candidate(hostname: str, ips: list[str], attempts: int = 5, env: dict[str, Any] | None = None) -> dict[str, Any]:
    usable = [ip for ip in ips if is_public_ipv4(ip)]
    if not usable:
        return {
            "hostname": hostname,
            "attempts": [],
            "attempt_count": 0,
            "transport_successes": 0,
            "cleanup_successes": 0,
            "passed": False,
            "dirty": False,
            "code": "ERROR:INVALID_REALITY_IPV4",
            "failure_counts": {"INPUT": 1},
            "dominant_failure_stage": "INPUT",
        }
    env = env or environment()
    rows = []
    dirty = False
    for idx in range(attempts):
        row = run_attempt(hostname, usable[idx % len(usable)], env=env)
        row["attempt"] = idx + 1
        row["ip"] = usable[idx % len(usable)]
        rows.append(row)
        if not row.get("cleanup_success"):
            dirty = True
            break
    successes = sum(1 for r in rows if r.get("transport_success"))
    cleanups = sum(1 for r in rows if r.get("cleanup_success"))
    passed = len(rows) == attempts and successes == attempts and cleanups == attempts and not dirty
    failure_counter = Counter(str(r.get("failure_stage")) for r in rows if r.get("failure_stage"))
    dominant = failure_counter.most_common(1)[0][0] if failure_counter else None
    code = "OK" if passed else "TARGET_DIRTY_STATE" if dirty else "HARD:REALITY_FAILED"
    return {
        "hostname": hostname,
        "attempts": rows,
        "attempt_count": len(rows),
        "transport_successes": successes,
        "cleanup_successes": cleanups,
        "passed": passed,
        "dirty": dirty,
        "code": code,
        "failure_counts": dict(sorted(failure_counter.items())),
        "dominant_failure_stage": dominant,
    }
