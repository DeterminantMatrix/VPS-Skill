# Optional regional seed files

The v3 worker can discover institutional candidates from target-side regional metadata without a bundled seed file. If a stable region-specific seed list is maintained, store it here as `<region>.txt` (for example `us.txt` or `sg.txt`), one hostname per line.

Seed files are controller inputs only; candidate DNS and all network evaluation still occur on the target VPS.
