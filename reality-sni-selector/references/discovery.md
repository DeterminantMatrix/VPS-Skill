# Candidate Discovery

Read this reference for serious selection, reselection, requests to find something better, or decisions about whether to keep searching.

## Coverage

Complete these sources when the region provides enough candidates:

- authorized VPS `/24` and same-ASN/provider evidence;
- at least 10 same-region ordinary organizations;
- at least 10 small universities, research groups, departments, libraries, or colleges;
- at least 10 regional B2B/service-provider candidates;
- at least 10 social-service, health, community, charity, professional, chamber, media, or local institutional candidates.

After the first potential A candidate appears, complete two independent expansion rounds. Use at least 10 new unique domains per round and change the source or organization category.

## Layered discovery

1. Identify the VPS ASN, provider, region, routed prefix, and nearby exchange or metro.
2. Scan only the authorized `/24` when appropriate.
3. Search passive public sources for same-provider or same-metro customer sites.
4. Add ordinary regional organizations with established public websites.
5. Add small universities/research institutions.
6. Add local B2B, IT, SaaS, hosting, logistics, chambers, and media.
7. Add community, health, charity, cultural, and professional institutions.
8. Use famous global brands only as compatibility fallbacks.

Useful queries:

```text
"<ASN_OR_PROVIDER>" "https"
"<REGION>" "university" "https"
"<REGION>" "managed service provider"
"<REGION>" "museum" "organization"
"<REGION>" "community services"
```

## RealiTLScanner

Derive the `/24` from the VPS IP and run only that range:

```powershell
cd C:\RealityScan
.\RealiTLScanner.exe -addr <CIDR_24> -port 443 -thread 20 -timeout 5 -out "<OUTPUT.csv>"
```

Clean output:

```powershell
python "<SKILL_DIR>\scripts\clean_reality_candidates.py" "<OUTPUT.csv>" --out "<CANDIDATES.txt>" --strict --show-rejects
```

Reject malformed names, IPs, wildcard entries, origin certificates, panels, monitoring/admin names, obvious proxy infrastructure, random numeric domains, suspicious TLDs, and famous unrelated front doors.

## RealityChecker

Use RealityChecker from the VPS as a compatibility filter:

```bash
mapfile -t domains < candidates.txt
./reality-checker batch "${domains[@]}"
```

Preserve these as separate values:

- submitted hostname;
- certificate hostname/SAN;
- redirect destination;
- RealityChecker final domain.

Reject silent substitutions such as a parked-domain redirect to an unrelated registrar. Do not trust stars, CDN labels, popularity labels, or redirect handling without manual verification.

## Candidate record

Record:

```text
domain:
category:
discovery source:
regional reason:
scanner result:
manual gate status:
rejection reason:
```

Do not claim same-ASN or same-region superiority until the natural-identity categories have also been checked.
