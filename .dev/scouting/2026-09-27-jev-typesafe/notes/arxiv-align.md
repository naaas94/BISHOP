# arXiv 2609.29429v1 — "Just Ask Jev" — Phase 1 raw notes (alignment slice)

**Locator:** https://arxiv.org/html/2609.29429v1  
**Captured from:** `agent-tools/5f6c4b31-4d7f-4caf-a692-4c9194578f82.txt`  
**Slice:** abstract, §1 intro, §2–3 method (question vs state, strategy selection), §4 results, §6 limitations (+ ethics/repro where load-bearing)

---

## Authors and affiliations (verbatim from title block)

> Ruoqi Guo Yi Liu Griffith University Griffith University ruoqi.guo@griffithuni.edu.au yi.liu@griffith.edu.au Gelei Deng Yuekang Li Nanyang Technological University UNSW gelei.deng@ntu.edu.sg yuekang.li@unsw.edu.au Lida Zhao Yutao Wu Independent Researcher Deakin University LIDA001@e.ntu.edu.sg oscar.w@deakin.edu.au Simin Chen Ying Zhang George Mason University Wake Forest University schen68@gmu.edu ying.zhang@wfu.edu Leo Yu Zhang Griffith University leo.zhang@griffith.edu.au † † thanks: Corresponding author.

**Vendor vs independent read (observation, not verdict):** No author affiliation lists TypeSafe AI. Paper repeatedly cites TypeSafe as product/docs vendor; study uses TypeSafe’s public API and releases cached responses. Ethics: > "We evaluate a commercial model, Jev, accessed through TypeSafe’s public API (TypeSafe AI, 2026)."

---

## What Jev is (paper’s definition)

- RLCD = reinforcement learning for calibrated decisions (distinct from RL from contrastive distillation per footnote).
- > "Jev, TypeSafe’s RLCD model, answers many binary (Noul), categorical (Choice), and ordinal (Score) questions about one input, the state, in a single call."
- One request: state σ (string or JSON) + questions {q1…qm}; Noul → P(yes|σ,q); Choice/Score → distributions + confidence; all questions share one call.

**Model version used in all runs:**

> "All runs use jev-1.13.0 (TypeSafe AI, 2026)."

Reproducibility adds:

> "All runs resolved to jev-1.13.0. As of 2026-09-20, the API accepts this versioned ID even when the jev-latest alias moves to a newer release (TypeSafe AI, 2026), but the developer states no retention period, so the cached responses, not re-queries, are the reference for every reported number."

---

## What the paper actually measured (task + benchmark)

**Research gap stated:**

> "Whether it detects alignment failures has not been measured."

**Benchmark built:** RLCDAlignBench

- Ten alignment failure types: sycophancy, jailbreaks, deception, prompt injection, hallucination, privacy violation, social bias, reward hacking, concealing uncertainty, power seeking.
- 44 benchmarks, **7,193 detection instances**, five open **2–7B target models** (Qwen3.5-2B, Phi-4-mini, Gemma-2-2B, Llama-3.2-3B, Olmo-3-7B).
- Labels: mostly each benchmark’s reference scorer (20 rule, 24 LLM judge); human labels on StrongREJECT + HarmBench; second-judge labels on AbstentionBench + InstrumentalEval.
- Detection = binary: score s(x)∈[0,1], flag if s(x)≥t.

**Pipeline (Figure 2 / §3):** build state σ → one Jev call with typed questions → combine answers into s(x) → compare to labels Jev never sees in training baselines sense (TF-IDF baseline does see labels in CV).

---

## Method: question vs state split

**Key idea (abstract + §1):**

> "Our key idea is therefore to vary what Jev is asked separately from what it sees: the question’s wording and answer type on one side, the fields of the input on the other."

**State (§3.2):**

- Canonical state = target input + output only (response-level monitor view).
- Scorer verdicts, gold answers, metadata, target internal logprobs **never** enter canonical state (confidence *in* response text can).
- **49 paired contrasts:** add one field at a time; tags deployable vs label-key fields.
- Relational failures: canonical state may lack the reference (user belief, injected instruction, etc.).

**Questions (§3.3):**

- **Generic question:** template + per-benchmark behaviour phrase ⟨b⟩; three answer types (Noul, Choice, Score) on same wording where applicable.
- Readouts: P(yes), E[level]/2, or argmax.
- **Targeted questions:** direct / rubric (reference judge prompt) / decomposition families.
- **Strategy selection:** s(x)=g(a1,…,am) — mean/max/product/difference or logical rules over thresholded answers; **15–40 strategies per benchmark**; full battery = **one request** per benchmark item.

**Anti-inflation protocol (§3.4, §1):**

> "We therefore select questions on one half of the items and score them on the other, so that gains reflect Jev rather than our search."

Split-half: best targeted strategy selected on one half, evaluated on other; **mean of 20 grouped splits**. Primary metric **AUROC**; F1 at t=0.5 and CV threshold; 38 usable benchmarks in aggregates (6 degenerate excluded).

---

## Results headline numbers (verbatim quotes)

**Abstract:**

> "A single generic question reaches a median AUROC of 0.886 zero-shot and beats supervised baselines on most benchmarks."

> "Question wording matters little, while context matters more, mostly through fields that encode the label."

> "Jev matches the reference scorer’s agreement with human labels, surfaces label defects in existing benchmarks, and costs 63× less than LLM-judge scorers."

**Intro (aligned numbers):**

> "The generic question already ranks most failures well zero-shot, with a median AUROC of 0.886 over the 31 benchmarks with a Noul form, above supervised TF-IDF and length baselines on 25."

> "Out of sample, targeted wording adds +0.006 [−0.004, +0.015] AUROC."

> "A pass over the 19 judge-scored benchmarks costs $0.30, 63× less than their judges at list prices."

**§4.1 Overall:**

> "The generic Noul reaches a median AUROC of 0.886 [0.821, 0.952] over the 31 benchmarks that admit it, and the split-half targeted strategy reaches 0.911 [0.860, 0.944] over all 38 (Table 6)."

> "Without seeing any label, the generic Noul exceeds the better of response length and an in-domain TF-IDF logistic regression by a median of +0.132 [+0.057, +0.190] and wins on 25 of 31 benchmarks"

**Calibration caveat (§4.4):**

> "The probabilities rank well but do not transfer as thresholds: the median ECE is 0.168 against a null of 0.074"

> "Its median per-benchmark ECE, however, is 0.168 against 0.074 under perfect calibration"

**Human agreement StrongREJECT (§4.5):**

> "The generic Noul agrees with humans at κ=0.809 and the GPT-4o-mini scorer at 0.811 (difference −0.002 [−0.059, +0.057])"

> "Jev ranks better (AUROC 0.971 vs. 0.929, +0.042 [+0.016, +0.070]"

**Cost / latency (§4.5):**

> "A call carries 11.4 questions on average and returns in a median of 0.31 s."

> "On the 19 benchmarks with an API LLM judge, one Jev pass at list prices costs $0.30 against $18.96 for the judges, 63× less pooled (Appendix H)."

> "with every judge priced at GPT-4o-mini rates and Jev asked only the generic question, Jev is 12× cheaper pooled, with a median of 3.3×."

**Context (§4.3):**

> "Context a deployed monitor would hold helps on 1 of 7 benchmarks"

> "PrivacyLens’s secret list (Shao et al., 2024) is a label key because only leaks of listed secrets are positive" — example gain: "Adding the true answer moves the generic Noul from 0.540 to 0.941 on the official label" (SycophancyEval answer) — paper argues such gains measure label construct.

**Practitioner recipe (§4, conclusion):**

> "a generic question read as a probability, with its threshold fitted on ten labelled items"

> "a threshold fitted on ten labels costs 0.025" (F1 on validated labels context)

---

## Known Jev weaknesses cited (from TypeSafe docs, not new measurement)

§1:

> "the developer lists indirect meaning and adversarial content, both common in these failures, among Jev’s known weaknesses (TypeSafe AI, 2026)."

---

## Limitations (§6 Conclusion — verbatim)

> "Limitations. RLCDAlignBench covers one RLCD model (jev-1.13.0), English benchmarks, 2–7B targets, and mostly scorer labels. Extending it to other detectors, larger targets, and other languages is future work."

Additional caveats from results (not labeled "Limitations" but load-bearing):

- Label quality: 11 validated, 25 unvalidated, audit changed 8; generic Noul scores higher on unvalidated (0.949) than validated (0.872) labels.
- Per-benchmark calibration / threshold transfer poor (ECE, base-rate mismatch).
- Label keys in state inflate AUROC — not deployment-realistic for some benchmarks.
- MACHIAVELLI labels depend on annotations omitted from state (four variants).
- StrongREJECT parity with humans "holds pooled, not per generator" (GPT-3.5 κ gap vs scorer).
- Appendix F: ~25% of confident disagreements classified as Jev errors (rest label/scorer issues).

---

## What was NOT measured (explicit gaps)

- Whether Jev detects alignment failures **before this paper** — paper claims first systematic measurement via RLCDAlignBench.
- Other RLCD models, non-English, larger target LMs, production traffic — listed as future work in limitations.
- Live Anthropic/vendor judge costs beyond list-price comparison in Appendix H (paper uses benchmark judge configs).

---

## Artifacts

Code/data: https://github.com/sumleo/RLCDAlignBench  
Cached Jev responses (probabilities, confidences, latency, tokens) in released package; metrics recomputable offline without API.
