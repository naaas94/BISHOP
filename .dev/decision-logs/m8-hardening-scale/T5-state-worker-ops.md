# T5 — state-worker ops hub extension

**Plan:** m8-hardening-scale v1.2 · **Subtask:** T5 · **Tier:** architectural

## Chosen approach

Added two state-worker routes to the existing `entries` router (already mounted on `app.main`, so no `main.py` change was needed):

- `PATCH /entries/{source_id}/reading-status` — applies §0 flag 1's frozen resolution: writes `entries.reading_status` only, leaves `manifest`/`entries.processing_state` untouched. New transition helper `update_reading_status()` in `transitions.py`:
  - 404 (`NotFoundError`) when `source_id` is absent from `manifest` entirely.
  - 409 (new `EntryMissingError` → `{"error": "entry_missing", ...}`) when `source_id` exists in `manifest` but has no `entries` row yet (manifest-only — pipeline hasn't scraped content). This distinguishes "unknown id" (404) from "known id, nothing to mark read yet" (409), per the packet's error envelope row.
  - 422 on an invalid enum value is handled for free by Pydantic/FastAPI request validation against `ReadingStatusEnum` — no custom code needed.
- `POST /entries/permanent-fail` — applies §0 flag 2's frozen resolution: body `{"source_id": ...}`, only legal from `ESCALATION_FLAGGED` → `PERMANENTLY_FAILED`. New helper `mark_permanently_failed()`:
  - 404 (`NotFoundError`) if `source_id` unknown.
  - 409 (`InvalidTransitionError`, reusing the existing `invalid_transition` envelope already used by every other transition route) if `processing_state != ESCALATION_FLAGGED`.
  - Mirrors the existing `manual_retry()` pattern: updates `manifest.processing_state`, and if an `entries` row exists, syncs its `processing_state` and clears `flagged_for_review`.

New Pydantic wire models (`ReadingStatusPatchRequest/Response`, `PermanentFailPostRequest/Response`) added to `models/http.py`, matching the existing request/response pairing style (`RetryPostRequest/Response`).

## Alternatives rejected

- **Reuse `NotFoundError` for the manifest-only case instead of a new `EntryMissingError`.** Rejected: the packet's error envelope explicitly distinguishes 404 ("not in entries" / unknown id) from 409 ("no entries row, manifest-only"), and the router's existing dispatch (`_transition_error_response`) keys off exception type — collapsing both cases onto one exception type would make the 404-vs-409 split unrepresentable without ad hoc flags on `NotFoundError`.
- **A single `flagged_for_review` reset via `_sync_pipeline_state()` helper reuse for permanent-fail.** Rejected: `_sync_pipeline_state()` sets both rows unconditionally with no `expected=` guard, so it cannot enforce the "only from ESCALATION_FLAGGED" invariant on its own; the explicit check + `_set_manifest_state(..., expected=ESCALATION_FLAGGED)` pairing (matching `manual_retry`'s style) keeps the guard in one place and testable.

## Assumptions made

- **`entries.reading_status` is writable post-`INDEXED`.** The M1 migration (`alembic/versions/m1_001_initial_schema.py`) defines `entries.reading_status` as a plain `TEXT NOT NULL DEFAULT 'unread'` column with no CHECK constraint or trigger tying it to `processing_state`; the PATCH route issues a bare `UPDATE` with no state guard, so this holds for entries in any processing state, including terminal ones. If wrong, the load-bearing consequence is that reading-status updates on `INDEXED`/`PERMANENTLY_FAILED` entries would need a different guard — no test in this subtask exercises a terminal-state entry, since T6 (query-api/UI) drives the reachable states for a real user.
- **Manifest-only vs. entries-row distinction maps cleanly onto 404 vs. 409.** Confirmed against the actual schema and `_fetch_manifest`/`_fetch_entry` helpers already in `transitions.py` — no new assumption beyond what the packet's error-envelope row states.

## Items deferred

- None from this subtask's own scope. The escalation-panel UI wiring for these two actions (buttons, HTMX posts, query-api proxy routes) is explicitly T6's scope per §2 (`POST /entries/{source_id}/retry` (proxy), `POST /entries/{source_id}/permanent-fail` (proxy), `PATCH /entries/{source_id}/reading-status` (proxy) rows are all owned by T6) — not a gap opened here.
