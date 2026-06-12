To review later: 

- m1 passed w conditions: 
    New findings
    F-013 (major) — test_escalations_returns_flagged_entry_with_error_log still expects len(error_log)==1, but T8 dual-write correctly produces 2 rows (operational + ALERT). Full suite: 153 passed, 1 failed. Implementation matches spec §14.2/§14.3; the test is stale.

    F-014 (minor) — verify-g2.sh does not run test_state_worker_alerts.py (F-004 proof lives outside the G2 script).

    F-015 (minor) — Plan §8A append is uncommitted (M plan.md only).

    file: .dev\audits\2026-06-11-m1-state-kernel.md

- m2: 
    Verdict: pass-with-conditions
    Implementation matches the task statement and §2 contracts. 78/78 M2 gate tests pass at audit time (G2 slice + scraper suite). No critical findings or shipped contract violations.

    Blocking / major
    ID	Finding	Action
    F-002
    artifact-not-in-HEAD — .dev/plans/m2-discovery/ (plan, handoff, context-map, packets) is untracked at 0954ea8
    Commit the plan directory before M2 sign-off / M3 entry
    F-001
    context-map-stale — scout SHA 7e8be99 predates all M2 code
    Re-scout before M3 (expected; not a code defect)
    Minor conditions
    ID	Finding
    F-004
    RetryExhaustedError loop branch in loop.py has no loop-level test (CHANGELOG defers; envelope covered in T3)
    F-009
    T1 decision log still says stub CMD retained until T5 without supersession
    F-005
    BISHOP_ARXIV_MAX_RESULTS env override has no dedicated test (default 100 is asserted)
    What landed correctly
    bishop_shared/enums.py + drift guard test
    SourceAdapter ABC, Arxiv-only ADAPTER_REGISTRY, §15.1 rate limits, token bucket
    failure_envelope with §6.3 HTTP classification (429 retry, 400 permanent, 403 escalatable)
    ArxivAdapter Atom export API, 7-day backfill default, domain=professional
    scrape_cycle + scheduler, bishop/scraper:m2, scripts/verify-m2.sh
    Kill-criteria falsifiers: 429 survival, idempotency skipped >= 1, batch-failure state guard, compose tag matrix
    Non-goals respected: no state-worker edits, no extra adapters, fetch_content → NotImplementedError("M4")
    Adversarial highlights
    Integration seams (C1–C3): domain wire, compose :m2 tag, idempotency — pass
    C4 rate-limiter ordering: code places acquire() before HTTP in arxiv.py — pass by inspection; plan §5.4 claim of a dedicated acquire-order unit test is overstated (F-006)
    Empty Atom feed: adapter returns []; loop still updates scraper_state — observation (F-007), not a §2 violation
    Upgrade to pass
    Commit .dev/plans/m2-discovery/
    Add a RetryExhaustedError loop test or document an explicit waiver in committed handoff §8.6
    I can commit the plan artifacts or add the F-004 loop test if you want those conditions closed now.