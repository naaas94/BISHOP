# T8 — §14.3 alert emission and log-level contract

**Plan:** m1-state-kernel · **Date:** 2026-06-11

## Chosen approach

- **Module:** `services/state-worker/app/alerts.py` owns `emit_alert()` and `ALERT_ERROR_CLASS = "ALERT"`.
- **Dual-write:** Each alert emits `logger.critical(message, extra={alert_type, source_id, ...})` and inserts an `error_log` row with `error_class = "ALERT"` in the same SQLite transaction as the `record_failure` state update (before `commit`).
- **M1 trigger taxonomy** (single alert per `record_failure`, assigned at branch time):
  - `PERMANENTLY_FAILED` → `permanent_failure` (fatal HTTP 400/410)
  - `ESCALATION_FLAGGED` from `not is_retriable` or escalation HTTP (401/403/404/422) → `escalation_flagged`
  - `ESCALATION_FLAGGED` from `retry_count + 1 >= RETRY_MAX_ATTEMPTS` → `retry_budget_exhausted`
- **Log levels:** `record_failure` logs `ERROR` (`transition failure`); manifest ingest skip and `mark_indexed` idempotent return log `WARNING`; successful transitions remain `INFO`.

## Alternatives rejected

- **Post-commit alert INSERT:** Rejected — risks escalated manifest row without matching ALERT row if the process dies between commits; same-transaction insert preferred per plan hidden coupling.
- **Single combined error_log row (mutate `error_class` to ALERT):** Rejected — spec §14.3 dual-write preserves the operational failure row (`TimeoutError`, etc.) alongside the human-facing ALERT row.
- **Defer all §14.3 to M2:** Rejected at plan amendment — audit F-004 major; M1 G2 binding.

## Assumptions made

- ALERT `error_log` rows use `is_retriable=False` and `http_status=None`; operational detail remains on the sibling failure row inserted by `record_failure`.
- `logger.critical` is not transactional; audit evidence relies on pytest `caplog` / log record `extra` fields, not on log persistence across crash.
- Sweeps and successful transition paths already log at `INFO`; no sweep changes required for F-005/F-006.

## Items deferred

- **`profile_hash_mismatch`** — enrichment-batcher / M3; not wired in `record_failure`.
- **`batch_timeout_48h`, `batch_abort`** — batch-poller / M5; not wired in state-worker M1.
- **Push/email/pager notification channels** — out of M1 scope per plan non-goals.
- **Alert row missing on partial transaction rollback:** Covered by same-transaction ordering; full crash mid-commit fault injection deferred to post-M1 hardening.
