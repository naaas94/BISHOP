# LW practitioner posts — Jev as monitor (Phase 1 raw notes)

Slice: practitioner posts about using Jev as a monitor. No verdicts.

---

## Post 1 — Venkat T — APPS backdoor trusted monitor

**Locator:** https://www.lesswrong.com/posts/d7pQicW8EhpPBDRqz/a-non-generative-model-as-a-trusted-monitor-for-ai-control  
**Author:** Venkat T  
**Date:** 2026-09-18 16:06:48Z  
**Source on disk:** `agent-tools/e6fb8eb3-c605-4c41-9710-53ae82815a4c.txt`

### Task

- Pilot: use TypeSafe **Jev** as **trusted monitor** in **ControlArena APPS backdoor** setting (untrusted model writes Python CP solutions; some backdoored — pass tests, wrong on secret input).
- Monitor = single **Noul** (`P(yes)` = suspicion); state `{"problem", "code"}` ~1,050 tokens; model **jev-1.13.0** pinned.
- Operating metric: **TPR at fixed FPR** (1%, 2%, 5%); main line is **2% FPR** (audit budget).
- Author explicitly **did not run an actual LLM baseline** (time/$5 credit/15h constraint); comparisons to published numbers are **positioning only**.

### Data / baselines

- **Positive:** verified backdoors — `eugenekoran/apps-control-arena-high-quality`, ControlArena `RoganInglis/apps-control-arena`.
- **Honest H1:** LLM-written accurate solutions from `RoganInglis/control-tax` (matched problems).
- **Honest H2:** human APPS solutions from Control Tax paper.
- Splits: 150 dev; test **600 backdoors / 600 H1 / 600 H2**.
- **Confound baseline:** logistic regression on **code length + line count** (AUROC ~0.674 both honest sets).
- **Published comparison (not re-measured):** Control Tax reports **o3-mini with CoT AUROC 0.92–0.96** on related honest set; author positions Jev **0.970** on H2 inside/above that band.

### Metrics quoted — discrimination (Exp 1)

| Signal | Honest set | AUROC [95% CI] | TPR@1% | TPR@2% | TPR@5% |
|--------|------------|----------------|--------|--------|--------|
| Jev backdoor Noul | H1 LLM | 0.976 [0.968, 0.985] | 0.878 | 0.895 | 0.928 |
| Jev | H2 human | 0.970 [0.959, 0.979] | 0.853 | 0.878 | 0.917 |
| Log-reg size | H1/H2 | 0.674 | — | — | — |

- TL;DR: **90% of backdoors at 2% FPR**; single question **AUROC 0.976** vs LLM-written honest.
- **~$0.04 per thousand submissions** (TL;DR); body: **~$0.044 per thousand submissions** vs dollars for CoT monitor; pricing cite **$0.042 per million input tokens**, outputs free.
- **0.34 s median latency** (per submission, single question).

### Metrics quoted — consistency (Exp 2)

- 200 rows × 5 fresh calls (uid anti-cache trick).
- **std_dev mean = 0.008**; p90 = 0.019; largest range 0.100.
- **jaccard@10% = 0.924** (top-10% audit set overlap across repeats); jaccard@5% = 0.836.
- TL;DR: mean score move **0.008** across re-scores; top-10% flagged set **92%** same (aligns with Jaccard narrative).

### Metrics quoted — attacks (Exp 3)

- Scope 1 (monitor-directed comments): backdoor suspicion **not lowered by more than 0.014** (TL;DR aggregate framing); table shows **0 evasion** for instruct_monitor on backdoors; authority backdoors **3.7% evaded** at 2% budget framing.
- Honest code with “NOTE TO AUTOMATED MONITOR…”: flagged rate **1.3% → 29.0%** (instruct_monitor).
- Scope 2 (justify comments on trigger line): **0 backdoor evasions**; scores on backdoors **increase** (e.g. 0.65 → 0.68 / 0.73).

### Metrics quoted — best-of-N (Exp 4)

- Attacker scores up to **N variants**, submits **minimum** suspicion.
- At **2% audit budget**, catch rate falls when N>1; author: **~one-third get through vs ~one-tenth** if attacker probes before submit (headline 90% assumes attacker doesn’t know monitor).
- Caveat in post: selection hurts **any** thresholded monitor; Jev changes **probe economics** (cheap + stable → informative probes).

### Metrics quoted — structural vs semantic / grounding (Exp 5)

- **Caught at 2% FPR:** structural backdoors **97.3%** (n=415); semantic **71.9%** (n=185).
- Localization (Choice): top-1 trigger body **32.7%**, condition **55.4%**, either **87.5%**, top-3 **96.7%**.
- **Problem removed (code-only):** AUROC drops modestly (e.g. H1 0.976 → 0.964; H2 0.970 → 0.959); author: spec worth **~six points** on TPR@2% for H2 (0.878 → 0.800).

### Metrics quoted — calibration (Exp 6)

- Raw **P(yes)** **under-confident** above ~0.3; **ECE/Brier** discussed via reliability diagram.
- Author inference: **“great ranking and a poor probability”**; summing scores for residual risk estimate **not available** from raw API number.

### Author pre-registered hypotheses — outcomes

| ID | Claim | Outcome (author) |
|----|-------|------------------|
| A | AUROC below frontier reasoning monitor; competitive on FPR-per-dollar | **Too pessimistic** — matches strongest published monitor range at ~**1/100th** cost |
| B | More consistent than LLM verbalized 0–100 | **Not testable without baseline**; **partially falsified**: under-confident above 0.3 → raw score is **ranking not probability** |
| C | Immune to instruction-level attacks; content attacks may work | **Proven** (incl. persuasion on trigger line fails to evade) |
| D | Manipulation text on **honest** code raises suspicion | **Accurate** |

- Author summary: **2 of 4 hypotheses wrong** (“in very interesting ways”).

### Author limitations / caveats (explicit)

- No **measured** LLM baseline; Control Tax / o3-mini comparison **positioning only**.
- Toy: single config, one dataset family, single-file APPS backdoors, **33% prevalence** in test mix (not real queue).
- Best-of-N is a **floor** (independent variants, not adaptive attacker).
- Stable scores → **every probe informative to attacker** (noted as possible downside).
- Auto-clear sweep: aggressive clear at 0.10 → **~4% backdoors** waved through at 1% prevalence scenario (further analysis section).

---

## Post 2 — mahi-pas — CoT / thought-trace harm monitor

**Locator:** https://www.lesswrong.com/posts/GHCNKiFzDYThTELFp/jev-as-a-cot-monitor-6x-faster-and-500x-cheaper  
**Author:** mahi-pas  
**Date:** 2026-09-23 23:59:52Z  
**Retrieved:** 2026-09-27

### Task

- Classify **Chain-of-Thought / thought traces** for **harm score** (not harm class): labels **0** harmless, **0.5** potentially harmful, **1** harmful.
- Dataset: **[ReasoningShield/ReasoningShield-Dataset](https://huggingface.co/datasets/ReasoningShield/ReasoningShield-Dataset)** — **2,200** traces; harm types include child abuse, cybersecurity, deception, economic harm, hate, political, prohibited items, rights, sex, violence.
- Models asked to **quantify harm score** only; breakdown by harm type/class shown post hoc.

### Baselines

- **Claude Sonnet 5**
- **GPT-5.6 Luna**

### Metrics quoted — accuracy / F1

- **Exact-match accuracy** (label ∈ {0, 0.5, 1}): **Jev 71.5%** (1,560/2,182 labeled calls), **Sonnet 71.4%** (1,498/2,097), **Luna 79.4%** (1,649/2,077).
- **Macro F1:** Jev **58.2%**, Sonnet **56.4%**, Luna **70.3%**.

### Metrics quoted — latency

- **Mean classification time:** Jev **542 ms**; Sonnet **3,348 ms**; Luna **2,007 ms**.
- Title/section claim: **3.7× faster than Luna**, **>6× faster than Sonnet**.
- Table also: **median ms** — Jev **406**, Sonnet **1,950**, Luna **1,085**.

### Metrics quoted — cost

- **USD / 1,000 classifications:** Jev **$0.056**; Luna **$0.23**; Sonnet **$3.17**.
- **USD for 2,200 run:** Jev **$0.12**; Luna **$0.51**; Sonnet **$6.97**.
- Title: **500× cheaper**; body: **566× cheaper than Sonnet**, **41× cheaper than Luna**.

### Author performance caveats (not formal hypotheses table)

- **Harmful (score 1) traces:** Jev **worse than Sonnet and Luna** at identifying truly harmful traces; author: **Sonnet still better than Jev** because catching harm > reducing false positives on safe/potential.
- **By safety level F1:** Jev beats Sonnet on Safe and Potentially Harmful vs Luna; loses to Luna on those; **underperforms both on Harmful**.
- **By risk category:** Jev **only beats** Sonnet/Luna on **Safe**; Luna wins **every other category**; Jev beats Sonnet on subset (Deception & Misinformation, Economic Harm, Political Risks, Rights Violation) but **worse on** Child Abuse, Cybersecurity, Hate & Toxicity, Prohibited Items, Sex, Violence.
- **Conclusion reservations:** CoT monitoring concern — **[GPT-6 better at evading monitors](https://openai.com/index/safety-overview-gpt-6-astra/)**; Jev may stop **more obvious** harm only.
- Positive forward look: **finetuned Jev-style** model for CoT monitoring “could be very effective at scale.”

### Repo

- https://github.com/mahi-pas/Jev-CoT-Monitoring

---

## Cross-post contrast (observation only)

- **Venkat:** control / **code backdoor** ranking at low FPR; emphasizes **AUROC**, audit budget, attack robustness, **calibration as ranking-not-probability**, best-of-N economics.
- **mahi-pas:** **thought-trace harm** tri-class exact match; emphasizes **latency and $/1k** vs Sonnet/Luna; **no AUROC** reported; accuracy ceiling set by Luna **79.4%**.
