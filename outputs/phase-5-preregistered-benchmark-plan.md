# Routellect G5 Preregistered Benchmark Plan

Frozen: 2026-09-16, before inspecting candidate-model scores  
Status: Executed once; hidden test opened; no further tuning permitted

## Research question

Can Routellect's simple prompt-segment advisor improve the quality–cost utility of a compact model
pool over equally informed global and single-model baselines, without hiding regressions in task or
prompt-length slices?

This is an offline advisory benchmark. It performs no target-model inference.

## Evidence snapshot

- Dataset: [R2-Bench](https://huggingface.co/datasets/JiaqiXue/R2-Bench)
- Repository revision: `1b6234647a21705da4c220f339e44fbe72c69bb2`
- Declared dataset license: MIT
- Fixed source rows: first 5,000 aligned query rows from each selected result file
- Fixed output budget: 100 tokens
- Only `key`, `prompts_id`, `original_prompt`, `actual_token_count`, and `correctness_score` are used.
  Model responses, golden answers, and judge rationales are not retained.
- The normalized snapshot and manifest receive SHA-256 digests after acquisition.

The first-5,000 restriction is a download-size constraint and a known order-bias risk. It is frozen
before scores are inspected and must be reported with results.

## Candidate pool

The pool is frozen before score inspection to span four compute tiers and preserve a mathematics
specialist pair plus a general large model:

| Candidate | Parameter-size proxy |
|---|---:|
| Qwen3-0.6B | 0.6 |
| Qwen2.5-Math-1.5B-Instruct | 1.5 |
| Qwen2.5-Math-7B-Instruct | 7.0 |
| Llama-3.1-70B-Instruct | 70.0 |

No candidate is added, removed, or renamed after score inspection. Parameter count multiplied by
actual output tokens is the preregistered compute-cost proxy. It is not a provider price or measured
latency. Advisor overhead is measured separately.

## Frozen split

Each query key is assigned with `SHA-256("routellect-g5-v1|" + key)`:

- 60% development/train;
- 20% validation;
- 20% hidden test.

The hidden-test metrics are computed once after implementation and validation decisions are frozen.
Seed 42 controls all bootstrap and random-baseline operations.

## Compared strategies

1. `always_cheapest`: globally cheapest candidate by development mean compute proxy.
2. `always_best_quality`: highest development mean correctness.
3. `global_utility`: one candidate maximizing development mean utility.
4. `length_segment`: length-band means with empirical shrinkage to global model means.
5. `task_segment`: Routellect deterministic task-family means with empirical shrinkage.
6. `hybrid_segment`: task-family × fixed prompt-length-band means with empirical shrinkage.
7. `seeded_random`: deterministic per-query seeded candidate selection.
8. `oracle`: per-query upper bound; never an eligible deployable strategy.

Length bands are fixed at `<128`, `128–511`, `512–2047`, and `≥2048` characters. Segment support is
shrunk toward global model means with prior strength 20. No embeddings, target LLM, or external API
is used.

## Objectives and metrics

For model `m` and query `q`:

`utility(q,m,λ) = correctness_score(q,m) - λ × normalized_compute_proxy(q,m)`

Frozen λ values: `0.00`, `0.05`, `0.10`, `0.20`, `0.40`. The primary operating point is `λ=0.20`.

Report for validation and hidden test:

- mean correctness and 95% bootstrap confidence interval;
- mean normalized compute proxy and 95% interval;
- mean utility and 95% interval;
- paired utility difference versus `global_utility` and 95% interval;
- oracle regret;
- quality-floor violation rates at 0.40, 0.60, and 0.80;
- candidate recommendation shares;
- per-task-family and per-length-band metrics;
- strategy-level quality/cost Pareto frontier;
- routing overhead p50/p95 on the local CPU;
- sample sizes, exclusions, missingness, and snapshot digests.

Bootstrap resamples queries with replacement 2,000 times using seed 42. Intervals are percentile
intervals and are descriptive, not corrected for multiple comparisons.

Operational clarification recorded before score acquisition: all five λ values receive point
estimates as a sensitivity analysis. The full 2,000-resample confidence intervals, paired
differences, slice checks, and promotion decision are reported at the preregistered primary
operating point, λ=0.20. This keeps the confirmatory evidence distinct from sensitivity analysis.

## Promotion rule

`hybrid_segment` may be recommended as an offline learned candidate only if, on validation at
`λ=0.20`:

1. mean utility is at least `global_utility`;
2. no task-family slice with at least 30 samples regresses by more than 0.02 utility;
3. no length-band slice with at least 30 samples regresses by more than 0.02 utility;
4. routing p95 remains below 25 ms; and
5. no target-model calls occur.

Hidden-test results are then reported regardless of whether they support the candidate. Production
promotion still requires a separate signed-policy workflow and sponsor approval; G5 evidence alone
does not silently change live advice.

## Claims policy

Routellect will not claim to be the “best router” from this benchmark. A comparative claim must name
the dataset revision, selected rows, candidate pool, token budget, utility λ, baseline, uncertainty,
and limitations. Results do not transfer automatically to Routellect's live catalog because the
R2-Bench model IDs and cost proxy differ from live provider configurations.
