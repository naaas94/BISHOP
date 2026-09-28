# Search prompt shape

**Date:** 2026-09-27
**Scope:** `GET /search` on the live index (`http://localhost:8080/search`). Five queries, same hour, about TypeSafe Jev. Not a gate change, not a profile bump, not an MCP build.

## What happened

A query that named the thing put the three indexed Jev papers at the top of 20 hits:

`Jev TypeSafe System One decision model` → `arxiv:2609.30186`, `arxiv:2609.26550`, `arxiv:2609.24052`.

Four other articulations of the same idea did not:

| Query | Top of the list |
|---|---|
| `reinforcement learning for calibrated decisions` | Other RL papers. No Jev id. |
| `model that returns a yes or no probability about a document instead of writing text` | Generated-text detection first. The crash-narrative Jev paper second. |
| `non-generative monitor that scores whether submitted code hides a backdoor` | Code monitors and scanners. No Jev id. |
| `cheap gate that says whether a paper or repository is worth keeping, with a confidence score` | Enterprise eval and abstention papers. No Jev id. |

All five ran with `problem_shaped=false`, channels `bm25_main` and `dense`.

## What the hit card is safe for

The title and `source_id` were enough to open the papers. The summary and `relevance_score` were not enough to use a number.

- `arxiv:2609.26550` summary began "99% of GPT-4's accuracy". The paper's 99% line is a cascade that keeps 99% of GPT-6's accuracy at 57% of its fee.
- `arxiv:2609.30186` summary led with 79% AndroidWorld success. Table 1 is 0.79 for Jev-Mobile, 0.78 for SeeAct-V, and 0.84 for a step-wise VLM.
- Call 2 scored the GUI paper and the judge paper at 0.76 and the crash-narrative audit at 0.38. The audit is the paper that changed the Jev plan. The GUI paper did not.

Paper notes and the corrected reading: `.dev/scouting/2026-09-27-jev-typesafe/report.md` (F7, F9).

## Rule

Name the entity in `q` when you know it. A paraphrase of the method or the task is a different search. Read the paper, or `GET /entries/{source_id}`, before citing a summary figure. `relevance_score` is Call 2's taste score. It does not rank which hit is useful for the question you asked.

Indexed as PB-016 (`closed`, `ops`) in `product-backlog.yaml`.
