# Run r<NNN> — <UTC date>

**Trigger:** <which queued item (Q-xxx) or which decision is about to be made>
**Read at (UTC):** <from the query header>
**DBs:** <bishop_db path>, <ledger path>, `mode=ro`
**Uptime check:** <UTC days in the window with 0 rows or catch-up spikes, and what you did about them>

## Question

- population:
- window: <[start, end) on which clock>
- success:
- grain:

## Numbers (frozen)

<Paste tables. Do not re-probe to confirm; a new read is a new run.>

## Findings

| ID | Claim (with denominator) | Owner doc | Ask |
|----|--------------------------|-----------|-----|
| F-xxx | | | |

Each row is added to `../findings.yaml` as `routed`. If this run changed an older finding, update its `status_note` there.

## Noted (no owner, not in registry)

## Not run, and why
