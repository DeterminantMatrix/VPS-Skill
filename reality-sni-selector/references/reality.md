# Local sing-box Reality integration test

## Purpose

Prove that the candidate works through the actual sing-box Reality implementation on the target VPS. OpenSSL/Python TLS alone is not sufficient.

This is a **local integration test**, not a test of a real remote client path to the VPS.

## Isolation

- Use the real sing-box ELF binary on the target.
- Never edit or restart production sing-box.
- Bind server and SOCKS listeners to `127.0.0.1` only.
- Use ephemeral/high ports.
- Use a unique 0700 temporary directory per attempt.
- Store temporary JSON as 0600.
- Generate fresh test-only Reality keys, UUID, and short ID.
- Start temporary processes in their own process groups.
- Remove all processes and files after every attempt, including failures.

## Candidate binding

Keep the candidate hostname as the Reality client `server_name` and temporary inbound TLS `server_name`.

Resolve the candidate to a validated public IPv4 before the fixture and use that IPv4 as the temporary Reality handshake address. This avoids legacy `domain_strategy` and preserves the hostname SNI separately.

## Fixed sequence

For each attempt:

1. resolve/select one validated public IPv4;
2. generate fresh Reality keypair, UUID, and short ID;
3. create temporary VLESS Reality server/client configs;
4. run `sing-box check` on both configs;
5. launch loopback server and client;
6. make one short HTTPS HEAD through the loopback SOCKS listener, keeping the URL/SNI hostname and pinning destination IPv4;
7. record transport success, HTTP status, elapsed time, and bounded diagnostic category;
8. terminate process groups and prove listener/process cleanup;
9. delete the temporary directory.

## Control

Run the incumbent control once before candidate Reality tests. If it fails, emit `INVALID:REALITY_CONTROL_FAILED` and do not reinterpret all candidates as failures.

## Candidate requirement

Run exactly five sequential attempts per finalist. Final Reality eligibility requires 5/5 transport success.

A non-000 HTTP status indicates a response was reached; it does not establish website health. Keep `transport_success` and `http_health` separate.

Cleanup failure is run-level `TARGET_DIRTY_STATE` and stops the remaining Reality batch.
