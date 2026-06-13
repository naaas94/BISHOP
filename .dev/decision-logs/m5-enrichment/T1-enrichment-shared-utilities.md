# T1 — Enrichment shared utilities

**Plan:** m5-enrichment · **Date:** 2026-06-13

## Chosen approach

- **Tokenizer:** `tiktoken` `cl100k_base` for §13.1 4,000-token ceiling; declared in `pyproject.toml` `[project.optional-dependencies] dev` (T3/T4 Dockerfiles add service requirements).
- **Truncation strategies:** Per-source helpers in `content_truncation.py` — papers (abstract + 2k body), github (500-token header + structure lines), HF model (YAML frontmatter + 2k markdown), default beginning/end (2.5k + 500) for articles and unknown `entry_type_hint`.
- **Taxonomy:** `TAG_TAXONOMY` frozenset mirrors spec §20.8 literals exactly; `validate_tags` returns `(validated, stripped)` in input order.
- **Prompts:** Appendix A schema in `build_call1_system_prompt` with injected taxonomy list; Call 2 system blocks use Anthropic `cache_control: {type: ephemeral}` on the profile prefix block only.
- **Parsers:** `parse_call1_response` / `parse_call2_response` dataclasses mirror batch-poller pre-filter parse pattern; OOV tags stripped without failing the entry.

## Alternatives rejected

- **Character-based truncation:** Rejected — spec §13.1 binds token ceiling measured with tiktoken.
- **Single combined enrichment call:** Rejected — spec §13.2 mandates two-call separation; T1 only builds Call 1/2 surfaces.
- **Putting `EntryTypeEnum` in `bishop_shared`:** Rejected — enum lives in state-worker; parser validates literal strings from Appendix A schema.

## Assumptions made

- `cl100k_base` is acceptable for §13.1 measurement despite Anthropic model tokenizer differences (plan load-bearing assumption).
- When `entry_type_hint` is unknown at truncation time, beginning/end strategy is safe default (context-map Flag 3); HF model and github paths activate only when hint/source are known.
- Paper abstract split via `Abstract` heading heuristic is sufficient for M5 unit fixtures; live HTML quality is M8 concern.

## Items deferred

- **Live HF model-card YAML extraction e2e:** Unit fixtures only per plan risks; M8 owns adapter-specific validation.
- **HuggingFace model truncation without `entry_type_hint`:** Falls back to beginning/end until batcher passes hint from poll metadata in T3/T4.
- **Parser adversarial gap — markdown code-fence wrapped JSON:** Regex/object extractor may fail fenced responses; deferred — batch-poller T5 may add fence stripping if e2e surfaces it.
