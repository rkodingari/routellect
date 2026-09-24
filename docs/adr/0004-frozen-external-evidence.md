# ADR 0004: Frozen, minimized external routing evidence

- Status: Implemented; awaiting G5 gate approval
- Date: 2026-09-16

## Context

Routellect needs outcome evidence for advisory-policy evaluation without turning into a model proxy,
requiring provider credentials, redistributing unclear-license datasets, or leaking benchmark
responses and judge rationale into the product image. Several routing benchmarks are valuable but
have different code and dataset licensing boundaries.

## Decision

Use R2-Bench at pinned revision `1b6234647a21705da4c220f339e44fbe72c69bb2`, whose dataset card
declares MIT. Stream only the first 5,000 rows for four preregistered 100-token candidate files.
Require exact query keys and prompt IDs, plus a visible-character prompt fingerprint that ignores
only Unicode whitespace and control/format artifacts. Exclude any non-equivalent prompt from every
candidate.

Retain only query identity, canonical public prompt, output-token count, and correctness score.
Discard model responses, golden answers, templated prompts, and judge rationale. Hash the normalized
snapshot and keep it under `work/`, outside the production container.

Evaluate fixed deterministic, random, segmented, global, and oracle policies with a stable
60/20/20 hash split. Fit policies on training data only. Use the validation split for the frozen
promotion rule and access the hidden test once. The benchmark may recommend a candidate for a
separate policy review; it cannot change production advice automatically.

## Consequences

- The evidence is reproducible, license-aware, content-minimized, and target-call-free.
- Parameter count × output tokens is only a compute proxy, not price or measured model latency.
- The first-5,000-row sample can carry order bias and covers one dataset and token budget.
- Passing a non-regression gate does not imply practical value. A tied, more complex policy should
  remain unpromoted under the project's simplicity principle.
- Future policy work needs a separately preregistered dataset/candidate pool or a new untouched test
  split; the G5 hidden test must not become a tuning set.
