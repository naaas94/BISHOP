# Execution summary — m8-hardening-scale

**Scope:** explicit T10-bis,T11 (amendment-4). `{T10-bis, T11}` ran **in parallel**. Prior amendment-3 `{T9,T10,T12}` ran in parallel (T9/T12 complete; T10 halted). T1/T8/T10 not re-dispatched.
**Plan SHA at start / at end:** `f4da8f0057de87cc3eb9c983b0bdc9860d8c668e` / `f4da8f0057de87cc3eb9c983b0bdc9860d8c668e` (v1.5; unchanged mid-run)
**Run status:** complete

## Node outcomes
| ID | Status | model_class | Commit SHA | Summary |
|----|--------|-------------|------------|---------|
| T1 | halted | architectural | — | historical; not re-dispatched |
| T1-bis | complete | architectural | `7fd52b9` | historical |
| T2 | complete | standard | `7a836cb` | historical |
| T3 | complete | standard | `c6bd205` | historical |
| T4 | complete | architectural | `3a4dd2f` | historical |
| T5 | complete | architectural | `97c963b` | historical |
| T6 | complete | standard | `fb7e7e2` | historical |
| T7 | complete | standard | `b064f72` | historical |
| T8 | halted | architectural | — | historical; not re-dispatched |
| T8-bis | complete | architectural | `43a8bc4` | historical |
| T9 | complete | standard | `be024148e02ffbb77d37632e6760b2b0e758ec4d` | F2: registry tests rewritten + positive coverage |
| T10 | halted | standard | not committed | F1: header test outside Files-to-touch |
| T10-bis | complete | standard | `9f183675d6a713d76c3f822dcabb813f012d5c4d` | F1: typed HUGGINGFACE_TOKEN + setattr header test |
| T11 | complete | standard | `f4a793b183c2f636e47e7ebc52c46c2b55beec97` | F3: verify-m8.sh gate completeness |
| T12 | complete | standard | `ba2ad79ca2390b010811563786be8485e86b0164` | F4: compose scraper/ui tags bumped to m8 |

## Completion snapshot (auditor Phase 0.5 / Phase 2 input)
- Final tree SHA: `CEREMONY_SHA_PENDING` (pre-audit §8 ceremony; code HEAD at ceremony start = T10-bis `9f183675d6a713d76c3f822dcabb813f012d5c4d`; T11 parent `f4a793b`)
- Per-node commit SHAs this remediation set: T9 `be02414`; T12 `ba2ad79`; T10-bis `9f18367`; T11 `f4a793b`; T10 none
- Artifact paths this run: `runs/ledger.md`, `runs/T9-brief.md`, `runs/T10-brief.md`, `runs/T10-bis-brief.md`, `runs/T11-brief.md`, `runs/T12-brief.md`, `runs/execution-summary.md`
- Verification command declared by the plan: `scripts/verify-m8.sh` (extended by T11; detached-worktree counts live in plan §8.1)
- Plan §8.1–§8.6 is now populated (amendment-complete, audit-pending; `run_status` remains `amended`; re-audit slot `audit_status: not_run`)

## Open items
- [ ] Re-audit (revision 2) before any `audit_status` ceremony flip — F1–F4 now have landed SHAs
- [ ] T10-bis deferred: `fetch_content` README Authorization not separately asserted (named for auditor)
- [ ] Historical T1 / T8 / T10 HALT packets retained; do not re-dispatch
- [ ] Do not hand-flip `audit_status`; auditor is offered, not invoked
