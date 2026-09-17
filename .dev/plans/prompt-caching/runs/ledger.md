scope: full | nodes: T1,T2,T3,T4,T5,T6,T7,T8,T9,T10 | plan_sha: 70c5501 | started: 2026-09-12T18:58Z
2026-09-12T18:58Z | T1  | dispatched | model_class=architectural | packet_sha=e775a75
2026-09-12T18:59Z | T1  | dispatched | model_class=architectural | packet_sha=e775a75
2026-09-12T19:07Z | T1  | halted     | reason=kill-criterion-falsifier-outside-files-to-touch | brief=runs/T1-brief.md
2026-09-12T19:07Z | T2  | blocked    | blocked_by=T1
2026-09-12T19:07Z | T3  | blocked    | blocked_by=T1
2026-09-12T19:07Z | T4  | blocked    | blocked_by=T1
2026-09-12T19:07Z | T5  | blocked    | blocked_by=T1
2026-09-12T19:07Z | T6  | blocked    | blocked_by=T1
2026-09-12T19:07Z | T7  | blocked    | blocked_by=T1
2026-09-12T19:07Z | T8  | blocked    | blocked_by=T1
2026-09-12T19:07Z | T9  | blocked    | blocked_by=T1
2026-09-12T19:07Z | T10 | blocked    | blocked_by=T1
2026-09-12T19:07Z | G1  | blocked    | blocked_by=T1
2026-09-12T19:33Z | T1-bis | dispatched | model_class=architectural | packet_sha=36cd6bf | plan_sha=372ea5e
2026-09-12T19:42Z | T1-bis | complete   | commit=8d9af01 | brief=runs/T1-bis-brief.md
2026-09-12T19:42Z | T2  | dispatched | model_class=architectural | packet_sha=40c5f36
2026-09-12T19:42Z | T3  | dispatched | model_class=architectural | packet_sha=0e77ac6
2026-09-12T19:42Z | T4  | dispatched | model_class=architectural | packet_sha=d6d1f55
2026-09-12T19:42Z | T8  | dispatched | model_class=standard | packet_sha=eb2d762
2026-09-12T19:42Z | T9  | dispatched | model_class=architectural | packet_sha=a37b30f
2026-09-12T19:46Z | T8  | complete   | commit=c8fc67d | brief=runs/T8-brief.md
2026-09-12T19:47Z | T9  | halted     | reason=files-to-touch-vs-existing-test | brief=runs/T9-brief.md
2026-09-12T19:47Z | T10 | blocked    | blocked_by=T9
2026-09-12T19:47Z | G1  | blocked    | blocked_by=T9
2026-09-12T19:56Z | T3  | complete   | commit=c6d9f80 | brief=runs/T3-brief.md
2026-09-12T20:03Z | T4  | complete   | commit=e4b7e9d | brief=runs/T4-brief.md
2026-09-12T20:07Z | T2  | complete   | commit=d0f37d3 | brief=runs/T2-brief.md
2026-09-12T20:23Z | T9-bis | dispatched | model_class=architectural | packet_sha=0cd06f6 | plan_sha=614e46b
2026-09-12T20:38Z | T9-bis | complete   | commit=c47248e | brief=runs/T9-bis-brief.md
2026-09-12T20:38Z | T5  | dispatched | model_class=standard | packet_sha=b5f5258
2026-09-12T20:38Z | T6  | dispatched | model_class=architectural | packet_sha=bdafd4e
2026-09-12T20:38Z | T7  | dispatched | model_class=architectural | packet_sha=a14b678
2026-09-12T20:40Z | T5  | complete   | commit=eb9b873 | brief=runs/T5-brief.md
2026-09-12T20:41Z | T7  | halted     | reason=prior-log-supersession | brief=runs/T7-brief.md
2026-09-12T20:41Z | T10 | blocked    | blocked_by=T7
2026-09-12T20:41Z | G1  | blocked    | blocked_by=T7
2026-09-12T20:56Z | T6  | complete   | commit=ba49bb1 | brief=runs/T6-brief.md
2026-09-12T21:18Z | T7-bis | dispatched | model_class=architectural | packet_sha=7715ed7 | plan_sha=3e588e8
2026-09-12T21:32Z | T7-bis | complete   | commit=1fe3ef4 | brief=runs/T7-bis-brief.md
2026-09-12T21:32Z | T10 | dispatched | model_class=standard | packet_sha=e584177 | plan_sha=3e588e8
2026-09-12T21:38Z | T10 | halted     | reason=frozen-path-baseline-stale | brief=runs/T10-brief.md
2026-09-12T21:38Z | G1  | blocked    | blocked_by=T10
2026-09-12T21:52Z | T10-bis | dispatched | model_class=standard | packet_sha=27ae4bf | plan_sha=d28e809
2026-09-12T22:13Z | T10-bis | complete   | commit=21c8e3d | brief=runs/T10-bis-brief.md
2026-09-12T22:25Z | G1  | gate-satisfied | cache_key=A | second_complete=ebc1c3be | cache_read_tokens=276150
2026-09-12T22:50Z | T11 | dispatched | model_class=standard | packet_sha=fd74849 | plan_sha=5704555
2026-09-12T22:58Z | T11 | complete   | commit=31b68f1 | brief=runs/T11-brief.md
2026-09-15T12:40Z | T12 | direct-implementation | model_class=standard | packet=none (operator-approved, outside orchestrator dispatch) | closes=FU-CACHE-WARMUP-01 | decision-log=.dev/decision-logs/prompt-caching/T12-cache-warmup-ping.md
