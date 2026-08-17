#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

_payload = Path(__file__).with_name(Path(__file__).name + ".gz")
_source = gzip.decompress(_payload.read_bytes())
if hashlib.sha256(_source).hexdigest() != "ae8ad00c722d685f353abccc616e1ef475fea34bcc76f2e4410f6a97a385a5ce":
    raise RuntimeError("WORKER_AUXILIARY_PAYLOAD_HASH_MISMATCH:target_probe.py")
exec(compile(_source, str(_payload), "exec"), globals(), globals())
