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
    def test_jsonc_single_reality_target_fallback(self):
        old_files = target_worker.FIXED_CONFIG_FILES
        old_dirs = target_worker.FIXED_CONFIG_DIRS
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                proc = root / "proc"
                proc.mkdir()
                cfg = root / "config.jsonc"
                cfg.write_text(r'''
                {
                  // production inbound
                  "inbounds": [{
                    "type": "vless",
                    "tls": {
                      "server_name": "mendpoverty.org",
                      "reality": {"handshake": {"server": "mendpoverty.org", "server_port": 443}}
                    }
                  }]
                }
                ''', encoding="utf-8")
                target_worker.FIXED_CONFIG_FILES = [cfg]
                target_worker.FIXED_CONFIG_DIRS = []
                host, error, info = target_worker.resolve_auto_incumbent(proc_root=proc)
                self.assertEqual(host, "mendpoverty.org")
                self.assertIsNone(error)
                self.assertEqual(info["source"], "FIXED_CONFIG_FALLBACK")
        finally:
            target_worker.FIXED_CONFIG_FILES = old_files
            target_worker.FIXED_CONFIG_DIRS = old_dirs

    def test_multiple_targets_fail_closed(self):
        old_files = target_worker.FIXED_CONFIG_FILES
        old_dirs = target_worker.FIXED_CONFIG_DIRS
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                proc = root / "proc"
                proc.mkdir()
                cfg = root / "config.json"
                cfg.write_text('''{"inbounds":[
                  {"tls":{"reality":{"handshake":{"server":"a.example.org"}}}},
                  {"tls":{"reality":{"handshake":{"server":"b.example.org"}}}}
                ]}''', encoding="utf-8")
                target_worker.FIXED_CONFIG_FILES = [cfg]
                target_worker.FIXED_CONFIG_DIRS = []
                host, error, info = target_worker.resolve_auto_incumbent(proc_root=proc)
                self.assertIsNone(host)
                self.assertEqual(error, "AUTO_INCUMBENT_AMBIGUOUS")
                self.assertEqual(info["candidate_count"], 2)
        finally:
            target_worker.FIXED_CONFIG_FILES = old_files
            target_worker.FIXED_CONFIG_DIRS = old_dirs

    def test_parse_live_config_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            conf = root / "conf"
            conf.mkdir()
            a = conf / "10-in.json"
            b = conf / "20-route.jsonc"
            a.write_text("{}", encoding="utf-8")
            b.write_text("{}", encoding="utf-8")
            paths = target_worker._parse_sing_box_config_args(["sing-box", "run", "-C", "conf"], root)
            self.assertEqual(paths, [a, b])


if __name__ == "__main__":
    unittest.main()
