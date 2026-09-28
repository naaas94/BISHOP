# Value Scout — jev-typesafe — 2026-09-27

Operator 2026-09-27: this run folder is the record. Do not open a backlog row, a learning note, or a decision log for it unless a later session picks up F1.

## Source
Type:           mixed
Location:       First-party: https://typesafe.ai/blog/introducing-system-one-models-and-jev and https://docs.typesafe.ai (models, API, primitives, confidence, jaggedness, machine-learning primer). Paper: https://arxiv.org/html/2609.29429v1 . Audits: https://truestandard.ai/blog/jev-accuracy-tested ; https://escholarship.org/content/qt4t4449jv/qt4t4449jv.pdf . Practitioners: https://www.lesswrong.com/posts/d7pQicW8EhpPBDRqz/a-non-generative-model-as-a-trusted-monitor-for-ai-control ; https://www.lesswrong.com/posts/GHCNKiFzDYThTELFp/jev-as-a-cot-monitor-6x-faster-and-500x-cheaper . Secondary only where labeled in notes.
Retrieved:      2026-09-27
Author/origin:  TypeSafe AI (Jev, announced 2026-09-15, CEO Diogo Almeida). Independent measurements: Arun Agrahri (TrueStandard, 2026-09-18); Lingsen Meng (UCLA preprint, 2026-09-24); Guo, Liu, Deng, Li, Zhao, Wu, Chen, Zhang, Zhang (arXiv 2609.29429v1, university affiliations, no TypeSafe author line). Practitioners: Venkat T (2026-09-18), mahi-pas (2026-09-23).
Why this, now:  Operator asked what Jev is, from papers and public discussion, and whether any of it is worth carrying into Bishop.
Scan depth:     deep — method limits and independent numbers, not the launch abstract alone.
Coverage:       Read in full: launch post; docs pages listed in `notes/vendor-launch.md` and `notes/api-shape.md`; arXiv 2609.29429 (abstract, method, results, limitations); TrueStandard; Meng preprint extract; both LessWrong posts. Amendment the same day, after `GET /search` on the live index: full HTML of arXiv 2609.30186 (Jev-Mobile), 2609.26550 (JEV-as-a-Judge), and 2609.24052 (crash narratives). Sampled as non-measurements: Kingy review (no API call), Prefactor (no API call). Unofficial mirrors (`jevtypesafeai.com`, `jevwiki.ai`) used only to separate conflicting prices. Not read: evals.typesafe.ai workflow cases. Neighbor hits from the other four searches (generic RL, code monitors, enterprise eval) were not scouted.
Run dir:        .dev/scouting/2026-09-27-jev-typesafe/

## Findings

| ID | Type | Claim | Gate result | Destination | Status |
|----|------|-------|-------------|--------------|--------|
| F1 | experiment-hypothesis | Shadow-score pinned `jev-1.13.0` on frozen public gate labels before any pipeline change | kept | operator experiment note beside PB-008 (do not open a PB in this run) | unrouted |
| F2 | risk-or-antipattern | Treat the returned probability as a ranking until it is binned on Bishop labels | kept | `.dev/retrospectives/learning/` | unrouted |
| F3 | risk-or-antipattern | A live gate uploads title and abstract to a closed API and drops the rationale string | kept | `.dev/retrospectives/learning/` | unrouted |
| F4 | concept | The contract is a typed decision plus a probability; schema match, calibration, and accuracy are three different properties | kept | `.dev/retrospectives/learning/` | unrouted |
| F5 | concept | An attention must-look flag fits a noul; the digest sentence does not | kept | `.dev/retrospectives/learning/` (theme: attention-pass consumer) | unrouted |
| F6 | reference-only | RLCD is a named objective with no published reward, data, or architecture | kept | — | unrouted |
| D1 | — | Jev can replace enrichment Call 2 | declined:EG3 | — | declined |
| D2 | — | Add Jev as a second live LLM pre-filter in front of Haiku | declined:EG1 | — | declined |
| D3 | — | Jev can write the attention-pass digest | declined:EG3 | — | declined |
| D4 | — | Budget Jev at $0.42 per million input tokens | declined:EG3 | — | declined |
| D5 | — | Study 2005 Justification Endorsed Voting for Bishop | declined:EG4 | — | declined |
| D6 | — | Question rewrites will fix thin manifests | declined:EG3 | — | declined |
| D7 | — | Budget latency at the vendor 70ms floor | declined:EG3 | — | declined |
| D8 | — | Best-of-N monitor economics matter on the ingest path | declined:EG4 | — | declined |
| D9 | — | Date and counting jaggedness makes Jev unfit for the paper corpus | declined:EG3 | — | declined |
| F7 | experiment-hypothesis | Run the shadow score in the shape of the crash-narrative audit: pin the id, record the id returned, refit only on Bishop labels | kept | same home as F1 (this folder) | unrouted |
| F8 | risk-or-antipattern | A relevance judgment is not one of the workloads JEV-as-a-Judge marks safe to accept | kept | this folder | unrouted |
| F9 | risk-or-antipattern | Cite the paper notes here, not the indexed search snippet, when the number is load-bearing | kept | this folder | unrouted |
| D10 | — | Jev-Mobile's AndroidWorld success is evidence for a Bishop document gate | declined:EG3 | — | declined |
| D11 | — | Reuse τ=0.9 or the Texas Platt map as Bishop's cutoff | declined:EG3 | — | declined |

## Kept findings (detail)

### F1
Type:        experiment-hypothesis
Claim:       Shadow-score pinned `jev-1.13.0` on frozen public gate labels before any pipeline change.
Evidence:    TypeSafe docs, question type noul: answer field is `noul` in 0–1, questions in one call share one state (`notes/api-shape.md`, primitives). Cost basis, first-party: "Input tokens: $0.042 / MTok ($ 42 per billion tokens). Output tokens: FREE" (launch post). TrueStandard ran Jev 1.13 on 108 hand-labeled claims for "$0.00033". Bishop already has the measurement surface: "Do not treat `relevance_score` as the pre-filter gold. Eval gold lives in `eval/prefilter_v0/`." (`.dev/sqlite.md`).
Why it matters: The binary gate is the only Bishop stage whose shape matches a noul. Everything else in the launch is a vendor story until that slice is scored.
Destination: operator experiment note beside PB-008. This run does not add a backlog row.
Next step:   One offline script, public eval items only, model pinned to `jev-1.13.0`, state = title + abstract, instructions = the rendered professional profile (or a faithful short form of that same bar). Record the model id the service returns on each call (F7). Fit any cutoff on a selection split of these labels; do not import τ=0.9 or the Texas Platt map (D11). Falsifier: on `eval/prefilter_v0/`, precision/recall does not beat the frozen Haiku gate, or dollars per item with the rubric inside `instructions` are not lower than cached Haiku on the same slice, or ECE is not better than Haiku asked for a 0–1 probability. Any one falsifier ends it. A win still does not authorize a compose service (F3). Optional second slice: `eval/github_repo_gate_v0/`, same pin, no profile split.
Status:      unrouted

### F2
Type:        risk-or-antipattern
Claim:       Treat the returned probability as a ranking until it is binned on Bishop labels.
Evidence:    Launch post: workflow reference is "the average of GPT-6 Astra and Fable 5.1", not ground truth. TrueStandard, 108 claims: ECE 0.0660 (Jev 1.13), 0.0611 (Gemini 3.1 Flash Lite), 0.0669 (Claude Haiku 4.5); author: "A cheap frontier-lab model, asked properly for a probability, calibrates about as well as the model built to produce calibrated probabilities." Meng preprint: "the calibration error changes by 0.071 between two ways of posing the same question"; SST-2 yes/no ECE 0.091, choice form 0.020. arXiv 2609.29429: "The probabilities rank well but do not transfer as thresholds: the median ECE is 0.168 against a null of 0.074." Vendor jaggedness: refund noul 0.72 and not_refund 0.47, sum 1.19. Venkat T, hypothesis B: under-confident above ~0.3, "great ranking and a poor probability."
Why it matters: A Bishop threshold copied from the launch post would be a ranking used as a probability.
Destination: `.dev/retrospectives/learning/`
Next step:   If F1 is run, publish a reliability table on that labeled slice before anyone picks a cutoff. Ask one noul, not a complementary pair.
Status:      unrouted

### F3
Type:        risk-or-antipattern
Claim:       A live gate uploads title and abstract to a closed API and drops the rationale string.
Evidence:    `AGENTS.md`: "Bishop is a local-first ingest pipeline (scrape → pre-filter → enrich → index → query)." Docs: weights are not released; "Jev is not fine-tuned or LoRA-adapted with customer data"; same weights for every account; customer requests are not training data (vendor claim, `models.md`). Gate 1 persists a rationale: output contract `{"decision": 0 or 1, "rationale": "..."}` (`.dev/decision-logs/prompt-caching/T7-bis-call2-breakpoint-move.md`). Docs: "System One models do not write replies, produce code, or generate explanations of their reasoning."
Why it matters: The cheap-call story is an argument for putting Jev on the hot path. That path exports the corpus and stops storing `pre_filter_rationale`.
Destination: `.dev/retrospectives/learning/`
Next step:   Keep F1 on `eval/prefilter_v0/` and `eval/github_repo_gate_v0/` JSON only. No `bishop.db`, no compose service, no `TYPESAFE_API_KEY` in the pipeline env.
Status:      unrouted

### F4
Type:        concept
Claim:       The contract is a typed decision plus a probability; schema match, calibration, and accuracy are three different properties.
Evidence:    Launch: "While Jev gives up string generation, it’s optimized for structured outputs and can’t hallucinate." Same post, type-error plot: "Our number is not empirical. Schema matching is guaranteed, thus we can confidently add 0% into the plots." Docs: "Calibration is measured across groups of predictions; it does not guarantee that an individual answer is correct." `confidence` "is a statistic computed from the probability distribution"; "Noul answers don't carry one."
Why it matters: Bishop's gate already stores a binary decision. The new part is a closed output space and a separate probability, and the launch uses "can't hallucinate" for the closed space.
Destination: `.dev/retrospectives/learning/`
Next step:   File a short learning note with those three sentences if the operator wants the distinction somewhere stickier than this report.
Status:      unrouted

### F5
Type:        concept
Claim:       An attention must-look flag fits a noul; the digest sentence does not.
Evidence:    Attention-pass layers table: "Must-look / skip / short digest" and "Do not fold digest text into Call 1/2 fields" (`.dev/decision-logs/ops/attention-pass-consumer.md`). Same doc: build order starts with a hand pass, "Experiment before mill." Docs: the model does not generate explanations or replies.
Why it matters: When that parked idea is picked up, the flag and the sentence are different tools. Jev is eligible only for the flag, and only after hand labels exist.
Destination: `.dev/retrospectives/learning/` (theme: attention-pass consumer)
Next step:   When the hand-pass rubric is written, record must-look as a boolean and the digest as prose in two fields. Do not call Jev for this until that labeled set exists.
Status:      unrouted

### F6
Type:        reference-only
Claim:       RLCD is a named objective with no published reward, data, or architecture.
Evidence:    Primer one-liner: "Reinforcement learning for calibrated decisions trains TypeSafe to return decisions and calibrated probabilities instead of generated text." `notes/vendor-launch.md` records no reward function, scoring rule, dataset, or hyperparameters on the primer, models, or jaggedness pages. arXiv search claim on systemonemodels.org (zero papers as of 2026-09-20) was not re-run here; the first-party gap is enough.
Why it matters: There is nothing to reimplement locally. The product is the API.
Destination: —
Next step:   Cite the docs URL if RLCD comes up again. Do not schedule a reproduction.
Status:      unrouted

### F7
Type:        experiment-hypothesis
Claim:       Run the shadow score in the shape of the crash-narrative audit: pin the id, record the id returned, refit only on Bishop labels.
Evidence:    arXiv 2609.24052, full HTML: model row "jev-1.13.0 (195,857)"; "All runs use the pinned model identifier, and the identifier returned by the service is recorded on every call"; 27 questions "in one call"; human-reference n = 2,416, F1 0.908, raw ECE 0.0231, Platt out-of-fold ECE 0.0069; "its probabilities are not calibrated"; "The recalibration maps were fitted on 3 coders’ judgment of Texas narratives and should be refitted rather than transported." Measured cost "$0.154 per thousand narratives." Notes: `notes/arxiv-2609-24052.md`.
Why it matters: This is the largest ground-truth audit in the index, and Bishop scored it 0.38. The first scout never read it. It is the protocol for F1, on a different domain.
Destination: this folder, beside F1
Next step:   F1's script writes the returned model id, the raw ECE, and a refit fit only on a held-out half of `eval/prefilter_v0/`.
Status:      unrouted

### F8
Type:        risk-or-antipattern
Claim:       A relevance judgment is not one of the workloads JEV-as-a-Judge marks safe to accept.
Evidence:    arXiv 2609.26550: "Treat confidence as an escalation signal, not a certificate; check it on style-adversarial pairs and validate any temperature per workload." "No single temperature fits; each workload needs its own validation." Reference-free prose: "mean maximum probabilities of 0.90, 0.95, and 0.96, a JEV Brier score of 0.815 with error-detection AUROC 0.518" and "no threshold helps." "Specialized professional domains are untested." Operating envelope marks ordinary preference and evidence-grounded factuality as "Use JEV," and reference-free prose as "Not supported." Notes: `notes/arxiv-2609-26550.md`.
Why it matters: Bishop's gate is a taste judgment against a profile, not a pairwise preference and not a check that a passage supports a claim. Their safe envelope does not include it.
Destination: this folder
Next step:   F1 still runs, and a pass on gold is what would put this workload in the envelope. Do not skip the gold slice because preference-judging worked.
Status:      unrouted

### F9
Type:        risk-or-antipattern
Claim:       Cite the paper notes here, not the indexed search snippet, when the number is load-bearing.
Evidence:    Live `GET /search` on 2026-09-27 returned, for `arxiv:2609.26550`, a summary beginning "JEV achieves 99% of GPT-4's accuracy". The paper's conclusion is "keep 99% of GPT-6’s accuracy at 57% of its fee" for a cascade that escalates the unsure cases; the abstract's "99% of the comparator’s accuracy" names that cascade, and the notes record no "99% of GPT-4" sentence. For `arxiv:2609.30186` the snippet leads with 79% AndroidWorld success; Table 1 is 0.79 Jev-Mobile, 0.78 SeeAct-V, 0.84 step-wise VLM.
Why it matters: The index is how these papers were found. The snippet dropped the cascade and the stronger baseline.
Destination: this folder
Next step:   Any later citation of these three ids uses `notes/arxiv-2609-26550.md`, `notes/arxiv-2609-24052.md`, and `notes/arxiv-2609-30186.md`. The search-behavior rule is filed at `.dev/decision-logs/ops/2026-09-27-search-prompt-shape.md`.
Status:      unrouted

## Declined findings (log)

| ID | Type (pre-gate) | Claim | Gate fired | Note |
|----|------------------|-------|------------|------|
| D1 | pattern | Jev can replace enrichment Call 2 | EG3 | Call 2 stores `relevance_reason` and `value_rationale` (`.dev/sqlite.md`). Docs: the model does not generate explanations. |
| D2 | pattern | Add Jev as a second live LLM pre-filter in front of Haiku | EG1 | `harvest-pool-next.md`: "A second LLM pre-pre-filter. Mechanical drops wait until after we can see the pool." |
| D3 | pattern | Jev can write the attention-pass digest | EG3 | Digest is prose. System One "do not write replies" (docs `concepts/system-one.md`). The boolean half is F5. |
| D4 | tool-or-library | Budget Jev at $0.42 per million input tokens | EG3 | That figure is only on `jevtypesafeai.com` (unofficial mirror). First-party blog and `docs.typesafe.ai/models.md` both say $0.042/MTok, output free. |
| D5 | concept | Study 2005 Justification Endorsed Voting for Bishop | EG4 | Different acronym (Ontañón, multi-agent CBR). Current papers and posts mean TypeSafe's Jev. |
| D6 | pattern | Question rewrites will fix thin manifests | EG3 | arXiv 2609.29429: targeted wording adds +0.006 AUROC [−0.004, +0.015] on alignment benchmarks, and label-key fields in the state inflate AUROC. That is not a result about LessWrong titles. Shape law already parks an ambiguous title (`config/source-notes/lesswrong.md`). |
| D7 | concept | Budget latency at the vendor 70ms floor | EG3 | Vendor band is "70ms-500ms" measured "from our laptops on the West Coast." Venkat median 0.34 s; mahi-pas median 406 ms; the paper's median call is 0.31 s. |
| D8 | risk-or-antipattern | Best-of-N monitor economics matter on the ingest path | EG4 | Venkat's result is about an attacker who can resubmit code to a suspicion monitor. Bishop ingest has no such adversary loop. |
| D9 | risk-or-antipattern | Date and counting jaggedness makes Jev unfit for the paper corpus | EG3 | Jaggedness lists math, dates-as-text, and large irrelevant state as weak spots (`model-jaggedness/jev-1.13.md`). Gate 1's state is title + abstract, which avoids the long-state failure, and the gate question is a relevance judgment, not a date comparison. F1 keeps state to title + abstract so this weakness is not the thing under test. |
| D10 | pattern | Jev-Mobile's AndroidWorld success is evidence for a Bishop document gate | EG3 | arXiv 2609.30186 evaluates multi-step GUI control. "The output space is constrained, but correctness is not guaranteed." Full-task success is 0.79 versus 0.84 for a step-wise VLM. §8: AndroidWorld only, and no ablation that replaces Jev with a small VLM. No title+abstract task. |
| D11 | pattern | Reuse τ=0.9 or the Texas Platt map as Bishop's cutoff | EG3 | 2609.26550: "No single temperature fits; each workload needs its own validation." 2609.24052: recalibration maps "should be refitted rather than transported." |

## Synthesis

Jev is a closed decision API (early access opened 2026-09-15, shipping weights `jev-1.13.0`): one text state, many typed questions, probabilities back, no prose. The single finding worth acting on is still a shadow score against `eval/prefilter_v0/`. The amendment adds the shape of that run from the crash-narrative audit already in the index: pin `jev-1.13.0`, record the id the service returns, report raw calibration error, and refit only on Bishop labels. JEV-as-a-Judge does not put a profile-taste question in its "Use JEV" envelope, and its 99% figure is a cascade against GPT-6, not a standalone tie with GPT-4. Jev-Mobile is a GUI executor (0.79 vs 0.84 for a step-wise VLM) and is not evidence about the gate. A live swap would still send the corpus off-machine and stop writing `pre_filter_rationale`.
