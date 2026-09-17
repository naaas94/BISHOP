# Source notes (taste + intel)

Standing per-source files for **future agents**. Not a second pre-filter pin.

## What this folder is

One markdown file per registered adapter. Write here:

- operator **taste** (what “good” looks like on this source)
- **content shape** (what the manifest actually contains)
- **intel** (dated findings, junk/keep classes, live-mix surprises)
- **machine facts** that are easy to re-derive wrong (fetch floors, dead APIs, park vs reject)

These files are the place to persist “we learned X about GitHub / ArXiv” so the next session does not rediscover it from chat.

## What this folder is not

- Not `config/profiles/*.yaml`. Those are the **one** NL profile pin for gate 1.
- Not a GitHub-only rubric. That is **option 3** in `repo-gate-next.md` and is **not earned**.
- Not `config/sources/arxiv.yaml`. That is the zero-cost ArXiv **category gate** (primary category only).
- Not gold. Frozen labels stay in `eval/`. Stamps here are narrative + pointers.

## Sources

| file | adapter | gate-1 shape |
|---|---|---|
| [github.md](github.md) | `github` | 2 — repo (title + tagline) |
| [arxiv.md](arxiv.md) | `arxiv` | 1 — paper (real abstract) |
| [semantic_scholar.md](semantic_scholar.md) | `semantic_scholar` | 1 — paper |
| [openreview.md](openreview.md) | `openreview` | 1 — paper |
| [huggingface.md](huggingface.md) | `huggingface` | 3 — model card |
| [lesswrong.md](lesswrong.md) | `lesswrong` | 4 — article (title only) |
| [paperswithcode.md](paperswithcode.md) | `paperswithcode` | 5 — hub dump |

## Rules for agents

1. Before changing fetch, backfill window, shape law, or overlay for a source, **read that source’s file**.
2. Append dated intel. Do not silently rewrite history.
3. Do **not** invent per-source routing or a second profile pin from these notes. One pin until a later eval earns a split.
4. Call 2 `relevance_score` is not gold on any source.

## Related

- Pickup / next GitHub work: `repo-gate-next.md`
- Operator taste log (cross-source): `relevance_log.md`
- Overlay: `.dev/decision-logs/ops/soft-launch-precision-overlay.md`
- Shape law: `config/prompts/prefilter_rubric_v1.md`
- Pin (live): `config/profiles/professional_v1.2.0_soft_launch.yaml`
- Gold prefilter set: `eval/prefilter_v0/` (profile under test there is still `professional_v1.0.0.yaml`)
