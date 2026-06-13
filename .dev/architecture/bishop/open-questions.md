Section:      open-questions
Version:      1.3.0
Last updated: 2026-06-13

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

```
Question:     When will personal domain profile YAML and pre-filter routing be added (M3 is professional-only)?
Impact:       config/profiles/, pre-filter-worker domain gate, charter M3 scope boundary
Closes when:  M4+ charter slice or explicit deferral recorded in decision log
```

```
Question:     Should bishop_shared re-export profile_renderer and anthropic_config from __init__.py?
Impact:       import conventions across pre-filter-worker, batch-poller, tests
Closes when:  Refactor or explicit decision to keep direct submodule imports only
```

```
Question:     When will test_escalations_returns_flagged_entry_with_error_log be updated for T8 ALERT sibling rows?
Impact:       Full-suite pytest (368/369 green); escalations panel contract tests
Closes when:  Test updated per OPEN-001 option A in .dev/known-test-failures.md, or router filtering decided per option B
```
