# Routellect Phase 7 Gate Review

Status: **G7-A approved by sponsor; G7-B authorized**  
Date: 2026-09-21

Approval recorded: 2026-09-21 (sponsor response: “Approve G7-A”).

## Gate recommendation

Approve G7-A and authorize G7-B evidence acquisition and baseline audit only.

The proposed phase keeps hard policy deterministic, replaces brittle substring profiling with a
versioned lexical layer plus a frozen explainable sparse classifier, stabilizes token/cost/latency
estimates, calibrates uncertainty, and requires prompt-specific value on untouched evidence before
production promotion.

## Acceptance checklist

- [x] Existing evidence limitations are stated without treating the seven software fixtures as a
  real-world quality benchmark.
- [x] The opened G5 hidden test is prohibited from new confirmatory use.
- [x] Profiler correctness and model-routing utility are evaluated as separate tracks.
- [x] Hard privacy, capability, context, budget, and latency policy retains final authority.
- [x] Proposed runtime classification is local, deterministic, versioned, and explainable.
- [x] RouterBench, R2-Bench, LLMRouterBench, and RouterArena have explicit proposed roles and
  license/usage gates.
- [x] Dataset identity, model answers, and outcome labels are prohibited runtime features.
- [x] Fixed/random/v2/content-blind/oracle baselines and ablations are required.
- [x] Quality retention, cost reduction, utility, regret, calibration, robustness, latency, and
  privacy metrics are preregistered.
- [x] Acceptance thresholds and one-time hidden-test rules are frozen before acquisition.
- [x] Advisory-only, no-credential, no-target-call, and no-default-prompt-retention boundaries remain.
- [x] Every implementation, validation, hidden-test, promotion, and release step has a sponsor gate.

## Decision requested

Approve G7-A to authorize only:

1. source and per-dataset license verification;
2. source revision, row identity, transformation, and checksum freezing;
3. content-minimized evidence acquisition;
4. duplicate-safe development/validation/hidden split creation; and
5. deterministic-v2 plus fixed, random, and oracle baseline measurement.

Approval does not authorize deterministic-v3 implementation, opening the hidden test, production
promotion, provider credentials, recommended-model execution, public deployment, or publication.

## Evidence package

- [Deterministic routing intelligence plan](./phase-7-deterministic-routing-plan.md)
- [G5 verification and limitations](./phase-5-verification-report.md)
- [Original benchmark protocol](./phase-1-benchmark-protocol.md)

Decision: **Approved.** Work may proceed through G7-B and must stop at the G7-B evidence and
baseline gate before deterministic-v3 implementation.
