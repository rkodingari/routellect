# Routellect Phase 7-C2 Bounded Revision Plan

Date: 2026-09-21  
Status: Complete; approved as a bounded research milestone on 2026-09-22  
Hidden-test access: **Not authorized**

## Objective

Determine whether legally usable pairwise preference evidence can improve the dependency-free
prompt-strength learner without weakening deterministic privacy, capability, context, budget, or
latency authority.

## Evidence decision

- Add `routellm/gpt4_judge_battles` as auxiliary development evidence. Its Hugging Face metadata
  explicitly declares Apache-2.0 at revision
  `2a1afe8d0659904c0f6f59de6179e086fdb027c7`.
- Retain only normalized prompt text, row identity, and the three winner indicators during local
  development. Do not retain model responses.
- Continue excluding xRouteBench: its repository is MIT, but the dataset card currently does not
  declare a dataset license.
- Continue reserving RouterArena for evaluation only; its policy prohibits fitting or tuning on its
  labels.

## Leakage decision

The original R2 hidden prompts remain sealed. Because cross-source prompt overlap cannot be checked
against a sealed partition, G7-C2 will not claim the auxiliary source is disjoint from that hidden
partition. No hidden run is authorized. Before any future confirmatory test, G7-D must either prove
cross-source group disjointness without exposing outcomes or freeze a new evaluation source after
the learner is finalized.

The already inspected R2 development and validation partitions are treated as visible development
evidence for G7-C2. Evaluation is grouped out-of-fold and explicitly exploratory.

## Implementation

1. Acquire a pinned, minimized 20,000-row RouteLLM window and verify license/model/label schema.
2. Train a binary sparse strength head using RouteLLM preference labels and visible R2 strong-tier
   labels, with fixed feature hashing and no runtime dependency.
3. Retain the existing candidate-specific sparse regression head for choosing among lower tiers.
4. Select thresholds only with grouped out-of-fold visible evidence.
5. Compare single-source G7-C, multi-source G7-C2, fixed/v2, content-blind, and oracle controls.
6. Keep all learned influence outside hard eligibility and leave v2 as the product default.

## Frozen safety criteria

- zero hard-constraint regressions;
- all G7-C synthetic profiler/runtime checks remain passing;
- no raw model responses or hidden prompts/outcomes persisted;
- no target-model calls or provider credentials;
- deterministic artifact and result checksums;
- grouped out-of-fold utility is not worse than G7-C;
- any production claim still requires the original G7 promotion thresholds—99% quality retention,
  40% compute reduction, positive paired utility bounds, and 20% regret reduction—on genuinely
  untouched evidence.

## Gate

Acquisition, implementation, grouped visible-evidence evaluation, tests, and the claim audit are
complete. The sponsor approved G7-C2 as a bounded research milestone on 2026-09-22. G7-D and all
hidden-test activity require a separate sponsor decision.

Follow-on status: G7-D was subsequently authorized and completed without hidden-test activity. G7-E
and all untouched-outcome access still require a new sponsor decision.
