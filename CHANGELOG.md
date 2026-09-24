# Changelog

All notable changes to Routellect follow Keep a Changelog. The project uses semantic versioning once
the first release is approved.

## [Unreleased]

### Added

- Advisory-only web, CLI, and HTTP interfaces.
- Deterministic privacy, capability, context, budget, latency, and quality policy.
- Opt-in local semantic-embedding assessor with Auto, Always, and Off modes.
- Dated multi-provider and local model catalog with estimate ranges and evidence links.
- Content-free recommendation receipts and structured outcome feedback.
- Reproducible software benchmark endpoint and Podman container.
- Ed25519-signed, versioned offline catalog import with strict validation and rollback.
- Content-minimized feedback export, item deletion, full reset, and collection opt-out.
- Profile-scoped Bayesian personalization with support gates, shrinkage, bounded influence,
  chronological replay, and explicit manual promotion.
- Pareto-safe primary selection, quality-specialist recall guard, uncertainty penalties, and
  score-level explanations that reconcile to the ranking total.
- Immutable feedback-policy identity, per-task replay guards, promotion audit receipts, and explicit
  rollback.
- Responsive evidence dashboard with shortlist comparison, feedback history, catalog provenance,
  benchmark explorer, and prompt-free Markdown/JSON advisory exports.
- Preregistered, score-blind R2-Bench acquisition with pinned revision, strict cross-model
  alignment, minimized retained fields, and SHA-256 snapshot provenance.
- Train/validation/hidden-test advisory benchmark with deterministic baselines, shrunken prompt
  segments, 2,000 paired bootstrap resamples, slice guards, Pareto analysis, and a no-target-call
  assertion.
- Checksummed backup/restore with traversal defense, refuse-overwrite behavior, SQLite integrity
  checks, and explicit age-based retention.
- CycloneDX 1.6 release inventory, versioned third-party notices, release provenance manifest, and
  offline verification support.
- Explicit experimental deterministic-v3 policy with boundary-aware weighted matching, negation
  handling, expanded synthetic privacy guards, conservative token sizing, stable absolute utility
  transforms, deterministic ties, and an inactive development-only sparse strength artifact.
- G7 synthetic invariant corpus, development/validation sparse-router audit, share-matched
  content-blind control, paired bootstrap intervals, and machine-readable promotion checks.
- Bounded G7-C2 multi-source strength experiment using a response-minimized, Apache-2.0 RouteLLM
  development snapshot, with an uncached dependency-free runtime and explicit non-promotion result.
- Sponsor approval of G7-C2 as a bounded research milestone, with deterministic-v2 unchanged as the
  production default and hidden-test access and v3 activation explicitly unauthorized.
- G7-D frozen-candidate audit with 10,000 paired bootstrap resamples, calibration and subgroup
  diagnostics, normalization and cross-process determinism checks, a preregistered untouched
  evaluation design, and machine-readable non-promotion criteria.
- Hardened rootless Podman evidence for the exact frozen artifact with network disabled, zero
  effective capabilities, read-only filesystems, non-root execution, and v2 retained as default.
- Sponsor approval of G7-D as a validation-and-candidate-freeze milestone, with G7-E, outcome
  acquisition, production activation, and existing-hidden-partition access still unauthorized.
- One-time G7-E evaluation on 15,634 overlap-screened, previously unused R2-Bench prompts, with
  outcome-blind recommendation commitment, 10,000 paired resamples, prompt-free public evidence,
  and automatic non-promotion after quality, compute, regret, and reasoning-slice gate failures.
- Sponsor approval of G7-E as a completed one-time evaluation with the non-promotion decision
  accepted, deterministic-v2 retained, v3 inactive, and no second evaluation authorized.
- G8-A architecture approval for one supported deterministic policy, preserving v2 constraints and
  ranking while admitting only isolated prompt-safety hardening; implementation remains gated.

### Changed

- Consolidated the advisor and profiler into one
  `deterministic-unified-v1+feedback-bayes-v1` path across the dashboard, API, CLI, and software
  benchmark.
- Ported reviewed Unicode normalization, boundary-aware matching, negation handling, expanded
  privacy canaries, conservative token sizing, and deterministic reason codes while retaining the
  supported v2 hard constraints and relative ranking.

### Removed

- Removed the CLI policy selector, alternate v3 advisor/profiler branches, sparse runtime module,
  packaged G7/G7-C2 strength artifacts, and obsolete policy-training implementations.

### Approved gates

- Sponsor approval of G8-B as the completed single-policy implementation, with G8-C container and
  release verification authorized but release publication still gated.
- G8-C container verification completed with fresh rootless Podman evidence, Docker-format
  healthcheck preservation, no-network advisory-only runtime checks, fresh SBOM/license inventory,
  and explicit residual dependency findings; release publication remains gated.

### Security

- No provider credentials, target-model adapters, prompt persistence, or runtime model downloads.
- Non-root image supports read-only root filesystems, dropped capabilities, and no-new-privileges.
- Catalog updates reject untrusted signatures, hash mismatches, replayed versions, expired snapshots,
  unsafe evidence URLs, unknown fields, and invalid estimates.
- External benchmark payloads retain no model response, reference answer, judge rationale, or
  templated prompt; the evidence snapshot remains outside the production container.
- Default 1 MiB write-body limit, per-client token-bucket write throttling, and duplicate-feedback
  rejection to reduce denial-of-service and feedback-poisoning risk.
- Container bases and the bundled assessor source are pinned to immutable digests/revisions; the
  unnecessary runtime package installer is removed.
