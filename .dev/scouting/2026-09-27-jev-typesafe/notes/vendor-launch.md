# Vendor launch — TypeSafe first-party (raw notes)

## https://typesafe.ai/blog/introducing-system-one-models-and-jev — opening

- TypeSafe announces “our first System One Model: a new class of frontier models built to make fast, structured decisions that software can use directly.”
- Stack described as: “a new model architecture, parallel sampler for maximum efficiency, and training method we call Reinforcement Learning for Calibrated Decisions (RLCD).”
- Jev: “available today in early access”; “achieves similar levels of intelligence on System One tasks compared to existing LLMs, while being two orders of magnitude faster and more efficient.”
- Verbatim: “While Jev gives up string generation, it’s optimized for structured outputs and can’t hallucinate.”
- Verbatim: “Think of Jev as a frontier-intelligence function call: unstructured state in, typed probabilistic decisions out.”

## Same URL — “Frontiers, Old and New” (comparison table)

- RLCD optimizes for: “Calibrated decisions: answers with epistemically honest probabilities on System One tasks.”
- System One outputs: “Type-safe structured values. Possible outputs and structure are defined in advance. The model never makes type errors. All answers are accompanied with calibrated probabilities and confidence scores.”
- Sampling: “Parallel. Generates all outputs in a single query.”
- Pricing (Jev row): “Input tokens: $0.042 / MTok ($ 42 per billion tokens). Output tokens: FREE (too cheap to meter).”
- Speed (Jev row): “End-to-end response time is 70ms-500ms for TypeSafe. This can range from 40x-200x faster for the same levels of frontier intelligence for System One shaped queries.”
- Confidence (Jev row): “Always communicates confidence and uncertainty with every output. Calibrated: higher confidence means higher accuracy.”

## Same URL — “Evidence / Technical Results”

- Verifiable claims listed: speed per call, cost per call, “No type errors: … it is mathematically impossible.”
- Cost nuance: “We can’t prove it isn’t subsidized; we’ll need the long-term to prove the sustainability of our pricing (which we expect to go down, not up).”
- Evals “generally run from our laptops on the West Coast.”

## Same URL — “Side-by-side demonstration” / Nuance

- Reference model for demo: “GPT-5.6 Terra with default reasoning … the most comparable at intelligence to Jev on average.”
- Demo query “highly simplified”; shorter input “paints our model in an advantageous light.”

## Same URL — “Workflow evals”

- Measurement: fixed “workflow” (compute graph in code); reference is not ground-truth labels — “use the predictions of the largest, smartest, and most expensive external models as reference probabilities.”
- Verbatim: “every model gets the same workflow. We test how they compare to the average of the smartest models (in this case, Astra and Fable).”
- Reference models named: “the average of GPT-6 Astra and Fable 5.1 as the reference answer.”
- LLM baseline uses “System One LLM wrapper, which constrains LLMs to output structured decisions compatible with our API.”
- Nuance: homepage “193.6x faster, 444.6x cheaper” claims “come from” these workflow evals; “on the higher end of real world gains.”
- Workflows “were not deliberately chosen … and are not in our training distribution” but “made by individuals on our model capabilities team, so some bias could exist.”
- Details pointed to: “workflow evals site” (evals.typesafe.ai — not fetched in this pass).

## Same URL — “Hallucination and Type-safety” / Nuance

- LLM hallucination/type-error plot numbers: “from OpenRouter.”
- Verbatim on Jev/type plot: “Our number is not empirical. Schema matching is guaranteed, thus we can confidently add 0% into the plots.”

## Same URL — “Wikiracing” / Nuance

- “Jev supports a cardinality up to 255.” Higher cardinality uses “a 2 stage-system of scoring independently then making an explicit choice.”

## Same URL — “We Give A FAQ”

- Names: Kahneman System 1/2; Jevons naming for Jev; “System 1 thinking has also implied error-prone” — reliability argument “we will get into in the future.”
- FAQ questions listed without body text in fetched page: “Why was a new training algorithm needed?”, “What use cases is Jev good for?”, “Is Jev just a smaller LLM?”, “How does Jev perform against public benchmarks?”, “Where does our training data come from?”, “These results are kinda crazy - how is it possible?” — answers not present in retrieved HTML.

## https://docs.typesafe.ai/ (Introduction)

- Verbatim role: “Jev is TypeSafe's flagship model and the first System One model. System One models are built to make fast, structured decisions that software can use directly.”
- Primitives table: Choice → `choice`, `probabilities`, `confidence`; Score → `score`, `probabilities`, `confidence`; Noul → `noul` (0–1).
- “Every question is evaluated in parallel and in isolation against the same state in one go.”

## https://docs.typesafe.ai/concepts/system-one.md — “System One”

- “System One models are trained for calibrated decisions: their probabilities are optimized against outcomes to reflect uncertainty. Calibration is measured across groups of predictions; it does not guarantee that an individual answer is correct.”
- “System One models do not write replies, produce code, or generate explanations of their reasoning.”
- Input: “Jev currently accepts text input only”; “Images, audio, and video are not supported (yet).”
- API: `POST /v1/systemone`; examples use `jev-latest`.

## https://docs.typesafe.ai/introduction/machine-learning-primer.md — RLCD

- Verbatim one-liner: “Reinforcement learning for calibrated decisions trains TypeSafe to return decisions and calibrated probabilities instead of generated text.”
- RLCD contract: model “does not generate text”; “returns decisions and probabilities”; “Higher probability should correspond to a greater chance that the answer is correct.”
- Calibration definition (group property): outcomes at `0.2` ~20%, `0.8` ~80%, `1.0` 100%; “These rates describe groups of predictions, not a guarantee about any single answer.”
- RLHF context: “RLHF was used to train InstructGPT and ChatGPT and was co-invented by Diogo Almeida, cofounder of TypeSafe.”
- Verbatim contrast: “An output can be compelling to a person without being reliable enough for unattended automation. Human preference and machine trustworthiness are different optimization targets.”
- No reward function, scoring rule, dataset, architecture diagram, or training hyperparameters on this page.

## https://docs.typesafe.ai/confidence.md — “Confidence”

- Verbatim: “`confidence` is a statistic computed from the probability distribution the answer already gives you.”
- “Noul answers don't carry one.”
- Worked example uses thresholds `0.5` (route to human) and `0.9` (high-stakes action) — “The correct threshold values depend on your domain and the performance of the model for your use case.”

## https://docs.typesafe.ai/models.md — pricing, limits, training claim

- Jev 1.13 ID: `jev-1.13.0`; price “$42 / $0.042” per Btok/Mtok; “Charged per input token. Output tokens are free.”
- Rate limits (current): “250,000 tokens per second / 1,200 requests per minute”; “can change without notice.”
- Context: “64k tokens per request; 32k tokens for `state` plus the longest question.”
- Verbatim training: “Jev is not fine-tuned or LoRA-adapted with customer data. It is trained with RLCD to return calibrated decisions, and the same weights serve every account.”
- Aliases: `jev-latest` and `jev-preview` → `jev-1.13.0`.
- Data: “Jev is not trained on customer requests or responses.”

## https://docs.typesafe.ai/model-jaggedness/jev-1.13.md — measured limitations / calibration scope

- “`jev-1.13` is fast, calibrated, and good at common-sense judgment but it is not perfect.”
- Weak at: literal reading, math/counting, dates as text, indirection, large irrelevant state, adversarial content, contradictory criteria, cross-question arithmetic identities, text generation.
- Worked example — complementary Nouls need not sum to 1: refund `0.72`, not_refund `0.47`, sum `1.19`; “There are many reasons that `P(noul)` and `1 - P(not noul)` may not be directly comparable.”
- Score levels: “weak in numerical calibration” for exact magnitude between levels.

## Explicitly not published (first-party only)

- RLCD: name + optimization target (calibrated decisions / probabilities) published; no paper, reward function, proper scoring rule, synthetic-data pipeline, training code, step counts, or task-family calibration metrics in launch post or docs primer/models/jaggedness pages read here.
- FAQ bodies on training data, benchmarks, “smaller LLM”, and “how is it possible” not available in fetched launch HTML.
- Empirical calibration curves / ECE for Jev: not in docs pages above (jaggedness discusses behavior; models page does not publish calibration numbers).
- Third-party pointer only (not first-party): https://systemonemodels.org/guides/rlcd-explained/ aggregates that TechCrunch (18 Sep 2026) quotes Almeida on synthetic-only training and alternate preposition “from calibrated decisions” — not verified against TypeSafe first-party text in this pass.

## URL fetch failures (wrong paths; content retrieved via llms.txt paths)

- 404: `https://docs.typesafe.ai/guides/machine-learning-primer`
- 404: `https://docs.typesafe.ai/guides/confidence`
- 404: `https://docs.typesafe.ai/models/jev-1-13/jaggedness`
- 404: `https://docs.typesafe.ai/guides/ai-primer`

Successful doc equivalents used: `introduction/machine-learning-primer.md`, `confidence.md`, `model-jaggedness/jev-1.13.md`, `concepts/system-one.md`, `models.md`.
