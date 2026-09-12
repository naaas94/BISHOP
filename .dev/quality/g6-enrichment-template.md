# G6 Enrichment Quality Sampling

Manual 10-entry checklist for enrichment Call 1 (`challenge_hooks`) and Call 2 (`value_rationale`) against the pinned enrichment profile `config/profiles/professional_v1.0.0.yaml`.

## Protocol

1. Select 10 entries that passed pre-filter from a recent enrichment batch (mix of `core` and `peripheral` tiers if available).
2. Record each entry's `source_id`, model-produced `challenge_hooks`, and `value_rationale`.
3. Judge whether hooks are problem-shaped (2–4 practitioner search framings) and whether `value_rationale` explains professional value.
4. Set `hooks_acceptable` and `rationale_acceptable` to `true` or `false` per entry.
5. When all ten entries are filled and judged, run:
   `BISHOP_G6_MANUAL=1 ./scripts/run-g6-enrichment-sampling.sh`

Gate passes when every entry has both acceptance flags set to `true`. Profile YAML iteration is out of scope unless sampling fails — prefilter pin `professional_v1.2.0.yaml` is already calibrated separately.

Reviewed 2026-09-10 from live `INDEXED` rows in `C:/Users/Ale/bishop_data/sqlite/bishop.db` (score-stratified 10; `pre_filter_tier` unset). Judgments from the G6 enrichment review canvas. All ten `value_rationale` flags accepted. Three `challenge_hooks` rejects: `arxiv:2606.09483`, `arxiv:2608.14509`, `arxiv:2606.27330`. Manual pytest gate will fail until those slots pass or are replaced.

```json
{
  "gate": "g6_enrichment",
  "version": 1,
  "profile_under_test": "config/profiles/professional_v1.0.0.yaml",
  "required_entry_count": 10,
  "entries": [
    {
      "slot": 1,
      "source_id": "arxiv:2607.19592",
      "challenge_hooks": [
        "How to make self-improving agent systems cost-effective and maintainable without coupling improvements to specific agent designs or task distributions",
        "Building reusable, transferable knowledge artifacts that persist across multiple agents and generalize to held-out tasks and different LLM families",
        "Reconciling conflicting evidence and competing hypotheses from multiple agent attempts into actionable, scoped guidance through structured discussion",
        "Evaluating whether knowledge curation outperforms prompt optimization and agent-centric self-improvement across heterogeneous reasoning, coding, and terminal benchmarks"
      ],
      "value_rationale": "Provides a concrete alternative to stateless agent patterns, showing how shared knowledge bases enable both improved solve rates and cost efficiency. Immediately actionable for designing scalable multi-agent workflows where knowledge distillation and curation reduce per-task redundancy and increase robustness across model families.",
      "hooks_acceptable": true,
      "rationale_acceptable": true,
      "reviewer_notes": ""
    },
    {
      "slot": 2,
      "source_id": "arxiv:2606.30704",
      "challenge_hooks": [
        "How to avoid expensive re-optimization when deploying workflows to new task-operator combinations?",
        "How to learn generalizable workflow patterns that reduce redundant per-instance generation while maintaining adaptation to untrained domains?",
        "How can LLMs synthesize reusable task-level workflow templates instead of instance-specific solutions for robust deployment?",
        "How to efficiently scale workflow generation across diverse problem domains without manual expert design?"
      ],
      "value_rationale": "Provides actionable insights into how to train LLMs to autonomously compose workflows from operator sets—applicable to building generalizable agent systems that adapt to new domains. The two-stage optimization (SFT + RLVR) and zero-shot transfer mechanics could inform architecture decisions for multi-domain agentic platforms, though production latency/cost implications of the training pipeline warrant evaluation.",
      "hooks_acceptable": true,
      "rationale_acceptable": true,
      "reviewer_notes": ""
    },
    {
      "slot": 3,
      "source_id": "arxiv:2606.23112",
      "challenge_hooks": [
        "How to structure tool selection in multi-turn agents without explicit supervision across large, overlapping API surfaces?",
        "How to construct reliable preference pairs from agent trajectories without train-deployment context mismatch?",
        "How to diagnose and address step-budget exhaustion vs. action-accuracy bottlenecks in conversational agent deployments?",
        "How to align preference learning objectives with inference-time orchestration guidance in self-improving agents?"
      ],
      "value_rationale": "Provides actionable patterns for improving agent reliability through ToolGraph architecture and divergence-point preference optimization, both applicable to production agentic systems. The alignment of training context with deployment scenarios solves a critical gap in agent reproducibility and performance.",
      "hooks_acceptable": true,
      "rationale_acceptable": true,
      "reviewer_notes": ""
    },
    {
      "slot": 4,
      "source_id": "arxiv:2607.21433",
      "challenge_hooks": [
        "How to detect when a reasoning model will fail to converge before wasting full token budget on doomed generations",
        "Why do some mathematical problems cause reasoning models to enter infinite loops despite longer thinking budgets not helping on simpler tasks",
        "How to optimize inference costs by identifying and early-exiting non-convergent reasoning chains using mechanistic signals"
      ],
      "value_rationale": "Directly applicable to building robust agentic workflows: understanding token budget saturation informs prompt engineering and timeout strategies, while convergence detection enables graceful degradation and cost optimization. However, the mechanistic probe methodology (AUC 0.608 is weak signal) requires validation before integration into production monitoring.",
      "hooks_acceptable": true,
      "rationale_acceptable": true,
      "reviewer_notes": ""
    },
    {
      "slot": 5,
      "source_id": "arxiv:2608.13760",
      "challenge_hooks": [
        "How to measure which reasoning behaviors are actually predictive of model correctness versus just appearing more frequently?",
        "Why do thinking models amplify self-correction and uncertainty acknowledgment yet these behaviors weakly correlate with correct answers?",
        "How to design process-level training objectives that reward calibrated grounding rather than surface-level reasoning trace elaboration?",
        "What mechanisms explain when extended reasoning traces help (recovery from failures) versus hurt (knowledge-heavy tasks with logical shortcuts)?"
      ],
      "value_rationale": "The Amplification-Lift Gap and Behavioral Lift metric could inform LLM-as-judge design and evaluation strategies for agentic systems, particularly around understanding which model behaviors actually correlate with correctness in production contexts. However, the work is most valuable for evaluation teams rather than builders of retrieval, agentic, or document intelligence systems.",
      "hooks_acceptable": true,
      "rationale_acceptable": true,
      "reviewer_notes": ""
    },
    {
      "slot": 6,
      "source_id": "arxiv:2606.09483",
      "challenge_hooks": [
        "How to track and retrieve user belief evolution over long sessions when embedding similarity collapses intermediate states and causal links",
        "Detecting latent cross-domain behavioral patterns that are behaviorally similar but semantically distant across unrelated life domains",
        "Separating fast online memory encoding from slow offline abstraction in agent systems to enable implicit personalization reasoning"
      ],
      "value_rationale": "The hierarchical memory organization (raw inputs → atomic facts → belief trajectories → schemas) and asynchronous pattern detection offer concrete design patterns for stateful agent systems; the doubly-linked supersedes chains for belief revision provide a testable approach to tracking agent reasoning evolution across interactions, valuable for observability and multi-turn agent reliability.",
      "hooks_acceptable": false,
      "rationale_acceptable": true,
      "reviewer_notes": "I think the hooks can be more direct when looking at the value ratioale + what the model relevance reason is saying as well - also there are lot of words that it took me a bit to uderstand what I was reading"
    },
    {
      "slot": 7,
      "source_id": "arxiv:2608.13567",
      "challenge_hooks": [
        "How can we identify and visualize functional modules within LLMs across different cognitive tasks?",
        "Do neural networks naturally develop human-like modular organization under standard training, or does it require architectural priors?",
        "Can circuit analysis predict which neuron populations will be recruited for novel reasoning tasks?"
      ],
      "value_rationale": "While understanding LLM internals has peripheral value for debugging unexpected behaviors in production systems, circuit analysis doesn't inform concrete engineering decisions around retrieval strategy, agent design, or inference optimization that ship within a 6-month horizon.",
      "hooks_acceptable": true,
      "rationale_acceptable": true,
      "reviewer_notes": ""
    },
    {
      "slot": 8,
      "source_id": "arxiv:2608.14509",
      "challenge_hooks": [
        "How to combine predictions from multiple unreliable sources without letting high-volume weak evidence overwhelm sparse strong evidence",
        "Why summing unnormalized weights and thresholding produces systematically biased decisions as source count varies",
        "How to maintain provenance and enable abstention in multi-source decision systems that currently concatenate evidence into monolithic prompts",
        "Designing calibrated aggregation rules that work across different domain readers while separating domain-neutral logic from domain-specific estimation"
      ],
      "value_rationale": "The evidence tuple interface and separation-of-concerns principle could inform multi-evidence fusion in agent decision systems, and log-likelihood-ratio pooling has theoretical merit for aggregating scores in reranking pipelines. However, the contribution is primarily statistical/methodological rather than addressing production concerns like latency, reliability, or architectural patterns that drive shipping decisions.",
      "hooks_acceptable": false,
      "rationale_acceptable": true,
      "reviewer_notes": ""
    },
    {
      "slot": 9,
      "source_id": "arxiv:2606.27330",
      "challenge_hooks": [
        "How to improve task planning capabilities of small MLLMs for cross-website GUI automation without access to large commercial models",
        "Whether atomic-level task training effectively generalizes to complex high-level planning, and how to properly measure compositional generalization",
        "How to align exploration trajectories with task definitions and extract quality training signals from autonomous agent interactions"
      ],
      "value_rationale": "The hindsight experience replay and task decomposition patterns could inform agentic workflow design, but the GUI-specific environment exploration and visual grounding are orthogonal to the primary domains of RAG, document extraction, and LLM orchestration.",
      "hooks_acceptable": false,
      "rationale_acceptable": true,
      "reviewer_notes": ""
    },
    {
      "slot": 10,
      "source_id": "arxiv:2607.04425",
      "challenge_hooks": [
        "How to train unified GUI agents across heterogeneous platforms without blurring platform-specific interaction conventions?",
        "How to integrate specialized desktop and mobile expertise into a single policy while preserving behavioral anchors for each platform?",
        "How to balance cross-platform knowledge transfer with native interaction pattern retention during continuous policy optimization?",
        "How to collect and validate high-quality executable trajectories spanning multiple GUI environments at scale?"
      ],
      "value_rationale": "The multi-teacher distillation methodology could offer minor insights for agent ensemble patterns, but the focus on platform-specific UI conventions and GUI trajectory learning is orthogonal to the core production concerns of retrieval systems, LLM inference, and structured extraction pipelines that define this profile's primary work.",
      "hooks_acceptable": true,
      "rationale_acceptable": true,
      "reviewer_notes": ""
    }
  ]
}
```
