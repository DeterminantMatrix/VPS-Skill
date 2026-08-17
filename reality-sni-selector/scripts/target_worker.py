#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

_payload = Path(__file__).with_name(Path(__file__).name + ".gz")
_source = gzip.decompress(_payload.read_bytes())
if hashlib.sha256(_source).hexdigest() != "04b2b8627c274a6ef2ae32fffbe372491a606428812af1013e71fd067062a65a":
    raise RuntimeError("WORKER_AUXILIARY_PAYLOAD_HASH_MISMATCH:target_worker.py")
exec(compile(_source, str(_payload), "exec"), globals(), globals())
