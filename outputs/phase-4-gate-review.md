# Routellect Phase 4 Gate Review

Status: **G4 approved by sponsor; G5 authorized**  
Date: 2026-09-16

Approval recorded: 2026-09-16 (sponsor response: “yes”).

## Gate recommendation

**Approve G4 with the evidence-bound deferrals below.** The product now delivers a distinctive but
simple advisory experience: Pareto-safe recommendations, a protected quality specialist, exact score
explanations, private governed learning, and one focused evidence dashboard. It remains fully
advisory-only and Podman-containerized.

## Acceptance checklist

- [x] G3 sponsor approval recorded; work stayed within the G4 authorization boundary.
- [x] Hard privacy/capability/context/budget/latency/quality eligibility still precedes ranking.
- [x] Uncertainty penalties and a quality/cost/latency Pareto filter are implemented.
- [x] A dominated option cannot become the primary recommendation.
- [x] Lowest-cost and highest-quality specialist roles are protected in the three-item shortlist.
- [x] Every score reconciles to visible quality, cost, latency, evidence-risk, uncertainty, and
  optional feedback contributions.
- [x] Bounded feedback is the only learned ranking signal and remains off by default.
- [x] Promotion requires manual replay, aggregate non-regression, and per-task non-regression.
- [x] Insufficient, promoted/unchanged, rejected, and rollback decisions are auditable.
- [x] Dashboard includes advisor, comparison, report export, feedback history/control, catalog
  provenance, policy audit/rollback, and benchmark explorer.
- [x] Keyboard/accessibility semantics, reduced motion, responsive breakpoints, production build, and
  live desktop browser review pass.
- [x] 34 tests pass, 86% coverage, lint/typecheck/build pass.
- [x] Built-in benchmark: 100% task-family accuracy, 100% Pareto-safe primaries, 100% specialist
  shortlist coverage, exact score reconciliation, 0.549 ms p95 on this run, zero target calls.
- [x] Final 0.3.0 image builds under rootless Podman; hardened runtime controls and readiness pass.
- [ ] Outcome-calibrated quality/difficulty/cost/latency learned estimators — correctly not activated
  without G5 outcome data.
- [ ] Formal confidence calibration and quality-floor thresholds — deferred to G5 outcome evidence.
- [ ] Independent cryptographic signing of learned-policy releases — deferred to G6 image/release
  provenance; G4 uses immutable SHA-256 policy identity and audit receipts.
- [ ] Automated multi-viewport pixel-diff service — desktop live visual baseline completed; broader
  release automation remains G6.

## Decision requested

Approve G4 to authorize G5 only: frozen, license-compatible routing datasets; compact candidate-pool
selection; preregistered deterministic/learned baselines; statistical quality–cost–latency results;
failure slices; and reproducible benchmark reports.

Approval does **not** authorize public deployment, publication, provider credentials, target-model
execution, automatic catalog fetching, release signing, or a “best in benchmarks” claim before G5
evidence satisfies the approved protocol.

## Evidence package

- [G4 verification report](./phase-4-verification-report.md)
- [G4 benchmark result](./phase-4-benchmark-result.json)
- [Explainable Pareto advisor ADR](../docs/adr/0003-explainable-pareto-advisor.md)
- [G3 approval](./phase-3-gate-review.md)
- [Benchmark protocol](./phase-1-benchmark-protocol.md)
- [Delivery plan](./phase-1-delivery-plan.md)

Decision: **Approved with the recorded evidence boundaries.** Work may proceed through G5 and must
stop at the G5 review gate.
