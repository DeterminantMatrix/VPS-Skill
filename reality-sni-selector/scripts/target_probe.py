#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

_payload = Path(__file__).with_name(Path(__file__).name + ".gz")
_source = gzip.decompress(_payload.read_bytes())
if hashlib.sha256(_source).hexdigest() != "cf4b32a392493c716567dbf2cd78a75883859c80edb2dcd3ac678ec8417e60f1":
    raise RuntimeError("WORKER_AUXILIARY_PAYLOAD_HASH_MISMATCH:target_probe.py")
exec(compile(_source, str(_payload), "exec"), globals(), globals())
