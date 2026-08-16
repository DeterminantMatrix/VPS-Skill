# Architecture

## Control plane vs measurement plane

The controller may validate inventory, freeze parameters, open SSH, collect structured output, and render artifacts. It must not use its own network path as final evidence for candidate DNS, TLS, CDN classification, or latency.

The target VPS performs all candidate discovery and candidate-related measurements. This prevents controller geography, DNS, routing, or RTT from being mistaken for target behavior.

## Remote execution boundary

Normal run:

```text
controller
  -> resolve alias/region from inventory IPv4
  -> one OpenSSH process using existing alias
  -> fixed remote command: reality-sni-target-worker run
  -> frozen JSON job on stdin
  <- one structured JSON result on stdout
```

The controller never sends arbitrary shell, user-selected commands, arbitrary ports, or uploaded scripts during a run.

## Target worker deployment

`target_worker.py` is part of the Skill bundle so it can be reviewed and installed deliberately on owned VPSes. Installation is an out-of-band administrative action, not part of SNI selection. The normal workflow must fail closed when the fixed worker is unavailable.

## Stage ownership

| Stage | Controller | Target VPS |
|---|---:|---:|
| Inventory guard | yes | no |
| Freeze profile | yes | no |
| Egress observation | no | yes |
| Regional/source discovery | no | yes |
| Candidate DNS | no | yes |
| TLS/certificate | no | yes |
| HTTP-header/CDN evidence | no | yes |
| Fast benchmark | no | yes |
| Deep benchmark | no | yes |
| Local Reality integration | no | yes |
| Final artifact rendering | yes | no |
