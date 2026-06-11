Section:      open-questions
Version:      1.0.0
Last updated: 2026-06-10

```
Question:     Should QUERY_API_HOST_PORT and UI_HOST_PORT be documented in .env.example alongside BISHOP_DATA_ROOT?
Impact:       docker-compose.yml, developer onboarding, G1 verification on non-default ports
Closes when:  Decision recorded in decision log; .env.example updated or explicitly rejected with rationale (auditor CR-4 flagged this)
```

```
Question:     Is tilde expansion of BISHOP_DATA_ROOT=~/bishop_data reliable on all Windows Docker Desktop setups?
Impact:       Volume bind paths, G1 writability checks, init-volumes scripts
Closes when:  Verified on target Windows environments or .env.example mandate switches to explicit paths only
```

```
Question:     Should the per-service volume matrix move from tests/test_compose.py into bishop_shared or a dedicated config module?
Impact:       bishop_shared, docker-compose.yml, T1 coupling surface, future M1 mount additions
Closes when:  M1 pre-plan or refactor decision chooses single encoding location
```

```
Question:     How will Phase 2 spec CONDITIONAL verdict (N1–N3) affect M1 state-worker contract before implementation begins?
Impact:       services/state-worker, data-contract-registry, public-interface-inventory
Closes when:  Spec phase2_verdict resolves to approved or M1 plan explicitly cites deferred items
```

**Resolved at M0 (for reference — remove when moved to changelog on confirmation):**

- G1 state-worker health verification path: in-container curl via compose healthcheck, not host-mapped port (context-map A1) — implemented in verify-g1.sh and T4 decision log.
