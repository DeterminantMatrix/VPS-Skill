# Current incumbent SNI assessment

Evaluate the configured incumbent from the same target-side run. Do not infer health from production popularity or historical success alone.

## Evidence precedence

Use, in order:

1. REALITY protocol-minimum evidence (TLS1.3, h2, certificate/identity, redirect policy);
2. policy/safety evidence;
3. deep reliability evidence;
4. local Reality incumbent control;
5. performance against fully `SELECTABLE` alternatives.

A lower-priority performance advantage never overrides a higher-priority safety/reliability failure.

## Verdicts

| Code | Chinese verdict | Rule |
|---|---|---|
| `REPLACE_REQUIRED` | `需要更换` | REALITY protocol hard failure; confirmed policy hard rejection; deep overall TLS success <95%; sufficiently sampled IP <90%; or clean Reality control failure |
| `REPLACE_RECOMMENDED` | `建议更换` | incumbent otherwise passes, but a fully selectable alternative improves P50 by >=30% and P95 by >=15% when P95 is measurable; also use when incumbent P50 is above the 60 ms target and a selectable alternative improves P50 by >=20% |
| `KEEP_WITH_REVIEW` | `暂可继续使用，建议复核` | no hard failure, but current SNI has review signals or the Reality control needed retries |
| `KEEP_OPTIMIZABLE` | `可继续使用，但有优化空间` | incumbent passes policy/reliability/Reality but best selectable alternative improves P50 by >=15%, or incumbent P50 remains above the advisory target without a decisive replacement case |
| `KEEP` | `继续使用` | incumbent passes policy/reliability/Reality and no material replacement advantage is demonstrated |
| `UNABLE_TO_ASSESS` | `暂无法评估` | incumbent deep evidence or Reality control is unavailable, or cleanup uncertainty prevents attribution |

## Confidence

- `HIGH`: decisive safety/reliability result, or GOOD coverage with clean evidence.
- `MEDIUM`: performance/review decision with limited coverage or a retried control.
- `LOW`: missing evidence / unable to assess.

Always include machine-readable reasons and the best fully selectable alternative when one exists.

## v4.5 performance tradeoff explanation

Always emit `tradeoff_code` and `tradeoff_text` when a recommended selectable alternative exists. The text must explicitly state whether the current SNI is faster, slower, or near-tied with the recommendation.

When the incumbent has a hard policy rejection but is faster than the recommended candidate, use `CURRENT_FASTER_BUT_POLICY_REJECTED` and say both facts: the incumbent wins on latency, but the higher-priority policy failure still requires replacement. Do not hide a performance regression behind the safety verdict.
