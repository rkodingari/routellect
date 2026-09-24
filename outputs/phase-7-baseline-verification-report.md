# Routellect G7-B Evidence and Baseline Verification Report

Date: 2026-09-21  
Status: G7-B complete; G7-C sponsor approval required

## Outcome

G7-B confirms the need for deterministic-v3 without opening the hidden test. A new 10,000-row,
zero-overlap R2-Bench window was frozen and divided by normalized prompt identity. Development and
validation evidence was minimized and persisted; 1,949 hidden rows were committed but their prompts
and outcomes were discarded.

The current v2 prompt segments add no validation routing value at the preregistered `λ=0.20`
operating point. Task, length, and task×length policies all select Llama-3.1-70B-Instruct for every
validation prompt, exactly matching the strongest/global fixed baseline.

## Data and integrity verification

| Check | Result |
|---|---:|
| Previously unused aligned rows | 10,000 |
| Development / validation / committed hidden | 6,045 / 2,006 / 1,949 |
| Alignment exclusions | 0 |
| Missing candidate observations | 0 |
| Trusted G5 prefix matches per candidate | 5,000/5,000 |
| Hidden prompts persisted | 0 |
| Hidden outcomes persisted | 0 |
| Hidden-test runs | 0 |
| Target-model calls | 0 |

Both persisted snapshots are verified by SHA-256 before benchmark loading. The hidden key/prompt
commitment is recorded in the provenance report and manifest.

## Current profiler audit

The deterministic-v2 profiler processed all 8,051 development and validation prompts in 613.57 ms,
or 0.0762 ms per prompt. Speed is excellent, but feature resolution is weak:

| Predicted family | Count |
|---|---:|
| General | 3,845 |
| Reasoning | 2,811 |
| Code | 670 |
| Writing | 274 |
| Extraction | 266 |
| Agent | 102 |
| Research | 78 |
| Summarization | 5 |

`general` accounts for 47.76% of visible evidence. These are v2 predictions, not ground-truth task
labels, so this distribution cannot establish classification accuracy. It does show that the current
feature vocabulary provides little segmentation for nearly half the corpus.

## Validation baseline at λ=0.20

| Strategy | Correctness | Normalized compute | Utility (95% CI) | Oracle regret | Selection behavior |
|---|---:|---:|---:|---:|---|
| Strongest fixed | 0.5366 | 0.9178 | 0.3530 (0.3371–0.3696) | 0.1565 | 100% Llama-3.1-70B |
| Global utility | 0.5366 | 0.9178 | 0.3530 (0.3371–0.3696) | 0.1565 | 100% Llama-3.1-70B |
| Length segment | 0.5366 | 0.9178 | 0.3530 (0.3371–0.3696) | 0.1565 | 100% Llama-3.1-70B |
| Task segment | 0.5366 | 0.9178 | 0.3530 (0.3371–0.3696) | 0.1565 | 100% Llama-3.1-70B |
| Hybrid segment | 0.5366 | 0.9178 | 0.3530 (0.3371–0.3696) | 0.1565 | 100% Llama-3.1-70B |
| Cheapest fixed | 0.2170 | 0.0086 | 0.2153 (0.2015–0.2282) | 0.2942 | 100% Qwen3-0.6B |
| Seeded random | 0.2858 | 0.2596 | 0.2339 (0.2202–0.2467) | 0.2756 | Approximately balanced |
| Oracle | 0.6056 | 0.4803 | 0.5095 (0.4955–0.5232) | 0 | Prompt-specific upper bound |

The oracle's paired utility advantage over global is 0.1565 with a 95% interval of
0.1456–0.1674. It selects the 70B candidate only 49.15% of the time and uses all four candidates.
This establishes meaningful complementarity in the validation evidence, while v2 fails to recover
any of it.

Routing policy lookup remains negligible at 0.000209 ms p95 over 10,000 measurements. Therefore,
G7-C should optimize discrimination and calibration without sacrificing the deterministic fast path.

## Interpretation

G7-B supports four conclusions:

1. Deterministic-v2 remains a safe, fast baseline.
2. Current task and length features are too coarse for prompt-specific routing on this evidence.
3. The failure is not caused by an absence of model complementarity; the oracle gap is substantial.
4. A stronger feature model must prove value over both v2 and a share-matched content-blind control.

The results do not validate the live provider catalog, current prices, target-model latency, or a
universal best-model claim. Correctness comes from R2-Bench judge scores and was not independently
rejudged.

## G7-C implementation recommendation

Proceed with deterministic-v3 development using only development and validation evidence:

- boundary-aware weighted lexical rules with negation and multi-label capability preservation;
- a frozen sparse linear utility/strength predictor trained on development outcomes;
- reviewed synthetic task/capability/privacy invariants for labels unavailable in R2-Bench;
- conservative token ranges and stable absolute utility transforms;
- calibrated uncertainty and an explicit low-confidence state;
- exact deterministic ties and dominated-candidate stability tests; and
- validation ablations against v2, fixed, random, content-blind, and oracle controls.

Because R2-Bench does not provide trustworthy task/capability labels, G7-C must not present v2
predictions as training truth. Learned heads should predict candidate utility/strength from outcomes;
task, capability, and privacy behavior remains governed by reviewed policy fixtures unless another
source passes a separate license and label-quality gate.

## Verification

- Repository lint: passed.
- New-script compilation: passed.
- Full Python suite: 53 passed with 87.05% statement coverage.
- Focused G7/evidence/profiler subset: 15 passed.
- Bootstrap repetitions: 2,000 with fixed seed 73.
- Baseline result SHA-256:
  `27537c804834cd06fb47ddedf583811856ba83720258bacd35e8915c28a147fa`.
- Hidden test: unopened.

The machine-readable aggregate result is `phase-7-baseline-results.json`.
