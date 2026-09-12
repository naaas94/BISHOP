# config/prompts

Rubric annexes for the three Anthropic batch gates (pre-filter, enrichment
Call 1, enrichment Call 2). Unlike `config/profiles/`, this directory is
**image-baked, never bind-mounted** (prompt-caching plan §2 row 16) — the
`COPY config/prompts` line in `services/pre-filter-worker/Dockerfile` and
`services/enrichment-batcher/Dockerfile` is the only way these files reach
a running container. A rubric change requires an image rebuild.

Files land here as siblings own their subtasks:

- `prefilter_rubric_v1.md` — source-shape law (T2)
- `call1_rubric_v1.md` — extraction guidance (T3)
- `call2_rubric_v1.md` — relevance-scoring guidance (T4)

Each file follows the front-matter schema enforced by
`bishop_shared/rubric_assets.py`:

```
---
rubric_id: <prefilter_rubric|call1_rubric|call2_rubric>
version: "<semver>"
canonical_hash: "<64-hex sha256 of the body>"
---
<body>
```

Stamp/verify the hash with `python scripts/rubric_hash.py <path> [--render]`.
