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
