## HALT Report — T9

**Subtask ID:** T9

**HALT reason:** Contract bindings contradict a pre-existing artifact outside **Files to touch** (equivalently: implementation needs a file outside **Files to touch** to avoid breaking an existing test).

**What I discovered:**

Contract row 18 (which T9 owns) requires raising the enrichment batch-size defaults:

> `BISHOP_ENRICHMENT_STAGE1_BATCH_SIZE` (10 → **50**) ... and the identical STAGE2 triad.

`services/enrichment-batcher/app/config.py` is in T9's **Files to touch**, so I can change `ENRICHMENT_STAGE1_BATCH_SIZE` / `ENRICHMENT_STAGE2_BATCH_SIZE` defaults there. But the repo already has `tests/test_enrichment_batcher_config.py` (pre-existing, **not** in T9's Files to touch) with:

```10:44:tests/test_enrichment_batcher_config.py
def test_enrichment_stage1_batch_size_default(monkeypatch: pytest.MonkeyPatch) -> None:
 monkeypatch.delenv("BISHOP_ENRICHMENT_STAGE1_BATCH_SIZE", raising=False)
 config = _load_config_module()
 assert config.ENRICHMENT_STAGE1_BATCH_SIZE == 10
...
def test_enrichment_stage2_batch_size_default(monkeypatch: pytest.MonkeyPatch) -> None:
 monkeypatch.delenv("BISHOP_ENRICHMENT_STAGE2_BATCH_SIZE", raising=False)
 config = _load_config_module()
 assert config.ENRICHMENT_STAGE2_BATCH_SIZE == 10
```

These two tests pin the **old** default (10). Raising the default to 50 per contract row 18 will make both fail. I cannot edit `tests/test_enrichment_batcher_config.py` to update the pinned assertions to 50, because that path is not in T9's declared **Files to touch** (`services/pre-filter-worker/app/config.py`, `services/pre-filter-worker/app/loop.py`, `services/enrichment-batcher/app/config.py`, `services/enrichment-batcher/app/stage1_loop.py`, `services/enrichment-batcher/app/stage2_loop.py`, `tests/test_prefilter_loop.py`, `tests/test_enrichment_batcher_stage1_loop.py`, `tests/test_enrichment_batcher_stage2_loop.py`, `CHANGELOG.MD`, `.dev/decision-logs/prompt-caching/T9-batch-amortization.md`).

Both hard rules apply simultaneously and cannot both be honored: "confine diffs to Files to touch" vs. "existing tests break → HALT, do not fix them to pass, and do not need files outside Files to touch." (The pre-filter side of row 18 has no such conflict — `PREFILTER_BATCH_SIZE` stays 50, unchanged — this is isolated to the two enrichment `BATCH_SIZE` defaults.)

**What the orchestrator needs to decide:**

- Add `tests/test_enrichment_batcher_config.py` to T9's **Files to touch** (so the two default-value assertions can be updated from 10 → 50 in this same subtask), or
- Issue a follow-on/amendment packet scoped to update that test file, or
- Clarify whether the stage1/2 default bump is intended to land via a different subtask that already owns that test file.

**Partial work:** None. No files were edited or staged; nothing was committed. I stopped design work at this contract/Files-to-touch conflict before making any diff (the rest of the amortization design — per-gate in-process hold accumulator seeded at first claim, hold-deadline clock that survives hash-abort retries per coupling C9, `now:` injection kwarg matching the existing `batch-poller` idiom — is fully scoped in my head but intentionally not written, since it depends on this default-value change landing cleanly first).
