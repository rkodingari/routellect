# Routellect Phase 7-D Validation and Candidate-Freeze Plan

Date: 2026-09-22  
Status: Complete; approved as a validation-and-candidate-freeze milestone on 2026-09-22  
Hidden-test access: **Not authorized**  
Production activation: **Not authorized**

## Authorization boundary

The sponsor authorized G7-D by responding `proceed` after the G7-C2 approval gate. This phase may
run validation ablations, robustness tests, software verification, and hardened Podman checks; it
may freeze the candidate and preregister a new evaluation. It must not reconstruct or inspect the
existing 1,949-row R2 hidden partition, execute the new confirmatory evaluation, activate v3, or
start G7-E.

## Research decision

The evaluation design accounts for two recent benchmark findings:

- [R2-Bench](https://huggingface.co/datasets/JiaqiXue/R2-Bench) provides 30,968 prompts, ten models,
  sixteen output budgets, per-prompt quality scores, and an explicit MIT declaration. It is the only
  reviewed source that contains the exact four-model, 100-token pool used by this candidate.
- [LLMRouterBench](https://github.com/ynulihao/LLMRouterBench) provides more than 400,000 instances
  from 21 datasets and emphasizes Best Single, Random, Oracle, model-recall, cost, and latency
  controls. Its paper reports that several routers do not reliably beat Best Single. The repository
  and result bundle do not currently expose a sufficiently clear data-license declaration for this
  project, and its model pool differs from Routellect's frozen pool.

Accordingly, LLMRouterBench is a protocol influence and a possible future source-transfer check,
not G7-D training data or primary promotion evidence. It remains quarantined pending an explicit
dataset/result license and a preregistered tier-mapping rule.

## G7-D validation work

1. Re-evaluate the frozen G7-C2 artifact on already visible validation evidence without retraining,
   threshold selection, or model-pool changes.
2. Report fixed/Best Single, share-matched content-blind, G7-C, G7-C2, lower-tier-only, threshold
   sensitivity, and Oracle controls.
3. Use 10,000 paired bootstrap resamples for frozen promotion metrics.
4. Report task-family and difficulty slices, strong-tier calibration, recommendation shares, and
   prompt-normalization stability.
5. Verify byte-identical deterministic decisions across process hash seeds, no network requirement,
   no raw-prompt cache, and no raw prompt in generated reports.
6. Run the complete software suite and a rootless, read-only, capability-dropped Podman benchmark.
7. Freeze code, artifacts, evidence identities, threshold, model pool, metric definitions, and the
   promotion rule in a machine-readable manifest.

## New confirmatory evaluation design

The primary G7-E evaluation, if separately authorized, will use an untouched R2-Bench range after
the candidate freeze:

- source revision: `1b6234647a21705da4c220f339e44fbe72c69bb2`;
- source prompt IDs: 15,001 through 30,968;
- exact candidate pool: Qwen3-0.6B, Qwen2.5-Math-1.5B-Instruct,
  Qwen2.5-Math-7B-Instruct, and Llama-3.1-70B-Instruct;
- output budget: 100 tokens;
- no responses, golden answers, templated prompts, or judge rationales retained;
- exact and normalized duplicate groups shared with all visible R2 and RouteLLM prompts excluded
  before outcomes are made available to the evaluator;
- near-duplicate screening rules frozen before prompt-only acquisition;
- excluded-group counts reported, never silently replaced;
- candidate recommendations generated and committed before model outcomes are joined;
- outcomes joined once in an isolated evaluation process; and
- every preregistered result, subgroup, and failure reported.

R2-Bench does not publish origin-dataset labels. Therefore this primary test is an untouched
exact-pool evaluation, not evidence of source-level generalization. A source-grouped secondary test
must use a separately licensed benchmark with explicit dataset identity. It is mandatory for a
broad cross-domain claim but cannot substitute for the exact-pool promotion test.

## Frozen promotion criteria

All conditions are conjunctive on the new untouched exact-pool evaluation:

- zero hard-constraint, privacy, capability, budget, or latency regressions;
- quality-retention lower 95% bound versus strongest fixed model at least 0.99;
- compute-reduction lower 95% bound versus strongest fixed model at least 0.40;
- paired utility-difference lower 95% bound versus fixed and share-matched content-blind above 0;
- Oracle-regret reduction at least 20%;
- no preregistered major slice with a statistically material safety or quality regression;
- uncached local p95 candidate inference below 10 ms; and
- one evaluation run, with no threshold, artifact, feature, or exclusion-rule changes afterward.

Failure of any condition means automatic non-promotion. Thresholds will not be relaxed after the
evaluation.

## Stop condition

The validation report, Podman evidence, freeze manifest, and gate review are complete. The sponsor
approved G7-D on 2026-09-22. Work remains stopped; G7-E and all untouched-outcome access require a
new sponsor decision.
