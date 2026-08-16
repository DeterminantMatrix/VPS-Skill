# Incumbent baseline

## Default mode

The normal controller input is only the target inventory IPv4. The target worker resolves the incumbent before candidate evaluation by reading only fixed, local sing-box configuration locations:

```text
/etc/sing-box/config.json
/etc/sing-box/config.jsonc
/usr/local/etc/sing-box/config.json
/usr/local/etc/sing-box/config.jsonc
/opt/sing-box/config.json
/etc/sing-box/conf.d/*.json{,c}
/etc/sing-box/config.d/*.json{,c}
```

The worker extracts only Reality inbound handshake hostnames (or the sibling TLS `server_name` when the handshake address is an IP). It never emits UUIDs, private keys, short IDs, passwords, or full configuration.

If exactly one hostname is found, freeze it as the incumbent before discovery. If none are safely available, return `AUTO_INCUMBENT_UNAVAILABLE`/`AUTO_INCUMBENT_CONFIG_UNREADABLE`. If multiple distinct targets are found, return `AUTO_INCUMBENT_AMBIGUOUS`.

## Explicit override

Use `--incumbent <hostname>` when the production configuration is non-standard or intentionally has multiple Reality targets. The explicit hostname remains subject to measurement and appears as `BASELINE_ONLY` if it fails current candidate policy.
