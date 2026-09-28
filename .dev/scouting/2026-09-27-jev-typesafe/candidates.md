# Candidates — Jev (TypeSafe) — unclassified

One sentence each. No type, gate, or destination.

1. Jev takes one text state and returns typed decisions (choice, score, or noul) with probabilities, in one parallel call, and does not generate prose; a schema match is guaranteed by the output space.
2. RLCD is a published training objective (stated probabilities should match how often the answer is right, across a group) without a published reward, dataset, or architecture.
3. Jev's stated probability is a ranking to bin on your own labels before any threshold, because independent measurements do not show a calibration advantage that survives question form, and the vendor's workflow scores are agreement with other models.
4. A pinned `jev-1.13.0` noul can be shadow-scored on Bishop's frozen public labels (`eval/prefilter_v0/`, and optionally `eval/github_repo_gate_v0/`) with the real rubric in the question and title+abstract as state, before any pipeline change.
5. Jev can replace enrichment Call 2.
6. Jev can be added as a second live LLM pre-filter in front of Haiku.
7. Jev can write the attention-pass digest.
8. A future attention rubric can split a must-look boolean, which fits a noul, from a prose digest, which the model does not emit.
9. Budget Jev at $0.42 per million input tokens.
10. The JEV to study for Bishop is the 2005 Justification Endorsed Voting system.
11. A hot-path Bishop gate would upload each item's title and abstract to a closed TypeSafe API whose weights are not released.
12. Rewriting the question sent to Jev will fix thin sources such as LessWrong title-only manifests.
13. Bishop should budget Jev latency at the vendor's 70ms floor.
14. Best-of-N probing economics from the control-monitor write-ups matter for Bishop's ingest path.
15. Vendor jaggedness on dates, counting, and long irrelevant state makes Jev unfit for Bishop's paper corpus.

## Amendment — Bishop-indexed papers missing from the first pass (2026-09-27)

16. The crash-narrative audit (arXiv 2609.24052) is the template for a Bishop shadow score: pin `jev-1.13.0`, record the model id the service returns, ask the schema in one call, report raw calibration error, and refit only on Bishop labels.
17. JEV-as-a-Judge (arXiv 2609.26550) uses max label probability as an escalation gate only after the threshold is fit on that workload; reference-free prose stays confidently wrong.
18. Jev-Mobile's 79% AndroidWorld success is evidence that a Bishop document gate would work.
19. Reuse the judge paper's τ=0.9 or the crash paper's Platt map as Bishop's cutoff.
20. Bishop's search snippet is a safe citation for those papers' headline numbers.
