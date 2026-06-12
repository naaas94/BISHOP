To review later: 

- m1 passed w conditions: 
    New findings
    F-013 (major) — test_escalations_returns_flagged_entry_with_error_log still expects len(error_log)==1, but T8 dual-write correctly produces 2 rows (operational + ALERT). Full suite: 153 passed, 1 failed. Implementation matches spec §14.2/§14.3; the test is stale.

    F-014 (minor) — verify-g2.sh does not run test_state_worker_alerts.py (F-004 proof lives outside the G2 script).

    F-015 (minor) — Plan §8A append is uncommitted (M plan.md only).

    file: .dev\audits\2026-06-11-m1-state-kernel.md