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
