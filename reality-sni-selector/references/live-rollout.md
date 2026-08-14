# Reversible Live Rollout

Use only when the user explicitly authorizes a production SNI/target change.

## Preflight

1. Read the current server target/SNI and client SNI.
2. Confirm the expected incumbent.
3. Confirm the chosen candidate is verified direct/non-CDN and passes the target probe and actual REALITY test.
4. Identify the persistent and runtime configs that must change.
5. Back up those configs and record the current service state.

## Apply

Update paired values together:

- server `target`/`dest`/`handshake.server`;
- server allowed/server name when applicable;
- client `serverName`/SNI.

Validate syntax with the installed core before reload/restart.

## Verify

Require:

- service/listener active;
- no new relevant REALITY/TLS errors;
- actual selected client path succeeds repeatedly;
- at least two independent external destinations work;
- persistent and runtime configs contain the same intended SNI.

## Roll back

If validation fails, restore every affected server/client copy, reload the smallest necessary service set, and confirm the incumbent works again.

Never leave server and client on different SNI values.

## Useful checks

Xray:

```bash
xray run -test -config /path/to/config.json
systemctl is-active xray
```

sing-box:

```bash
sing-box check -c /path/to/config.json
systemctl is-active sing-box
```

mihomo/ShellCrash:

```text
validate the staged YAML with the installed core
preserve current proxy-group selections
re-read both runtime and persistent node fields after reload
```
