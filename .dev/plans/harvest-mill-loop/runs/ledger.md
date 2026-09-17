scope: full | nodes: T1,T2,T3,T4 | plan_sha: untracked:078dcf0d99b607e1c82741150741522a886610d0 (HEAD=9afcb991f3a041b3e1dbf676508706861de0dd76) | started: 2026-09-17T22:45Z
2026-09-17T22:45Z | RUN | halted     | reason=plan-absent | plan.md dag.json packets T1–T4 context-map.md all fail git ls-files --error-unmatch
2026-09-17T22:45Z | T1  | blocked    | blocked_by=preflight:plan-absent
2026-09-17T22:45Z | T2  | blocked    | blocked_by=preflight:plan-absent
2026-09-17T22:45Z | T3  | blocked    | blocked_by=preflight:plan-absent
2026-09-17T22:45Z | T4  | blocked    | blocked_by=preflight:plan-absent
