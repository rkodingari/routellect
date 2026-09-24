# Routellect Benchmark Protocol

Status: Proposed at Gate G1

## 1. Purpose and claims

Routellect is evaluated as an advisory system, never as an inference gateway. It recommends a model and configuration; benchmark outcomes are joined to those recommendations from frozen, imported evidence. The product does not call the recommended models.

The preregistered primary question is:

> On a held-out workload, can the advisor retain at least 99% of the strongest fixed-model aggregate quality while reducing estimated inference cost by at least 40%?

Secondary questions measure top-1/top-3 utility, regret, calibration, rare-expert recall, advisor latency, feedback uplift, privacy, and catalog freshness. A dedicated ablation asks whether the local semantic assessor delivers prompt-specific improvement over deterministic-only and content-blind selection after accounting for its latency and resource cost. “Best” claims are prohibited unless the protocol supports them statistically.

## 2. Evaluation modes

| Mode | Purpose | Permitted claim |
|---|---|---|
| Software simulation | Rules, assessor schema/fallback, constraints, edge cases, determinism | Software correctness only |
| Offline replay | Join recommendations to frozen per-prompt model outcomes | Accuracy/cost/latency trade-off for that evidence snapshot |
| Catalog validation | Check prices, capabilities, dates, and provenance | Catalog integrity and freshness |
| Feedback holdout | Test whether private feedback improves future advice | Personalization uplift on unseen, later examples |
| Container performance | Measure advisor startup, memory, throughput, and latency | Performance on named Podman host/configuration |

No live target-model execution occurs inside the application or its benchmark runner. Externally collected results may be imported only with provenance, license, model/configuration identity, collection date, and checksums.

## 3. Evidence and workloads

- Prefer license-compatible slices of LLMRouterBench, RouterEval, RouterBench, and RouteLLM-compatible artifacts where raw outcomes are available.
- Add project-owned deterministic fixtures for privacy, long prompts, code, reasoning, extraction, multilingual input, tool-use requirements, and conflicting constraints.
- Group splits by source and task family to reduce paraphrase or dataset-identity leakage.
- Record source URL, version/hash, license, acquisition date, model/configuration, pricing date, prompt template, split, and transformations.
- Keep imported public benchmark content separate from user feedback. Raw user prompts are not retained by default.

Historical outcomes and prices are always labeled as historical. They are never presented as proof of current provider performance.

## 4. Candidate portfolio

The default shortlist contains three recommendations: primary, economical alternative, and privacy/latency alternative when eligible. The underlying catalog remains deliberately curated.

Portfolio selection uses development data only:

1. Measure each model/configuration’s quality, estimated cost, latency, capability, privacy eligibility, and pairwise error complementarity.
2. Select the smallest pool preserving most attainable oracle gain.
3. Include distinct economy, balanced, frontier, and local/open-weight roles where evidence supports them.
4. Freeze exact model IDs, reasoning effort, context/settings, provider/runner, prices, evidence versions, and dates in the run manifest.

This tests an important research finding: a compact, well-chosen pool can outperform an indiscriminately large pool, while protecting rare specialists.

## 5. Baselines

Every primary report includes:

- Cheapest eligible model/configuration.
- Fastest eligible model/configuration.
- Strongest fixed model selected on validation only.
- Uniform random eligible choice over repeated seeds.
- Deterministic task/constraint rules with assessor Off.
- Content-blind/fixed-tier allocation matched to the hybrid advisor’s model-selection shares.
- Hybrid Auto advisor with the local assessor but no feedback personalization.
- Hybrid Always advisor as a diagnostic upper-overhead ablation.
- Embedding/KNN advisor.
- Calibrated learned advisor without feedback personalization.
- Full uncertainty-aware advisor with feedback personalization.
- Per-prompt oracle as an unattainable upper bound.

All methods receive the same catalog, constraints, evidence snapshot, and split.

## 6. Metrics

### Recommendation utility

- Dataset-native quality and macro-average across task families.
- Quality retention: `advisor_quality / best_fixed_quality`.
- Estimated cost reduction versus best fixed model.
- Top-1 success and top-3 coverage.
- Regret to the eligible per-prompt oracle.
- Worst-family performance and rare-expert recall.
- Constraint-violation count; hard privacy/capability violations must be zero.

### Confidence and ranking

- Brier score or log loss where labels support it.
- Expected calibration error and reliability curves.
- Selective risk versus coverage.
- Ranked-list NDCG and confidence-interval coverage.
- Recommendation stability under harmless prompt paraphrases.

### Hybrid assessor value

- Auto assessor activation rate overall and by task/difficulty slice.
- Incremental recommendation utility and regret reduction versus assessor Off.
- Improvement versus share-matched content-blind/fixed-tier allocation, isolating genuine prompt targeting from route-mix effects.
- Assessor task/difficulty/capability accuracy and calibration.
- Invalid-output, timeout, crash, and deterministic-fallback rates.
- Added p50/p95 latency, peak memory, image-size contribution, and CPU time per activation.
- Privacy-policy monotonicity: assessor suggestions may tighten but never weaken constraints.

### Feedback value

- Cold-start versus personalized utility on a chronological holdout.
- Cost-adjusted success uplift and regret reduction.
- User/model/task support count and uncertainty.
- Pairwise preference agreement when optional comparisons exist.
- Poisoning sensitivity and maximum influence of one feedback record.

### Product performance and privacy

- Advisor response latency p50/p95/p99, startup time, throughput, image size, and peak memory.
- Catalog age, missing provenance, and unsupported-configuration rate.
- Raw-prompt retention count and unintended telemetry disclosure; both must be zero by default.
- Target-provider network calls, credentials requested, reservations, and charges; all must equal zero.

## 7. Statistical protocol

- Freeze the analysis plan before exposing held-out results.
- Use prompt-level paired bootstrap resampling, stratified by task family, with at least 10,000 resamples for final 95% confidence intervals.
- Use paired bootstrap or permutation tests for the primary comparison and Holm correction for secondary comparisons.
- Run stochastic methods with at least five fixed seeds and report between-seed variance.
- Use paired prompt-level ablations with identical catalog/evidence for Off, Auto, Always, and content-blind controls.
- Use chronological feedback splits and group by user/profile so future or cross-user feedback cannot leak into training.
- Report sample counts, exclusions, missing outcomes, and sensitivity analyses.
- Calibrate any LLM-judge-derived evidence against blinded human ratings; prefer deterministic task metrics.

## 8. Success rules

The primary result passes only when both held-out conditions hold:

1. The lower 95% confidence bound for quality retention versus the validation-selected best fixed model is at least `0.99`.
2. The lower 95% confidence bound for estimated cost reduction is at least `0.40`.

Separate release invariants must also pass: zero target-model calls, zero hard-constraint violations, no default raw-prompt retention, and reproducible recommendations from a frozen manifest.

Auto mode becomes the product default only if its held-out prompt-specific utility is statistically better than both assessor Off and the share-matched content-blind control, while meeting the approved latency/memory/privacy bounds. If not, the hybrid capability ships available but defaults to Off until a candidate passes.

A “best benchmark” claim additionally requires a statistically supported Pareto improvement over every implemented non-oracle baseline under identical evidence. Otherwise, the report must state the actual result and failure slices.

## 9. Anti-gaming and bias controls

- Hidden test indices are unavailable to feature, rule, and portfolio selection code.
- Dataset name is excluded as a feature unless it would exist in real use.
- Near-duplicate prompts remain within one split.
- Every attempted configuration and exclusion is recorded.
- Missing model outcomes are not silently interpreted as failures or wins; coverage and selection bias are reported.
- Advisor entropy, model selection share, and rare-expert recall detect collapse onto a popular model.
- A share-matched content-blind control detects apparent gains caused by selecting stronger tiers more often rather than understanding prompts.
- Prices and capabilities are refreshed before a run and then frozen.
- Feedback promotion requires replay evidence and manual approval; online self-modification is forbidden.

## 10. Reproducible artifacts

Each run produces:

- `manifest.json` — advisor, catalog, evidence, split, seed, container, and host versions.
- `recommendations.parquet` — content-minimized choices, estimates, confidence, and reason codes.
- `metrics.json` — aggregate, slice, calibration, feedback, and invariant results.
- `report.html` — interactive Pareto, calibration, model-share, and failure views.
- `report.md` — concise findings, limitations, and claim eligibility.
- `checksums.txt` — artifact integrity.

Public benchmark evidence and private user feedback use separate stores, retention rules, and exports.
