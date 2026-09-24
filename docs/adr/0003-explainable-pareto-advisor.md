# ADR 0003: Explainable Pareto-aware advisor and governed policy promotion

- Status: Implemented; awaiting G4 gate approval
- Date: 2026-09-16

## Context

Routing research increasingly shows that complex learned routers do not reliably outperform simple
baselines across datasets and candidate pools. A small advisory tool therefore needs to make its
trade-offs inspectable, preserve specialist models that aggregate ranking can overlook, and refuse to
activate learned behavior merely because it is more sophisticated.

## Decision

Routellect retains deterministic hard eligibility and objective scoring as the primary advisor. It
adds an uncertainty penalty, computes the quality/cost/latency Pareto frontier, and requires the
primary recommendation to come from that frontier. The three-place shortlist preserves the
objective winner, lowest-cost eligible alternative, and highest-quality specialist when distinct.
Every score is the exact sum of visible quality, cost, latency, evidence-risk, uncertainty, and
optional feedback contributions.

The only learned ranking signal remains the bounded local empirical-Bayes feedback policy. Its
versioned manifest has a stable SHA-256 identity. Manual promotion requires chronological aggregate
and per-task non-regression checks; every promotion attempt is recorded, and rollback is explicit and
audited. The policy cannot modify hard privacy, capability, context, cost, latency, or quality-floor
eligibility.

The dashboard separates prompt advice from evidence and learning. It exposes catalog provenance,
score contributions, shortlist comparison, prompt-free feedback history, policy audit, rollback, and
the non-executing software benchmark. Recommendation exports omit the raw prompt.

## Consequences

- A dominated configuration cannot become the primary recommendation.
- Quality specialists remain visible even under cost-focused objectives.
- Users can reproduce each displayed score and inspect uncertainty.
- No learned quality estimator is activated without outcome-level validation; that evidence remains a
  G5 prerequisite.
- The policy digest provides immutable identity and auditability but is not a cryptographic release
  signature. Release/image signing remains G6 scope.

## Research basis

- RouteLLM established preference-data routing with cost/quality trade-offs.
- RouterEval and LLMRouterBench found that router results depend strongly on candidate curation,
  datasets, latency treatment, and evaluation protocol, and that simple baselines remain competitive.
- Calibrated selective classification supports treating uncertainty and abstention thresholds as
  measured operating decisions rather than unqualified confidence claims.
