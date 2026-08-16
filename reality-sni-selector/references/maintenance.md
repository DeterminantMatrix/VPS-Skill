# Selection vs maintenance

## SELECTION MODE

Normal SNI selection may:

- read inventory;
- open one fixed SSH process;
- invoke `/usr/local/bin/reality-sni-target-worker run`;
- perform bounded target-side discovery/probes;
- write local run artifacts and reports.

It must not:

- upload or replace worker files;
- edit the Skill source;
- edit AGENTS/memory/project documentation;
- install packages;
- alter production sing-box, services, firewall, routing, SSH, or networking;
- create Git commits as a side effect of selection.

When a worker/environment defect blocks selection, stop and report `REPAIR_REQUIRED` with evidence.

## MAINTENANCE / REPAIR MODE

Enter only after explicit user authorization. Repair may:

- edit the reviewed Skill/worker source;
- run regression tests and validators;
- deploy the fixed worker to an owned VPS;
- verify the worker contract/manifest;
- update project documentation or Git history when requested.

After repair, start a new selection run with a new frozen job. Never resume the pre-repair frozen run because its code contract and evidence boundary changed.


## Read-only Skill validation

Do not run `py_compile` against an installed read-only Skill without relocating the bytecode cache. Validate from a writable checkout when possible. If syntax compilation is needed in place, use a temporary cache such as:

```text
PYTHONPYCACHEPREFIX=/tmp/reality-sni-pycache python3 -m py_compile <file.py>
```

An `EROFS` failure caused only by `__pycache__` creation is a validation-environment error, not evidence that the Skill source is invalid.

## Post-deployment contract check

After an authorized worker deployment, invoke the fixed wrapper **without** `run` in maintenance mode:

```text
ssh -T <declared-alias> /usr/local/bin/reality-sni-target-worker
```

Require the worker to return `FIXED_COMMAND_REQUIRED` and inspect its returned worker identity for protocol 4, implementation 4.1, and the expected six-file manifest. This performs no candidate discovery or SNI measurements. Then start a **new normal selection run**; the normal `run` job repeats the manifest check before target preflight/candidate traffic.
