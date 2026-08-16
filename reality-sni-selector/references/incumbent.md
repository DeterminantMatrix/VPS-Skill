# Incumbent baseline discovery

## Preferred live-process discovery

Before candidate evaluation, inspect local `/proc` read-only for running `sing-box` ELF processes. Parse only command-line configuration flags; do not invoke a shell.

Recognize sing-box global configuration arguments:

- `-c` / `--config`
- `-C` / `--config-directory`
- `-D` / `--directory` for resolving relative paths

When readable live-process configuration paths are available, treat them as authoritative and extract Reality targets only from those files.

## Fixed fallback

If no live-process configuration can be read, use the bounded fallback list:

```text
/etc/sing-box/config.json
/etc/sing-box/config.jsonc
/usr/local/etc/sing-box/config.json
/usr/local/etc/sing-box/config.jsonc
/opt/sing-box/config.json
/opt/sing-box/config.jsonc
/etc/sing-box/conf.d/*.json{,c}
/etc/sing-box/config.d/*.json{,c}
```

Never search the whole filesystem.

## Extraction

Extract only Reality inbound `handshake.server` hostnames, or the sibling TLS `server_name` when the handshake server is an IP. Do not emit UUIDs, private keys, short IDs, passwords, or full configs.

- exactly one distinct hostname -> freeze it as incumbent;
- zero -> `AUTO_INCUMBENT_UNAVAILABLE` or `AUTO_INCUMBENT_CONFIG_UNREADABLE`;
- more than one -> `AUTO_INCUMBENT_AMBIGUOUS`.

Use `--incumbent <hostname>` for an intentional explicit override.
