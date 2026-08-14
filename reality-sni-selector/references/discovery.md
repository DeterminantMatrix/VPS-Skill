# Candidate Discovery

Use this file only when the user does not already have enough candidates.

## Safety rule

Never run broad discovery scans from the production REALITY VPS. Broad scans can create an avoidable scanning footprint on the production IP.

Run RealiTLScanner or comparable range discovery from:

1. the user's local machine; or
2. a separate non-production host.

The production VPS should receive only the final 5-12 domain shortlist for low-rate exact-host probes.

## Keep discovery bounded

Start with the working incumbent, then collect candidates from:

1. existing RealiTLScanner/RealityChecker output;
2. nearby/regional ordinary HTTPS sites;
3. direct-hosted candidates found through focused discovery.

Stop once 5-12 plausible candidates exist. Apply the target gate, then keep only 2-3 verified-direct finalists.

Do not require quotas by organization type, ASN, institution type, or TLD.

## Preference-oriented discovery

After basic hygiene, prefer adding candidates that may score well on the post-gate Preference fit:

- sites whose resolved target ASN matches the VPS ASN;
- verified universities, research institutes, libraries, museums, nonprofits, NGOs, public research bodies, and public cultural institutions.

Do not scan an entire ASN from the production VPS. Find same-ASN candidates through passive/focused research, existing scanner datasets, or non-production discovery, then send only exact hostnames to the production target gate.

Preference candidates still have to pass every normal hard gate. Same ASN or institution type never overrides CDN/shared-front-door rejection.

## RealiTLScanner

Use only authorized ranges and run it away from the production VPS. Example:

```bash
./RealiTLScanner -addr <AUTHORIZED_CIDR> -port 443 -thread 20 -timeout 5 -out candidates.csv
```

Treat scanner output as discovery evidence, not a final ranking.

## Candidate hygiene

Reject before probing:

- malformed hostnames;
- IP literals when a hostname/SNI is required;
- wildcard strings such as `*.example.com` as the configured SNI;
- localhost/private control-plane names;
- duplicates;
- `.cn`, `.ru`, `.ir` targets in strict GFW-risk mode;
- hostnames containing `apple`, `icloud`, or `microsoft` in strict GFW-risk mode.

Do not reject an ordinary candidate only because its name contains generic strings such as `api`, `status`, or `test`.

## Strict no-CDN gate

Reject confirmed shared CDN or platform front doors before REALITY testing or benchmarking.

Use evidence in this order:

1. CNAME chain to a known CDN/shared-edge domain;
2. resolved IP ASN/provider clearly belonging to a CDN edge network;
3. scanner or trusted network evidence identifying a shared front door.

Cloudflare, CloudFront, Akamai, Fastly, Azure Front Door/CDN, and comparable shared edge services are hard rejects.

An AWS/Azure/Google cloud ASN without clear origin-vs-edge evidence is `unknown`, not `direct`, in strict mode. It cannot receive S/A until manually verified as a non-shared origin.
