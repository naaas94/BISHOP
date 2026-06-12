Section:      open-questions
Version:      1.1.0
Last updated: 2026-06-12

```
Question:     Should QUERY_API_HOST_PORT and UI_HOST_PORT be documented in .env.example alongside BISHOP_DATA_ROOT?
Impact:       docker-compose.yml, developer onboarding, G1 verification on non-default ports
Closes when:  Decision recorded in decision log; .env.example updated or explicitly rejected with rationale
```

```
Question:     Is tilde expansion of BISHOP_DATA_ROOT=~/bishop_data reliable on all Windows Docker Desktop setups?
Impact:       Volume bind paths, G1 writability checks, init-volumes scripts
Closes when:  Verified on target Windows environments or .env.example mandate switches to explicit paths only
```

```
Question:     Should the per-service volume matrix move from tests/test_compose.py into bishop_shared or a dedicated config module?
Impact:       bishop_shared, docker-compose.yml, T1 coupling surface, future mount additions
Closes when:  M3+ pre-plan or refactor decision chooses single encoding location
```

```
Question:     Should tests/test_state_worker_alerts.py be included in scripts/verify-g2.sh (M1 audit F-014)?
Impact:       G2 gate coverage, §14.3 alert dual-write regression detection
Closes when:  Gate script updated or explicit waiver recorded in committed handoff
```

```
Question:     When will bishop_shared.enums subsume all §20 enums currently duplicated in state-worker/app/enums.py?
Impact:       bishop_shared, state-worker models, drift guard scope
Closes when:  Refactor lands or decision records intentional split (ProcessingState stays state-worker-local)
```
