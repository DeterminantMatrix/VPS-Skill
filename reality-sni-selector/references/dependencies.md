# Dependencies

Normal runs never install packages automatically.

## Controller

Required:

- Python 3.10+
- OpenSSH client
- PyYAML for inventory parsing

## Target worker

Required:

- Python 3.10+
- system CA trust store
- `curl` for the loopback Reality HEAD integration test
- `sing-box` for final Reality integration

Optional but recommended:

- `dig` for CNAME evidence

If `dig` is absent, edge evidence may become `REVIEW:EDGE_UNKNOWN`; missing tooling is not proof of DIRECT and is not automatically proof of public CDN.

## Installation boundary

Installing or updating the target worker or dependencies is an explicit administrative task on an owned VPS. Do not combine it with a normal selection run.
