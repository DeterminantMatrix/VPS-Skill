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

- Prefer exact public-IPv4 matching against `access.address` or `access.hostname`. Also accept exact `hosts.<canonical>`, `inventory_id`, `alias`, `name`, `display_name`, or `label`.
- For a non-exact name, compare only those inventory identifiers and their safe alphanumeric tokens. Accept fuzzy resolution only when one candidate scores at least 0.84 and leads the runner-up by at least 0.08. Record `TARGET_SELECTOR_FUZZY_MATCH`, the matched identifier, and score.
- Fail closed when the fuzzy match is weak or ambiguous. For example, `hostzdire` may resolve to `lax-hostdzire` only when no similarly named HostDZire target competes.
- After name resolution, derive exactly one public IPv4 from `access.address`/`access.hostname`; do not infer an address from monitoring data.
- Require `alias`, `region`, `access.method: ssh`, and `capabilities.ssh: true`.
- Reject `state.retired: true`, `state.forbidden: true`, or an explicitly inactive/disabled state.
- When `inventory_id` exists, require it to match the canonical `hosts.<canonical>` key.
- Preserve `inventory_id` and `alias` separately even when they currently have the same value.
- Treat `access.user`, `access.port`, `proxy_jump`, and `identity_ref` as descriptive facts only. Do not rebuild SSH arguments from them.
- Execute SSH using only the existing alias so the user's OpenSSH configuration remains authoritative.
