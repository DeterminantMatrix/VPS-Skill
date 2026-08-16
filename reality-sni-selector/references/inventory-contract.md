# Local inventory contract

Use the local VPS workspace inventory as the source of truth.

## Default resolution

Prefer:

```text
inventory/hosts.yaml
```

Use `/opt/vps-control/inventory/hosts.yaml` only as a legacy fallback when the workspace-local file is absent. An explicit `--inventory` path overrides both.

## Required host shape

```yaml
hosts:
  best-vm-us:
    inventory_id: best-vm-us
    alias: best-vm-us
    region: US
    access:
      method: ssh
      hostname: 155.254.127.55
      address: 155.254.127.55
      port: 22
      user: root
      proxy_jump: null
      identity_ref: external:ssh-config
    capabilities:
      ssh: true
    state:
      retired: false
      forbidden: false
```

Rules:

- Match the requested target IPv4 only against `access.address` or `access.hostname` facts.
- Require exactly one match.
- Require `alias`, `region`, `access.method: ssh`, and `capabilities.ssh: true`.
- Reject `state.retired: true`, `state.forbidden: true`, or an explicitly inactive/disabled state.
- When `inventory_id` exists, require it to match the canonical `hosts.<canonical>` key.
- Preserve `inventory_id` and `alias` separately even when they currently have the same value.
- Treat `access.user`, `access.port`, `proxy_jump`, and `identity_ref` as descriptive facts only. Do not rebuild SSH arguments from them.
- Execute SSH using only the existing alias so the user's OpenSSH configuration remains authoritative.
