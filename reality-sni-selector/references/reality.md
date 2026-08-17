# LOCAL_REALITY_INTEGRATION_TEST v4.3.5

This stage validates the local sing-box server/client fixture on the target VPS. It is not an end-to-end test from a real remote client.

## Binary selection

Prefer reviewed fixed ELF paths before PATH. Require a regular executable ELF file; never execute a shell wrapper as the Reality test binary.

## Incumbent control

- Run one attempt first.
- If it succeeds, continue immediately.
- If it fails with clean cleanup, run two diagnostic retries.
- A retried control requires >=2/3 transport successes and 3/3 cleanups.
- Cleanup failure invalidates the batch.

## Adaptive candidate queue

- Only `ELIGIBLE` Deep survivors can enter candidate Reality testing. `REVIEW_REQUIRED` rows cannot become `SELECTABLE` and do not consume candidate Reality budget.
- Start with the initial Deep survivors in recommendation order.
- Stop immediately after five `SELECTABLE` candidates are obtained.
- If fewer than five are obtained and eligible Fast survivors remain, Deep-refill the next deterministic batch of four, then continue Reality testing.
- QUICK stops when five are found, Fast survivors/Deep cap are exhausted, a dirty state occurs, or 16 candidate Reality tests have been attempted.
- AUDIT uses the same rule with a 20-row Deep cap and 18 candidate Reality-test cap.

For each candidate:

- require exactly 5/5 transport successes and 5/5 cleanups;
- use fresh Reality keypair, UUID, and short ID per attempt;
- use loopback-only listeners and one short HTTPS HEAD through loopback SOCKS;
- after the first clean transport failure, stop that candidate because 5/5 is no longer possible;
- cleanup failure remains run-level `TARGET_DIRTY_STATE`.

Record `adaptive_refill.stop_reason`, refill rounds/counts, total Deep rows, Reality tested/passed, and final selectable count.

## Sanitized failure evidence

Record stage-level evidence without raw secret-bearing stderr: `CONFIG_CHECK`, `SERVER_START`, `CLIENT_START`, `PROXY_HEAD`, `INPUT`, `ENVIRONMENT`, `INTERNAL`, and `CLEANUP`.
