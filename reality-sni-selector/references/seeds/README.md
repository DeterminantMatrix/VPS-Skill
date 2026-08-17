# Optional regional seed files

The v4.4 worker performs multi-lane target-side discovery without requiring a bundled seed file. Institutional seeds remain an optional preference input, not a candidate-universe restriction. If a stable region-specific seed list is maintained, store it here as `<region>.txt` (for example `us.txt` or `sg.txt`), one hostname per line.

Seed files are controller inputs only; candidate DNS and all network evaluation still occur on the target VPS.
