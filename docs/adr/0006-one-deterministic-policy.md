# ADR 0006: Expose one deterministic recommendation policy

Date: 2026-09-24
Status: Implemented at G8-B; awaiting sponsor verification approval

## Context

Routellect currently supports production v2 and an explicit experimental v3 CLI path. Although the
separation protected production during research, it leaves two deterministic implementations in
the product code and makes the advisory contract harder to explain. G7-E also rejected promotion of
the complete v3 candidate.

## Decision

Routellect will have one supported deterministic policy. It will retain the proven v2 hard
constraints, ranking, shortlist, evidence, and feedback behavior while incorporating only isolated
prompt-interpretation hardening: bounded matching, negation handling, expanded privacy detection,
Unicode normalization, conservative token sizing, and deterministic reason codes.

The v3 selector, alternate advisor branch, and importable sparse candidate will be removed from the
runtime. Failed experimental ranking and sparse-routing behavior will not be merged. Historical
reports, aggregate evidence, and policy identifiers remain for reproducibility and auditability.

## Consequences

Users receive one explainable answer path across the dashboard, API, and CLI. Maintainers test one
set of runtime invariants. Existing research remains transparent without being confused with a
supported feature. This decision does not establish a new benchmark claim; future effectiveness
claims require a separately preregistered untouched evaluation.

The detailed migration and acceptance criteria are frozen in
`outputs/phase-8-single-policy-consolidation-plan.md`.

## Implementation

G8-B removes the CLI selector, alternate advisor and profiler branches, sparse runtime module,
packaged strength artifacts, and obsolete policy-training implementations. New responses identify
the single path as `deterministic-unified-v1+feedback-bayes-v1`. Container rebuilding and release
verification remain gated at G8-C.
