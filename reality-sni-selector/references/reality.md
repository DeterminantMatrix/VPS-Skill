# LOCAL_REALITY_INTEGRATION_TEST

This stage validates the local sing-box server/client fixture on the target VPS. It is not an end-to-end test from a real remote client.

## Binary selection

Prefer reviewed fixed ELF paths before PATH. Require a regular executable ELF file; never execute a shell wrapper as the Reality test binary.

## Incumbent control

- Run one attempt first.
- If it succeeds, continue immediately.
- If it fails with clean cleanup, run two diagnostic retries.
- A retried control requires >=2/3 transport successes and 3/3 cleanups.
- Cleanup failure invalidates the batch.

## Candidate queue

QUICK evaluates ranked deep survivors until either five `SELECTABLE` candidates are obtained or eight candidates have been attempted. AUDIT may attempt up to nine non-incumbent deep survivors while targeting the same five selectable results.

For each candidate:

- success standard remains exactly 5/5 transport successes and 5/5 cleanups;
- use fresh Reality keypair, UUID, and short ID per attempt;
- use loopback-only listeners and one short HTTPS HEAD through loopback SOCKS;
- because one clean transport failure makes 5/5 impossible, immediately stop that candidate and continue to the next ranked candidate;
- cleanup failure is never fail-fast optimization: it remains run-level `TARGET_DIRTY_STATE`.

## Sanitized failure evidence

Record stage-level evidence without raw secret-bearing stderr: `CONFIG_CHECK`, `SERVER_START`, `CLIENT_START`, `PROXY_HEAD`, `INPUT`, `ENVIRONMENT`, `INTERNAL`, and `CLEANUP`. Return failure counts, dominant failure stage, bounded HTTP status/elapsed time/curl exit code, and whether the candidate was early-stopped.
