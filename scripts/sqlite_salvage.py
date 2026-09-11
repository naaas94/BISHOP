"""Rebuild a clean bishop.db from a corrupt one plus its ``sqlite3 .recover`` dump.

Two independent salvage sources are merged into a freshly migrated database:

1. The ``.recover`` dump, which reconstructs whole tables from intact btree
   pages and dumps unattributable rows into ``lost_and_found``. Batch rows land
   there because the ``batches`` root page is torn, so they are re-attributed by
   column arity and shape.
2. A rowid walk of the corrupt file itself, which reaches rows that ``.recover``
   missed. Pages that raise are skipped one rowid at a time.

Neither source is trusted alone. Rows are inserted with ``INSERT OR IGNORE`` so
the first writer of a primary key wins, and every rejected row is reported.

Usage:
  python scripts/sqlite_salvage.py \
      --corrupt  C:/Users/Ale/bishop_data/_salvage_2026-09-11/forensics.db \
      --recovered-sql C:/Users/Ale/bishop_data/_salvage_2026-09-11/recovered.utf8.sql \
      --out      C:/Users/Ale/bishop_data/_salvage_2026-09-11/bishop.salvaged.db \
      --report   C:/Users/Ale/bishop_data/_salvage_2026-09-11/salvage-report.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logger = logging.getLogger("sqlite_salvage")


def _load_enums() -> Any:
    """Load state-worker enums by path; `services/*/app` packages collide on sys.path."""
    import importlib.util

    path = ROOT / "services" / "state-worker" / "app" / "enums.py"
    spec = importlib.util.spec_from_file_location("bishop_state_worker_enums", path)
    if spec is None or spec.loader is None:
        msg = f"cannot load enums from {path}"
        raise SystemExit(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Tables the .recover dump reconstructs in place, in foreign-key-safe order.
# alembic_version is deliberately excluded: the fresh database is stamped by
# Alembic itself, and a salvaged stamp could disagree with the real head.
RECOVERED_TABLES = ("manifest", "entries", "scraper_state", "error_log", "oov_tags_log")

# Physical column order of `batches` at head: m1_001 created it through
# external_batch_id, m3_001 appended source_ids. lost_and_found rows carry the
# values positionally in c0..c14, so this order is the mapping key.
BATCHES_COLUMNS = (
    "batch_id",
    "batch_type",
    "domain",
    "profile_version",
    "profile_render_hash",
    "status",
    "created_at",
    "submitted_at",
    "completed_at",
    "entry_count",
    "passed_count",
    "failed_count",
    "top_entries",
    "external_batch_id",
    "source_ids",
)
BATCH_TYPES = {"pre_filter", "enrichment_stage1", "enrichment_stage2"}


def _connect_rw(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _connect_ro(path: Path) -> sqlite3.Connection:
    """Open read-only and immutable so a torn file is never written or WAL-recovered."""
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def build_fresh_db(out: Path) -> None:
    """Create `out` at Alembic head. Refuses to clobber an existing file."""
    if out.exists():
        msg = f"refusing to overwrite existing {out}"
        raise SystemExit(msg)
    out.parent.mkdir(parents=True, exist_ok=True)

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{out.as_posix()}")
    command.upgrade(cfg, "head")

    with _connect_rw(out) as conn:
        head = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    logger.info("fresh db at alembic head %s: %s", head, out)


def load_recover_dump(sql_path: Path, staging: Path) -> None:
    """Execute a .recover dump into a throwaway database."""
    if staging.exists():
        staging.unlink()
    text = sql_path.read_text(encoding="utf-8", errors="replace")
    # A UTF-16 redirect (PowerShell `>`) leaves a BOM that sqlite cannot parse.
    text = text.lstrip("\ufeff")
    conn = _connect_rw(staging)
    try:
        conn.executescript(text)
        conn.commit()
    finally:
        conn.close()
    logger.info("loaded recover dump into staging db: %s", staging)


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]


def copy_recovered_tables(staging: Path, out: Path, report: dict[str, Any]) -> None:
    """Copy reconstructed tables from the staging db into the fresh db."""
    src = _connect_ro(staging)
    dst = _connect_rw(out)
    try:
        for table in RECOVERED_TABLES:
            target_cols = _columns(dst, table)
            src_cols = _columns(src, table)
            shared = [c for c in target_cols if c in src_cols]
            missing = [c for c in target_cols if c not in src_cols]
            placeholders = ", ".join("?" * len(shared))
            collist = ", ".join(f'"{c}"' for c in shared)
            inserted = rejected = 0
            reject_reasons: Counter[str] = Counter()

            for row in src.execute(f"SELECT {collist} FROM {table}"):  # noqa: S608
                try:
                    cur = dst.execute(
                        f"INSERT OR IGNORE INTO {table} ({collist}) VALUES ({placeholders})",  # noqa: S608
                        tuple(row),
                    )
                    inserted += cur.rowcount
                except sqlite3.DatabaseError as exc:
                    rejected += 1
                    reject_reasons[str(exc)[:120]] += 1
            dst.commit()
            report["recover"][table] = {
                "inserted": inserted,
                "rejected": rejected,
                "missing_columns": missing,
                "reject_reasons": dict(reject_reasons),
            }
            logger.info(
                "recover %-14s inserted=%-6d rejected=%-4d missing_cols=%s",
                table,
                inserted,
                rejected,
                missing or "-",
            )
    finally:
        src.close()
        dst.close()


def _looks_like_batch(row: sqlite3.Row) -> bool:
    """A lost_and_found row is a batches row if arity and discriminators match."""
    if row["nfield"] != len(BATCHES_COLUMNS):
        return False
    if row["c1"] not in BATCH_TYPES:
        return False
    batch_id = row["c0"]
    return isinstance(batch_id, str) and len(batch_id) == 36 and batch_id.count("-") == 4


def rebuild_batches(staging: Path, out: Path, report: dict[str, Any]) -> None:
    """Re-attribute lost_and_found rows to `batches` by arity and shape."""
    src = _connect_ro(staging)
    dst = _connect_rw(out)
    try:
        try:
            rows = list(src.execute("SELECT * FROM lost_and_found"))
        except sqlite3.DatabaseError:
            logger.warning("recover dump has no lost_and_found table")
            report["batches"] = {"inserted": 0, "candidates": 0, "skipped": 0}
            return

        collist = ", ".join(f'"{c}"' for c in BATCHES_COLUMNS)
        placeholders = ", ".join("?" * len(BATCHES_COLUMNS))
        inserted = candidates = skipped = 0
        reject_reasons: Counter[str] = Counter()
        by_type: Counter[str] = Counter()
        by_status: Counter[str] = Counter()

        for row in rows:
            if not _looks_like_batch(row):
                skipped += 1
                continue
            candidates += 1
            values = tuple(row[f"c{i}"] for i in range(len(BATCHES_COLUMNS)))
            # source_ids / top_entries must be JSON text for the Pydantic boundary.
            for idx in (12, 14):
                raw = values[idx]
                if raw is None:
                    continue
                try:
                    json.loads(raw)
                except (TypeError, ValueError):
                    reject_reasons[f"{BATCHES_COLUMNS[idx]} is not JSON"] += 1
                    break
            else:
                try:
                    cur = dst.execute(
                        f"INSERT OR IGNORE INTO batches ({collist}) VALUES ({placeholders})",  # noqa: S608
                        values,
                    )
                    inserted += cur.rowcount
                    if cur.rowcount:
                        by_type[str(values[1])] += 1
                        by_status[str(values[5])] += 1
                except sqlite3.DatabaseError as exc:
                    reject_reasons[str(exc)[:120]] += 1
        dst.commit()
        report["batches"] = {
            "lost_and_found_rows": len(rows),
            "candidates": candidates,
            "inserted": inserted,
            "skipped_not_batch": skipped,
            "reject_reasons": dict(reject_reasons),
            "by_type": dict(by_type),
            "by_status": dict(by_status),
        }
        logger.info(
            "batches rebuilt from lost_and_found: inserted=%d of %d candidates (%d non-batch rows)",
            inserted,
            candidates,
            skipped,
        )
    finally:
        src.close()
        dst.close()


def walk_table(
    corrupt: Path,
    out: Path,
    table: str,
    report: dict[str, Any],
    *,
    chunk: int = 50,
    max_skips: int = 20000,
) -> None:
    """Rowid-walk a torn table, stepping over pages that raise."""
    src = _connect_ro(corrupt)
    dst = _connect_rw(out)
    try:
        target_cols = _columns(dst, table)
        src_cols = _columns(src, table)
        shared = [c for c in target_cols if c in src_cols]
        collist = ", ".join(f'"{c}"' for c in shared)
        placeholders = ", ".join("?" * len(shared))

        cursor_rowid = 0
        inserted = read = skips = rejected = 0
        max_seen = 0
        while skips < max_skips:
            try:
                rows = list(
                    src.execute(
                        f"SELECT rowid, {collist} FROM {table} "  # noqa: S608
                        "WHERE rowid > ? ORDER BY rowid LIMIT ?",
                        (cursor_rowid, chunk),
                    ),
                )
            except sqlite3.DatabaseError:
                # Torn page under this rowid range; step past it one row at a time.
                cursor_rowid += 1
                skips += 1
                continue
            if not rows:
                break
            for row in rows:
                read += 1
                cursor_rowid = max(cursor_rowid, row["rowid"])
                max_seen = max(max_seen, row["rowid"])
                try:
                    cur = dst.execute(
                        f"INSERT OR IGNORE INTO {table} ({collist}) VALUES ({placeholders})",  # noqa: S608
                        tuple(row[c] for c in shared),
                    )
                    inserted += cur.rowcount
                except sqlite3.DatabaseError as exc:
                    rejected += 1
                    logger.debug("walk %s reject: %s", table, exc)
        dst.commit()
        report["walk"][table] = {
            "rows_read": read,
            "newly_inserted": inserted,
            "rejected": rejected,
            "page_skips": skips,
            "max_rowid_seen": max_seen,
            "hit_skip_cap": skips >= max_skips,
        }
        logger.info(
            "walk %-14s read=%-6d new=%-5d rejected=%-4d skips=%d",
            table,
            read,
            inserted,
            rejected,
            skips,
        )
    finally:
        src.close()
        dst.close()


def _row_violations(row: sqlite3.Row, table: str, enums: Any) -> list[str]:
    """Enum/shape violations that prove a row was reassembled from torn pages."""
    states = {s.value for s in enums.ProcessingState}
    sources = {s.value for s in enums.SourceEnum}
    domains = {d.value for d in enums.DomainEnum}
    reading = {r.value for r in enums.ReadingStatusEnum}

    bad: list[str] = []
    if row["processing_state"] not in states:
        bad.append(f"processing_state={row['processing_state']!r}")
    if row["source"] not in sources:
        bad.append(f"source={row['source']!r}")
    if row["domain"] not in domains:
        bad.append(f"domain={row['domain']!r}")
    source_id = row["source_id"]
    if not isinstance(source_id, str) or ":" not in source_id:
        bad.append(f"source_id={source_id!r}")
    elif source_id.split(":", 1)[0] not in sources:
        bad.append(f"source_id prefix={source_id!r}")
    if table == "entries":
        if row["reading_status"] not in reading:
            bad.append(f"reading_status={row['reading_status']!r}")
        if not row["content_raw"]:
            bad.append("content_raw empty")
    if table == "manifest" and row["relevance_decision"] not in (0, 1, None):
        bad.append(f"relevance_decision={row['relevance_decision']!r}")
    return bad


def quarantine_torn_rows(out: Path, report: dict[str, Any], quarantine_path: Path) -> None:
    """Delete rows that cannot satisfy the domain model, and requeue their re-fetch.

    `.recover` reassembles some rows from partial pages, leaving content text in
    enum columns or empty strings where a value is required. Such a row would
    fail Pydantic validation at the first read and 500 the route, so it is
    removed rather than served. Its `manifest` row is reset to RELEVANCE_PASSED
    so content-scraper re-fetches the body over plain HTTP, which costs nothing;
    only the enrichment calls for these few rows are re-paid.
    """
    enums = _load_enums()
    conn = _connect_rw(out)
    quarantined: dict[str, list[dict[str, Any]]] = {"manifest": [], "entries": []}
    try:
        for table in ("entries", "manifest"):
            rows = list(conn.execute(f"SELECT * FROM {table}"))  # noqa: S608
            for row in rows:
                bad = _row_violations(row, table, enums)
                if not bad:
                    continue
                record = {k: row[k] for k in row.keys()}  # noqa: SIM118
                # Bodies are megabytes and are re-fetchable; keep a length, not the blob.
                if "content_raw" in record:
                    body = record.pop("content_raw")
                    record["content_raw_length"] = len(body) if body else 0
                record["violations"] = bad
                quarantined[table].append(record)

        requeued = 0
        orphaned: list[str] = []
        for record in quarantined["entries"]:
            source_id = record.get("source_id")
            conn.execute("DELETE FROM entries WHERE id = ?", (record["id"],))
            if not isinstance(source_id, str):
                continue
            cur = conn.execute(
                "UPDATE manifest SET processing_state = ?, retry_count = 0, next_retry_at = NULL "
                "WHERE source_id = ? AND relevance_decision = 1",
                (enums.ProcessingState.RELEVANCE_PASSED.value, source_id),
            )
            if cur.rowcount:
                requeued += 1
            else:
                orphaned.append(source_id)

        for record in quarantined["manifest"]:
            conn.execute("DELETE FROM manifest WHERE source_id = ?", (record["source_id"],))
        conn.commit()

        quarantine_path.write_text(
            json.dumps(quarantined, indent=2, default=str),
            encoding="utf-8",
        )
        report["quarantine"] = {
            "entries_deleted": len(quarantined["entries"]),
            "manifest_deleted": len(quarantined["manifest"]),
            "manifest_requeued_for_rescrape": requeued,
            "entries_with_no_manifest_row": orphaned,
            "detail_file": str(quarantine_path),
        }
        logger.info(
            "quarantined %d torn entries + %d torn manifest rows; %d requeued to RELEVANCE_PASSED",
            len(quarantined["entries"]),
            len(quarantined["manifest"]),
            requeued,
        )
        if orphaned:
            logger.warning(
                "%d quarantined entries have no passing manifest row (need re-discovery): %s",
                len(orphaned),
                orphaned,
            )
    finally:
        conn.close()


def verify(out: Path, report: dict[str, Any]) -> bool:
    """Integrity check plus the histograms that prove the salvage is usable."""
    conn = _connect_rw(out)
    try:
        integrity = [r[0] for r in conn.execute("PRAGMA integrity_check")]
        fk = [tuple(r) for r in conn.execute("PRAGMA foreign_key_check")]
        ok = integrity == ["ok"] and not fk
        report["verify"] = {
            "integrity_check": integrity[:50],
            "integrity_ok": integrity == ["ok"],
            "foreign_key_violations": len(fk),
            "alembic_version": conn.execute(
                "SELECT version_num FROM alembic_version",
            ).fetchone()[0],
            "counts": {
                t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # noqa: S608
                for t in (*RECOVERED_TABLES, "batches")
            },
            "manifest_by_state": {
                f"{r[0]}|{r[1]}": r[2]
                for r in conn.execute(
                    "SELECT processing_state, relevance_decision, COUNT(*) "
                    "FROM manifest GROUP BY 1, 2 ORDER BY 3 DESC",
                )
            },
            "manifest_by_source": dict(
                conn.execute("SELECT source, COUNT(*) FROM manifest GROUP BY 1 ORDER BY 2 DESC"),
            ),
            "entries_by_state": dict(
                conn.execute(
                    "SELECT processing_state, COUNT(*) FROM entries GROUP BY 1 ORDER BY 2 DESC",
                ),
            ),
            "entries_missing_content": conn.execute(
                "SELECT COUNT(*) FROM entries WHERE content_raw IS NULL OR content_raw = ''",
            ).fetchone()[0],
            "batches_in_flight": dict(
                conn.execute(
                    "SELECT status, COUNT(*) FROM batches "
                    "WHERE status IN ('submitted', 'processing') GROUP BY 1",
                ),
            ),
            "entries_orphaned_from_manifest": conn.execute(
                "SELECT COUNT(*) FROM entries e "
                "WHERE NOT EXISTS (SELECT 1 FROM manifest m WHERE m.source_id = e.source_id)",
            ).fetchone()[0],
            # Paid work that survived: these are the calls we do not re-submit.
            "paid_work_retained": {
                "manifest_pre_filter_decided": conn.execute(
                    "SELECT COUNT(*) FROM manifest WHERE relevance_decision IS NOT NULL",
                ).fetchone()[0],
                "entries_with_stage1_summary": conn.execute(
                    "SELECT COUNT(*) FROM entries WHERE summary IS NOT NULL AND summary != ''",
                ).fetchone()[0],
                "entries_with_stage2_score": conn.execute(
                    "SELECT COUNT(*) FROM entries WHERE relevance_score IS NOT NULL",
                ).fetchone()[0],
                "entries_with_content_raw": conn.execute(
                    "SELECT COUNT(*) FROM entries WHERE content_raw IS NOT NULL AND content_raw != ''",
                ).fetchone()[0],
            },
        }
        return ok
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corrupt", required=True, type=Path)
    parser.add_argument("--recovered-sql", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--quarantine", type=Path, help="JSON detail of rows dropped as torn")
    parser.add_argument("--staging", type=Path, help="default: <out>.staging.db")
    parser.add_argument("--skip-walk", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-5s %(message)s")
    staging = args.staging or args.out.with_suffix(".staging.db")
    report: dict[str, Any] = {"recover": {}, "walk": {}, "sources": {
        "corrupt": str(args.corrupt),
        "recovered_sql": str(args.recovered_sql),
        "out": str(args.out),
    }}

    build_fresh_db(args.out)
    load_recover_dump(args.recovered_sql, staging)
    copy_recovered_tables(staging, args.out, report)
    rebuild_batches(staging, args.out, report)
    if not args.skip_walk:
        for table in RECOVERED_TABLES:
            walk_table(args.corrupt, args.out, table, report)

    quarantine_torn_rows(
        args.out,
        report,
        args.quarantine or args.out.with_name(f"{args.out.stem}-quarantined-rows.json"),
    )
    ok = verify(args.out, report)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        logger.info("report written: %s", args.report)

    print(json.dumps(report["verify"], indent=2, default=str))
    if not ok:
        logger.error("salvaged db FAILED integrity_check; do not start state-worker on it")
        raise SystemExit(1)
    logger.info("salvaged db passes integrity_check: %s", args.out)


if __name__ == "__main__":
    main()
