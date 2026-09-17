# arxiv

Adapter: `services/scraper/app/adapters/arxiv.py`  
Shape: **1 — paper** (real abstract). Highest-evidence academic shape.

## Taste

Operator wants **applied** systems, architecture of products (not of the base model), skills, workflows, shipped practice. ArXiv’s nature is paper-coded: pretraining, weights, internals, experimental SOTA. That is often on-topic for “AI” and still the wrong flavor.

From `relevance_log.md` (soft-launch):

- `arxiv:2606.11375` — pretraining, not applied engineering; Call 2 0.35
- `arxiv:2606.11722` — LLM internal representations; interesting as a summary, not the niche
- Overall: “too aie based but not in the way I’m interested in; applied, systems, architecture but not of the llm itself”

Logged keep (rare, write more as they appear):

- `arxiv:2607.19592` — Knowledge-Centric Self-Improvement

Cross-source want-list (also in `relevance_log.md` meta): skills, WFs, knowledge you don’t possess, LLM-based **systems**, architectures, reviews, stacks, techniques, agents, eval, observability, backend, quantification of results, explainability, stakeholder management — tied to the professional profile.

## Machine today

- Queries `cs.AI`, `cs.CL`, `cs.LG`.
- Zero-cost **category gate** (primary category only): `config/sources/arxiv.yaml`. Do not switch to any-category matching — cross-lists are noisy (`eval/prefilter_v0`). Empty `include_categories` is intentional; exclusion list does the work.
- Spec backfill window 60 days; live overlay currently **7 days**.
- Gate 1: same pin as every source. Do not invent an ArXiv-only profile because papers “feel academic.” Tighten taste in the **shared** profile/rubric, or accept that ArXiv will keep producing paper-shaped passes.

## Intel

- Soft-launch mix: ArXiv **pass rate is high** relative to HF/GitHub, but many passes are the wrong flavor (research internals vs stealable practice). That is a taste/profile problem, not a fetch-floor problem.
- Gold set for the **shared** prefilter (not ArXiv-only): `eval/prefilter_v0/`. Do not edit `items.json` after freeze.

## Do not

- Treat Call 2 as gold.
- Expand categories or any-category matching without replaying `eval/prefilter_v0`.
- Drop ArXiv from the registry because the flavor is wrong — document and calibrate; the applied sources (GitHub first) are the faucet we open after the repo bar is fixed.
