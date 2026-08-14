# Reversible Live Rollout

Read this reference only when the user explicitly requests or authorizes a production SNI change.

## Map dependencies

Identify:

- server inbound config;
- client/router node config;
- runtime and persistent copies;
- subscriptions or generators that can overwrite the change;
- policy groups currently selecting the node;
- domain-based routing, firewall, direct/block lists;
- relays, tunnels, or chained nodes;
- service and control-plane reload methods.

Search exact old-domain occurrences without printing context around secret-bearing lines.

## Preflight

1. Read current paired values and require the expected incumbent.
2. Confirm target direct TLS/HTTPS from the VPS.
3. Validate an isolated REALITY path.
4. Stage server and client changes separately.
5. Run each stack's syntax check before touching production.
6. Record current service state, listener, policy selections, and recent error count.

Abort before mutation if any expected value or syntax check differs.

## Back up

Create timestamped backups on every affected host:

- exact original config files;
- service status and version;
- runtime and persistent router configs;
- current group selections;
- rollback commands or script.

Keep the existing SSH session available when practical. Use explicit validated paths.

## Apply as one coordinated change

1. Update server `dest`/`handshake.server` and server `serverName`.
2. Restart or reload only the affected server service.
3. Confirm active state and listener.
4. Update client/runtime/persistent `serverName`.
5. Hot-load the client config while preserving group selections.
6. Confirm every stored and active copy contains the new exact hostname.

Set rollback state immediately after the first production file is replaced, not only after service restart succeeds.

## Validate production

Require:

- staged and final syntax checks;
- active services and expected listeners;
- no new relevant error, panic, REALITY failure, or handshake failure lines;
- direct target health;
- actual selected policy path to two independent external endpoints;
- at least five consecutive successes per endpoint;
- unchanged policy selections unless the user requested a change;
- expected exit identity when it can be checked safely.

Classify as A only after all production gates pass.

## Roll back

If any hard gate fails:

1. restore every affected server and client file;
2. restart/reload the smallest service set;
3. restore policy selections;
4. confirm the incumbent path works again;
5. report the failure and backup paths.

Do not leave server and client on different SNI values.

## Stack checks

sing-box:

```bash
sing-box check -c /etc/sing-box/config.json -C /etc/sing-box/conf
systemctl is-active sing-box
ss -lntp
```

Xray:

```bash
xray run -test -config /path/to/config.json
systemctl is-active xray
```

Mihomo/ShellCrash:

```text
test the staged YAML with the installed core
back up runtime and persistent YAML
hot-load the staged path
re-read active and stored node fields
verify current proxy-group selections
```

## Report

Always report:

- old and new exact SNI;
- changed hosts and config roles;
- syntax/service/listener results;
- real-path endpoints and success counts;
- recent error count;
- backup paths;
- whether rollback was triggered;
- grade, evidence maturity, and convergence separately.
