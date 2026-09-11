scope: full | nodes: T1,T2,T3,T4,T5,T6,T7,T8 | plan_sha: 76db7fc169788d1a5cd2f2b2eeed79834b97ad16 | started: 2026-09-10T17:43Z
2026-09-10T17:43Z | T1 | dispatched | model_class=architectural | packet_sha=b69ee8d12da7d4604c04f31ac3707dc4653292cc2026-09-10T17:47Z | T1 | halted     | reason=Implementation needs files outside Files to touch | brief=runs/T1-brief.md
2026-09-10T17:47Z | T2 | blocked    | blocked_by=T1
2026-09-10T17:47Z | T3 | blocked    | blocked_by=T1
2026-09-10T17:47Z | T4 | blocked    | blocked_by=T1
2026-09-10T17:47Z | T5 | blocked    | blocked_by=T1
2026-09-10T17:47Z | T6 | blocked    | blocked_by=T1
2026-09-10T17:47Z | T7 | blocked    | blocked_by=T1
2026-09-10T17:47Z | T8 | blocked    | blocked_by=T1

2026-09-10T17:52Z | T1-bis | dispatched | model_class=architectural | packet_sha=e3b9f625a8757e281fc56aa8efbfe06f5e4d1b8f | scope=explicit:T1-bis
2026-09-10T17:52Z | T1-bis | halted     | reason=Binding artifact not git-tracked | brief=runs/T1-bis-brief.md
2026-09-10T17:55Z | T1-bis | dispatched | model_class=architectural | packet_sha=e3b9f625a8757e281fc56aa8efbfe06f5e4d1b8f | scope=explicit:T1-bis resume
2026-09-10T18:04Z | T1-bis | complete   | commit=7fd52b97f4ba5a54e3f7299cd85c0ea1e10977d9 | brief=runs/T1-bis-brief.md
2026-09-10T18:04Z | T2 | dispatched | model_class=standard | packet_sha=d08e661fb77673dc7c2d69c25ef87102fd3d88de
2026-09-10T18:04Z | T3 | dispatched | model_class=standard | packet_sha=54c4b5f6d0a9f3bd9871224ca892d5e47931dc19
2026-09-10T18:04Z | T4 | dispatched | model_class=architectural | packet_sha=adfa00688a4bfec90a8842593e271fdc819f4c78
2026-09-10T18:04Z | T5 | dispatched | model_class=architectural | packet_sha=5bfe9e7df598ddff75cc99bb69c288275453d0f4
2026-09-10T18:04Z | T7 | dispatched | model_class=standard | packet_sha=700757245098804c8dbe9ea7ece61cc1b33a53a6
2026-09-10T18:20Z | T2 | complete   | commit=7a836cb | brief=runs/T2-brief.md
2026-09-10T18:20Z | T3 | complete   | commit=c6bd205b5d2270682a3e87cfb4d21df28e34b37f | brief=runs/T3-brief.md
2026-09-10T18:20Z | T4 | complete   | commit=3a4dd2f0b21261132a7c513b74f379193c4a88c9 | brief=runs/T4-brief.md
2026-09-10T18:20Z | T5 | complete   | commit=97c963b909dc21fad88681c987848a6dc5f0ec8c | brief=runs/T5-brief.md
2026-09-10T18:20Z | T7 | complete   | commit=b064f72 | brief=runs/T7-brief.md
2026-09-10T18:20Z | T6 | dispatched | model_class=standard | packet_sha=08b9233d4ff0c7f95cb33c9342add017fc876d78
2026-09-10T18:23Z | T6 | complete   | commit=fb7e7e2180cbae1c15ef20a295c722c199584ad9 | brief=runs/T6-brief.md
2026-09-10T18:23Z | T8 | dispatched | model_class=architectural | packet_sha=1e4d8199533d6061a5c965fe95a451632c81690c
2026-09-10T18:24Z | T8 | halted     | reason=G4/G5/G6 owner sign-off missing (G6 enrichment checklist) | brief=runs/T8-brief.md

scope: explicit | nodes: T8-bis | plan_sha: 7f512c64f9c1ee9b2437de97ac68ceb438eb4ffa | started: 2026-09-10T23:28Z
2026-09-10T23:28Z | T8-bis | dispatched | model_class=architectural | packet_sha=b2b12994048f754c57793cec307f60f60869702e | scope=explicit:T8-bis
2026-09-10T23:55Z | T8-bis | complete   | commit=43a8bc42d5c7499593849e3aab8b5ec918120cde | brief=runs/T8-bis-brief.md

scope: explicit | nodes: T9,T10,T11,T12 | plan_sha: e3fe55b07acd93d97b31a9c712c4994f58e727a0 | started: 2026-09-11T01:25Z
2026-09-11T01:25Z | T9  | dispatched | model_class=standard | packet_sha=a248eb76b54e0ab821551a4fa9757445ede81f9f
2026-09-11T01:25Z | T10 | dispatched | model_class=standard | packet_sha=3074232bedf99ada0684b96ac7dc54904c068343
2026-09-11T01:25Z | T12 | dispatched | model_class=standard | packet_sha=f66c29bdb8f11c50a30cb564e1e33d58c3258b6c
2026-09-11T01:28Z | T9  | complete   | commit=be024148e02ffbb77d37632e6760b2b0e758ec4d | brief=runs/T9-brief.md
2026-09-11T01:28Z | T12 | complete   | commit=ba2ad79ca2390b010811563786be8485e86b0164 | brief=runs/T12-brief.md
2026-09-11T01:28Z | T10 | halted     | reason=Existing tests break (executor skill §Hard prohibitions / self-check item 4) | brief=runs/T10-brief.md

scope: explicit | nodes: T10-bis,T11 | plan_sha: f4da8f0057de87cc3eb9c983b0bdc9860d8c668e | started: 2026-09-11T01:34Z
2026-09-11T01:34Z | T10-bis | dispatched | model_class=standard | packet_sha=ef20491345f0a4836746b72b1c9eb7dbe7f7a4ba | scope=explicit:T10-bis,T11
2026-09-11T01:34Z | T11 | dispatched | model_class=standard | packet_sha=44c2819f50760169cbb48d2a16f2eadfadb86b09 | scope=explicit:T10-bis,T11
2026-09-11T01:36Z | T11 | complete   | commit=f4a793b183c2f636e47e7ebc52c46c2b55beec97 | brief=runs/T11-brief.md
2026-09-11T01:38Z | T10-bis | complete   | commit=9f183675d6a713d76c3f822dcabb813f012d5c4d | brief=runs/T10-bis-brief.md
