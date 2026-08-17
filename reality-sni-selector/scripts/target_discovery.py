#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

_payload = Path(__file__).with_name(Path(__file__).name + ".gz")
_source = gzip.decompress(_payload.read_bytes())
if hashlib.sha256(_source).hexdigest() != "6a77bcea009c60741215368d6aa7ddaa6b46715adb8ad6940db399cee45dcab2":
    raise RuntimeError("WORKER_AUXILIARY_PAYLOAD_HASH_MISMATCH:target_discovery.py")
exec(compile(_source, str(_payload), "exec"), globals(), globals())
