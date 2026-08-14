# Candidate Discovery

Use this file only when the user does not already have enough candidates.

## Keep discovery bounded

Start with the working incumbent, then collect a small mixed pool from:

1. RealiTLScanner or RealityChecker results from an authorized range;
2. nearby/regional ordinary HTTPS sites;
3. direct-hosted candidates when obvious;
4. a few known compatible targets only as controls or fallbacks.

Stop broad discovery once 5-12 plausible candidates exist. Apply the strict no-CDN gate before expensive tests, then keep only 2-4 verified-direct finalists.

Do not require quotas by organization type, ASN, university/nonprofit status, or TLD.

## RealiTLScanner

Use only authorized addresses. Example:

```bash
./RealiTLScanner -addr <AUTHORIZED_CIDR> -port 443 -thread 20 -timeout 5 -out candidates.csv
```

Treat scanner output as discovery evidence, not a final ranking.

## Candidate hygiene

Reject only obvious unusable input before probing:

- malformed hostnames;
- IP literals when a hostname/SNI is required;
- wildcard strings such as `*.example.com` as the configured SNI;
- localhost/private control-plane names;
- duplicates.

Do not delete candidates merely because their name contains `api`, `status`, `cdn`, `apple`, `google`, `microsoft`, or a particular TLD. Convert real evidence about CDN, popularity, or policy sensitivity into risk flags later.

## Strict no-CDN gate

Reject confirmed shared CDN or platform front doors before REALITY testing or benchmarking. Examples include Cloudflare, Amazon CloudFront and shared AWS front doors, Akamai, Fastly, Azure Front Door/CDN, and comparable services.

Use evidence in this order:

1. CNAME chain to a known CDN/shared-edge domain;
2. resolved IP ASN/provider that is clearly a CDN edge network;
3. scanner or trusted network evidence identifying a shared front door.

Do not use domain substrings alone. An ordinary site hosted on a cloud VPS is not automatically a CDN. If evidence remains `unknown`, keep the candidate out of the Primary/finalist set until directness is verified.
