scope: full | nodes: T1,T2,T3,T4 | plan_sha: untracked:078dcf0d99b607e1c82741150741522a886610d0 (HEAD=9afcb991f3a041b3e1dbf676508706861de0dd76) | started: 2026-09-17T22:45Z
2026-09-17T22:45Z | RUN | halted     | reason=plan-absent | plan.md dag.json packets T1–T4 context-map.md all fail git ls-files --error-unmatch
2026-09-17T22:45Z | T1  | blocked    | blocked_by=preflight:plan-absent
2026-09-17T22:45Z | T2  | blocked    | blocked_by=preflight:plan-absent
2026-09-17T22:45Z | T3  | blocked    | blocked_by=preflight:plan-absent
2026-09-17T22:45Z | T4  | blocked    | blocked_by=preflight:plan-absent
2026-09-17T22:48Z | RUN | resume     | plan_tracked_at=8c3b3a784b3047fd7c1c65197e0fc7735fb19139 | plan_content_sha=078dcf0d99b607e1c82741150741522a886610d0 (unchanged)
2026-09-17T22:48Z | T1  | dispatched | model_class=mechanical | packet_sha=778381d7ed863f3faca112ca996b460f4ee034ef | wave0_serial_reason=shared_git_index
2026-09-17T22:55Z | T1  | complete   | commit=1948a72972c7961d2563eb3d9b32d17f5b875577 | brief=runs/T1-brief.md
2026-09-17T22:55Z | T2  | dispatched | model_class=standard | packet_sha=4e0e9e5942d2253ce908fd7f1bf84bc7f4be8084 | wave0_serial_reason=shared_git_index
2026-09-17T23:10Z | T2  | complete   | commit=4411142f9b9e9b1184e5eefed8eb4226b0d884bc | brief=runs/T2-brief.md
2026-09-17T23:10Z | T3  | dispatched | model_class=architectural | packet_sha=285243da4d56946bdc5cc1df6a2ea543007d4c31
2026-09-17T23:25Z | T3  | complete   | commit=6a5eadfec0d6654bffb8fa57a9df11887e9f1698 | brief=runs/T3-brief.md
2026-09-17T23:25Z | T4  | dispatched | model_class=mechanical | packet_sha=d20b8418a54784819bde0793259afac5eef28b7a
2026-09-17T23:40Z | T4  | complete   | commit=dc90d83518402c87059c7144633d512369895e30 | brief=runs/T4-brief.md
