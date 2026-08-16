# LOCAL_REALITY_INTEGRATION_TEST

This stage validates the local sing-box server/client fixture on the target VPS. It is not an end-to-end test from a real remote client.

## Binary selection

Prefer reviewed fixed ELF paths before PATH:

```text
/etc/sing-box/bin/sing-box
/usr/bin/sing-box
/usr/local/lib/sing-box/sing-box
/opt/sing-box/bin/sing-box
/opt/sing-box/sing-box
```

Accept a candidate only when it is a regular executable file with ELF magic. PATH is fallback only. Do not execute shell wrappers as the Reality test binary.

## Incumbent control

- Run one attempt first.
- If it succeeds, continue immediately.
- If it fails but cleanup is clean, run two additional diagnostic attempts.
- A retried control requires at least 2/3 total transport successes and 3/3 cleanups.
- A successful retried control emits `WARN:REALITY_CONTROL_TRANSIENT_FAILURE`.
- Cleanup failure immediately invalidates the batch.

## Candidate test

For each of at most five finalists:

- exactly 5 sequential attempts;
- fresh Reality keypair, UUID, and short ID per attempt;
- server and client listeners on `127.0.0.1` ephemeral/high ports;
- candidate hostname remains TLS/Reality `server_name`;
- selected candidate IPv4 is the Reality handshake server;
- validate both configs with `sing-box check`;
- perform one short HTTPS HEAD through loopback SOCKS;
- treat any HTTP status reached over successful transport separately from HTTP health;
- terminate process groups, verify ports closed, and remove 0700/0600 temporary artifacts.

Require 5/5 transport successes and 5/5 cleanups for Reality PASS.

## Sanitized failure evidence

Record stage-level evidence without raw secret-bearing stderr:

- `CONFIG_CHECK`
- `SERVER_START`
- `CLIENT_START`
- `PROXY_HEAD`
- `INPUT`
- `ENVIRONMENT`
- `INTERNAL`
- `CLEANUP`

Return failure counts, dominant failure stage, bounded HTTP status, elapsed time, and curl exit code. Never persist test credentials or complete temporary configs.
