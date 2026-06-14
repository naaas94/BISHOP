# vector-writer embedding device (CPU vs GPU)

Operational note from `docker compose up` on Windows — **2026-06-13**.

---

## Symptom

`vector-writer` logs on first encoder init:

```
INFO:sentence_transformers.base.model:No device provided, using cpu
```

Observed while the stack was starting; model download (`all-MiniLM-L6-v2`) proceeded normally afterward.

---

## Verdict

**Expected behavior — not a GPU detection failure.** The container is running embeddings on CPU because GPU use was never configured at any layer (application, Compose, or image).

---

## Root cause (three independent gaps)

### 1. Application — no device argument

`EmbeddingEncoder` and `QueryEmbeddingEncoder` construct `SentenceTransformer(EMBEDDING_MODEL)` with no `device` parameter. `sentence-transformers` defaults to CPU and logs the message above.

| Service | File |
|---------|------|
| Index-time encoding | `services/vector-writer/app/embedding.py` |
| Query-time encoding | `services/query-api/app/embedding.py` |

Shared model constant: `bishop_shared/indexing_config.py` (`EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"`).

### 2. Docker Compose — no GPU passthrough

`vector-writer` in `docker-compose.yml` has volumes and `STATE_WORKER_URL` only. No `deploy.resources.reservations.devices` (NVIDIA), no `runtime: nvidia`, no `NVIDIA_VISIBLE_DEVICES`.

`query-api` is in the same state (same embedding stack).

### 3. Image — CPU-only PyTorch stack

Both services use `python:3.12-slim` Dockerfiles and install `sentence-transformers` from `requirements.txt`. Pip resolves the default **CPU** PyTorch wheel. There is no CUDA runtime in the image, so `torch.cuda.is_available()` would remain false even if a host GPU were passed through.

---

## Current decision

**Defer GPU support.** CPU is acceptable for the current workload:

| Knob | Default | Env var |
|------|---------|---------|
| Index batch size | 10 | `BISHOP_VECTOR_WRITE_BATCH_SIZE` |
| Poll interval | 120s | `BISHOP_VECTOR_WRITE_POLL_INTERVAL_SEC` |
| Model | `all-MiniLM-L6-v2` (384-dim, small) | `bishop_shared/indexing_config.py` |

Low batch size and long poll interval mean embedding is not the bottleneck today.

---

## If GPU is needed later

All three layers must change together:

1. **Image** — CUDA-capable base (or multi-stage) and `torch` wheel matched to host CUDA version.
2. **Compose** — GPU device reservation on `vector-writer` (and `query-api` if query latency matters). On Docker Desktop for Windows: WSL2 backend, NVIDIA WSL drivers, GPU support enabled in Docker Desktop settings.
3. **Application** — env-driven device (e.g. `BISHOP_EMBEDDING_DEVICE=cuda` with CPU fallback) passed to `SentenceTransformer(..., device=...)`.

Optional: log chosen device at startup after model load for easier ops verification.

---

## Related docs

| Doc | Relevance |
|-----|-----------|
| `.dev/llm-models-and-cache.md` | Embedding model and where it runs |
| `.dev/decision-logs/m6-indexing/T2-lancedb-encoder.md` | `EmbeddingEncoder` design (no device binding) |
| `.dev/decision-logs/m7-read-path/T3-lancedb-duckdb-embedding.md` | Query-side encoder parity |
