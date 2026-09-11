## Completion Brief

- **Subtask ID · Status:** T12 · complete

- **Files changed:**
  - `docker-compose.yml`
  - `tests/test_compose.py`
  - `CHANGELOG.MD`

- **Tests run + result:** `python -m pytest tests/test_compose.py -v` — **26 passed**. Mutation check on `test_image_tags_use_milestone_convention` (scraper `milestone_tags` reverted to `m2` while compose stayed `m8`) — **failed as expected**, then reverted.

- **Commit SHA:** `ba2ad79ca2390b010811563786be8485e86b0164`

- **Changelog entry location:** `CHANGELOG.MD` → section `## m8-hardening-scale — 2026-09-10` → T12 bullet (committed at HEAD)

- **Decision log path:** N/A (standard tier)

- **Kill-criterion evidence:**
  - **Compose + test pairing:** `git show ba2ad79` changes `bishop/scraper:m2→m8`, `bishop/ui:m7→m8`, and `milestone_tags["scraper"]`/`["ui"]` to `"m8"` in the same commit.
  - **No other services touched:** staged diff limited to those four tag lines; no other `milestone_tags` entries or compose `image:` lines changed.
  - **Backfill env keys preserved:** `docker-compose.yml` diff shows only the two `image:` hunks; scraper block still contains `BISHOP_BACKFILL_ENABLED`, `BISHOP_BACKFILL_CHUNK_DAYS`, `BISHOP_BACKFILL_INTER_CHUNK_DELAY_SEC` unchanged (confirmed in mutation failure output).
  - **Files-to-touch only:** commit stat — 3 files, all declared in packet.
  - **Naming contract:** `tests/test_compose.py::test_image_tags_use_milestone_convention` passes at HEAD (mutation-checked).

- **Summary:** T12 closes audit finding F4 by landing the deferred M8 compose image-tag bump together with the matching `tests/test_compose.py` fixture, as required by T8-bis’s named landing gate. Scraper and UI tags move from `m2`/`m7` to `m8`; all other compose content—including T8-bis’s three `BISHOP_BACKFILL_*` env keys on the scraper block—remains byte-for-byte unchanged. Adversarial coverage defers backfill-env preservation to procedural diff verification (no dedicated pytest falsifier).
