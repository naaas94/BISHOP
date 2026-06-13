# Architectural decisions — execution-time divergence log

Runtime counterpart to program rationale: absorbed intent drift from milestone execution.

---

## M6 — 2026-06-13

**Spec intent:** Charter M6 requires a single per-domain file lock covering both BM25 indices in the **same write operation**.

**Execution decision:** `Bm25DualIndex` uses one lock file at the domain root but acquires it in separate `with` blocks for `add_main`, `add_challenge_hooks`, and `persist`.

**Rationale:** T3 decision log documents single lock file (not single critical section); acceptable for single-writer MVP; handoff §8.4 waiver F-006.

**Status:** absorbed
