# Reversible Live Rollout

Use only when the user explicitly authorizes a production SNI/target change.

## Preflight

1. Confirm the production REALITY listener is TCP/443.
2. Read the current server target/SNI and client SNI.
3. Confirm the expected incumbent.
4. Require an S or A candidate for normal production rollout.
5. Confirm the chosen candidate is verified direct/non-CDN and has real client-path evidence.
6. Identify persistent and runtime configs that must change.
7. Back up those configs and record the current service state.

## Apply

Update paired values together:

- server target/dest/handshake.server;
- server allowed/server name when applicable;
- client serverName/SNI.

Validate syntax with the installed core before reload/restart.

Do not weaken REALITY client-version constraints only to work around a client mismatch.

Where the installed Xray version supports fallback upload/download limiting or equivalent abuse controls, preserve or enable a conservative fallback limit appropriate for the deployment. Treat this as defense in depth, not a substitute for the strict no-CDN gate.

## Verify

Require:

- service/listener active on the intended port;
- no new relevant REALITY/TLS errors;
- actual production client path succeeds repeatedly;
- at least two independent external destinations work through the node;
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
