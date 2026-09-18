# ADR — Hybrid Local Prompt Assessor

Status: Direction approved by sponsor; implementation pending Gate G1  
Date: 2026-09-15

## Decision

Routellect will use a hybrid decision pipeline:

1. A deterministic fast profiler analyzes every prompt.
2. A calibrated uncertainty trigger invokes a compact local language model in Auto mode only for ambiguous or difficult prompts.
3. The local assessor proposes structured task, difficulty, capability, output-shape, ambiguity, and privacy-risk features.
4. A deterministic validator merges those features conservatively.
5. Deterministic eligibility, evidence scoring, and ranking select the recommended model/configuration.

The local assessor is not an autonomous agent. It has no tools, network, memory, provider credentials, catalog/model scores, or authority to make the final recommendation.

## User controls

- **Auto** — default candidate; invoke only above the calibrated uncertainty threshold.
- **Always** — run the assessor for evaluation or expert use.
- **Off** — deterministic-only behavior and no assessor load/inference.

Any timeout, crash, resource limit, or invalid output produces a visible deterministic fallback.

## Why

- Deterministic analysis is fast, private, reproducible, and auditable.
- Semantic assessment can recognize nuanced intent and difficulty that surface rules miss.
- Keeping the assessor away from model names and scores prevents it from becoming an opaque router.
- Uncertainty-triggered activation limits latency, memory, and energy overhead.

FrugalGPT provides evidence that learned cascades can improve cost/quality trade-offs in evaluated settings. A recent common-interface routing study also warns that apparent routing gains may come from route-mix changes rather than prompt understanding. Therefore, hybrid activation requires a share-matched content-blind control and paired prompt-level ablation before it becomes the default.

## G2 assessor bake-off

The exact model/runtime is intentionally not chosen at G1. G2 will compare a small set of license-compatible, CPU-capable candidates under the same frozen prompt-analysis dataset.

Selection considers:

- Task/difficulty/capability accuracy and calibration.
- Incremental end-to-end recommendation utility over deterministic-only advice.
- p50/p95 latency, peak memory, startup time, CPU time, and image-size contribution.
- Structured-output validity, injection robustness, privacy-policy monotonicity, and deterministic fallback rate.
- Model/runtime license, provenance, architecture support, reproducibility, and maintenance health.

The smallest candidate on the Pareto frontier wins; brand or parameter count does not.

## Default-activation gate

Auto becomes the default active mode only if held-out results show statistically supported prompt-specific improvement over both:

1. Assessor Off.
2. A content-blind baseline matched to Auto’s model-selection shares.

It must also satisfy the approved privacy, latency, memory, stability, and container bounds. If it does not, the hybrid capability remains available but defaults to Off.

## Consequences

- The production image contains one pinned quantized assessor artifact and CPU runtime, with no runtime download.
- Assessor identity, mode, invocation status, confidence, and fallback status appear in recommendation evidence and content-free receipts.
- Feedback may recalibrate the trigger and feature confidence only through offline candidate training, replay, bias checks, and manual promotion.
- Target-model execution remains completely outside product scope.

## Research references

- [FrugalGPT](https://arxiv.org/abs/2305.05176)
- [Common-interface hybrid router evaluation](https://arxiv.org/abs/2608.14641)
- [LLMRouterBench](https://arxiv.org/abs/2601.07206)
