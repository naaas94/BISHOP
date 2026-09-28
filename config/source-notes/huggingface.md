# huggingface

Adapter: `services/scraper/app/adapters/huggingface.py`  
Shape: **3 — model card** (card text / pipeline tags, not a paper abstract).

## Taste

Operator want-list is **systems and practice**, not another 7B instruct dump. A model card that is “an LLM for X” is usually peripheral or reject unless it carries a stealable recipe (training setup, eval harness, agent stack) — and even then GitHub is usually the better artifact.

No HF keep-list stamped yet. Default posture: **flood, almost all reject**.

## Machine today

- Spec backfill window 30 days. Live incremental already produced a large HF pile (~99% gate-1 reject in the soft-launch mix).
- **Do not rewind Hugging Face.** Stated in overlay / faucet work and in `repo-gate-next.md`.
- Gate 1: same pin. Shape 3: do not read a card as if it were a paper abstract.

## Intel

- Soft-launch: HF is the volume problem next to GitHub. GitHub is the one we want *if* the quality bar holds. HF is not the faucet to open.
- 7-day rewind still added ~286 incremental HF rows. That is not a success metric.

## Intel — 2026-09-27 cohort

Discovered 2026-09-11..09-21 UTC (discovery clock, settled window; host down 09-22..25): 13,200 of 30,052 discoveries (44%) and 7 of 189 INDEXED (3.7%). Volume without yield. Rewind stays closed. No HF-only profile (option 3 is not earned). Run: `.dev/insights-manager/runs/2026-09-27-r001.md` (F-005).

## Do not

- Extend HF lookback to “fill the corpus.”
- Add an HF-only profile because reject-rate is high — the shared gate is already rejecting; the cost is fetch + gate-1 tokens.
- Confuse HF model cards with GitHub repos of the same name.
