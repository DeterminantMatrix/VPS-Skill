#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import target_worker  # noqa: E402


class AutoIncumbentTests(unittest.TestCase):
    def test_jsonc_single_reality_target(self):
        old_files = target_worker.AUTO_CONFIG_FILES
        old_dirs = target_worker.AUTO_CONFIG_DIRS
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = Path(td) / "config.jsonc"
                cfg.write_text(r'''
                {
                  // production inbound
                  "inbounds": [{
                    "type": "vless",
                    "tls": {
                      "enabled": true,
                      "server_name": "mendpoverty.org",
                      "reality": {
                        "enabled": true,
                        "handshake": {"server": "mendpoverty.org", "server_port": 443},
                        "private_key": "secret-should-never-be-returned"
                      }
                    }
                  }]
                }
                ''', encoding="utf-8")
                target_worker.AUTO_CONFIG_FILES = [cfg]
                target_worker.AUTO_CONFIG_DIRS = []
                host, error = target_worker.resolve_auto_incumbent()
                self.assertEqual(host, "mendpoverty.org")
                self.assertIsNone(error)
        finally:
            target_worker.AUTO_CONFIG_FILES = old_files
            target_worker.AUTO_CONFIG_DIRS = old_dirs

    def test_multiple_targets_fail_closed(self):
        old_files = target_worker.AUTO_CONFIG_FILES
        old_dirs = target_worker.AUTO_CONFIG_DIRS
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = Path(td) / "config.json"
                cfg.write_text('''{"inbounds":[
                  {"tls":{"reality":{"handshake":{"server":"a.example.org"}}}},
                  {"tls":{"reality":{"handshake":{"server":"b.example.org"}}}}
                ]}''', encoding="utf-8")
                target_worker.AUTO_CONFIG_FILES = [cfg]
                target_worker.AUTO_CONFIG_DIRS = []
                host, error = target_worker.resolve_auto_incumbent()
                self.assertIsNone(host)
                self.assertEqual(error, "AUTO_INCUMBENT_AMBIGUOUS")
        finally:
            target_worker.AUTO_CONFIG_FILES = old_files
            target_worker.AUTO_CONFIG_DIRS = old_dirs


if __name__ == "__main__":
    unittest.main()
