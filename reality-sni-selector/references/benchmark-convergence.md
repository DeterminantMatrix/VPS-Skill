# Fair Benchmark, Scoring, and Convergence

Read this reference before naming a serious primary, grading production readiness, or claiming that searching can stop.

## Predeclare the tournament

Apply the cheap protocol/front-door/site gate before the tournament. Include the incumbent and two to three challengers that survived it. Fix before testing:

- exact hostnames;
- IPv4/IPv6 policy;
- redirect policy;
- 20 fresh connections per candidate per timing window;
- pacing and timeout;
- two independent REALITY endpoints;
- metrics and rejection thresholds.

Do not spend a 20-round budget on a candidate missing exact SAN, TLS 1.3, ALPN `h2`, stable DNS/IP evidence, acceptable redirect behavior, or the requested front-door policy. Keep institutional and same-ASN preference as a tie-breaker after these hard gates.

Do not add a preference after seeing results. If the finalist pool changes materially, rerun the complete pool.

## Run fairly

Use rotating order. Never finish all samples for one candidate before starting the next.

Run the bundled script on the VPS:

```bash
python3 benchmark_https.py --rounds 20 --pace 0.5 <INCUMBENT> <CHALLENGER...>
```

The script:

- performs document-only IPv4 GETs;
- follows redirects;
- rotates candidate order;
- sleeps between candidates;
- records status, TCP, TLS, total time, and remote IP;
- aborts a candidate on `429` or repeated distress statuses;
- emits JSON.

Use at most 20 direct HTTP requests per candidate per window and two pre-production windows unless investigating a documented anomaly.

Record:

- successes and statuses;
- TLS p50, p95, maximum, and samples above 200 ms;
- total-time p50, p95, and maximum;
- IP/ASN/certificate changes;
- REALITY successes and service errors.

## Fixed 100-point evidence model

Apply hard gates before score:

- certificate identity: 20;
- region/network/organization fit: 20;
- website legitimacy and traffic plausibility: 20;
- repeated HTTPS stability: 20;
- actual REALITY path: 15;
- operational durability: 5.

Create an evidence JSON object and run:

```bash
python "<SKILL_DIR>/scripts/score_candidate.py" --example
python "<SKILL_DIR>/scripts/score_candidate.py" evidence.json
```

The script accepts controlled enums and measured values, applies fixed mappings, and returns component scores, hard-gate failures, grade ceiling, and total. Do not change weights during a candidate search.

Evidence values must have recorded reasons. The script makes scoring repeatable; it does not manufacture missing evidence.

## Grade gates

A requires:

1. durable regional organization/business identity;
2. `substantial` or defensibly `small-active` website;
3. traffic plausibility `fit`;
4. exact explicit SAN and at least 30 days remaining;
5. five of five direct HTTPS successes and acceptable status;
6. inspected DNS/ASN/region/CDN;
7. real production path to at least two external endpoints;
8. at least five consecutive real-path successes;
9. synchronized dependencies, active services, clean recent logs, and rollback.

B passes manual gates but lacks synchronized production or actual user-path evidence.

C connects but retains a documented compromise. D fails certificate, reachability, HTTP, or real path.

## Material improvement

A challenger is materially better only with no hard-gate regression and one of:

- total score improves by at least 5;
- it removes a wildcard/shared identity, placeholder, traffic mismatch, region mismatch, abnormal status, or repeated timeout;
- TLS p95 or maximum improves by at least 20% in both timing windows without worsening certificate, website, network, or real-path behavior.

A 2–10 ms median difference alone is normally noise.

## Timing and convergence

- Use two comparable windows separated by at least 30 minutes for convergence.
- The first window may cover the incumbent and the full fixed finalist pool; the second window may be limited to the incumbent, winner, and runner-up if the pool and protocol remain unchanged.
- A later production check may count as the second window if protocol and metrics remain comparable.
- Require another successful window at least six hours later before saying `durable` or `long-term stable`.

Mark `converged` only when:

1. at least one A exists;
2. discovery coverage is complete;
3. incumbent and finalists used identical tests;
4. two timing windows agree or show no material difference;
5. two consecutive expansion rounds find no materially better challenger;
6. the winner passes website and traffic plausibility.

Otherwise report `not assessed` or `provisional`. Prefer the incumbent when candidates are operationally tied.
