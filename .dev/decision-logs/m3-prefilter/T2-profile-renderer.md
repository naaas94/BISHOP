# T2 — NL profile renderer and professional v1.0.0

**Plan:** m3-prefilter · **Date:** 2026-06-13

## Chosen approach

- **Profile YAML:** `config/profiles/professional_v1.0.0.yaml` authored per §11.2 example content with committed `canonical_hash`.
- **Hash algorithm (Flag 6 resolution):** `compute_profile_hash()` loads YAML → dict, **excludes `canonical_hash`**, `json.dumps(..., sort_keys=True, ensure_ascii=True)` → SHA-256 hex. Same path at authoring and batch time (T4). Prompt text is **not** hashed.
- **System prompt:** `render_profile_prompt()` builds a fixed-section markdown template from `context`, `principles`, `anchors`, `exclusions`, and `output.instruction` — deterministic ordering, double-newline separators, trailing newline.
- **Profile selection (Flag 7):** `resolve_profile_path(DomainEnum.PROFESSIONAL)` → `/app/config/profiles/professional_v1.0.0.yaml`; `PERSONAL` raises `ValueError` (deferred §3.2).
- **Volume seed:** `scripts/seed-profiles.sh` / `.ps1` copy `config/profiles/` → `${BISHOP_DATA_ROOT}/profiles` only when destination is empty (compose volume overlay C1).

## Alternatives rejected

- **Hash raw YAML bytes:** Rejected — §11.3 and plan Flag 6; non-deterministic across parsers/environments.
- **Hash `render_profile_prompt()` output:** Rejected — plan §2 freeze separates LLM system prompt from audit hash; `profile_render_hash` matches `canonical_hash` via JSON dict path.
- **Include `canonical_hash` in hash input:** Rejected — circular dependency; stored hash could never match recomputation after commit.
- **Active profile pointer file:** Rejected for M3 — hardcoded filename per Flag 7.

## Assumptions made

- `canonical_hash` field is excluded from `_hashable_dict()` so committed YAML self-verifies at batch time.
- **Hash input surface:** `compute_profile_hash()` accepts `Path` or raw YAML `dict` only (full file content minus `canonical_hash`); `ProfileDocument` is the typed load surface for prompt rendering, not hash serialization.
- PyYAML is available in dev/test and will be declared in service `requirements.txt` when pre-filter-worker ships (T4); not added to `pyproject.toml` in T2 (out of files-to-touch).

## Items deferred

- **LLM relevance quality (G6):** Prompt template structure is functional for M3; empirical tuning is M8 scope per plan risk note.
- **Personal domain profile and pointer mechanism:** §3.2 / Flag 7 — M3 professional only.
- **PyYAML in `pyproject.toml` dev deps:** Adjacent per context-map; service requirements in T4.
