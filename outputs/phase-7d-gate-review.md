# Routellect Phase 7-D Gate Review

Date: 2026-09-22  
Decision date: 2026-09-22  
Status: **Approved as a validation-and-candidate-freeze milestone**

## Sponsor decision

G7-D was approved on 2026-09-22 with the gate recommendation and restrictions below. This approval
accepts the completed validation, Podman evidence, and candidate freeze. It does not authorize
G7-E, outcome acquisition, production activation, or use of the existing hidden partition.

## Gate recommendation

Approve G7-D as a completed validation-and-candidate-freeze milestone. Reject production activation
and keep deterministic-v2 as the default. G7-E, new evaluation acquisition, and all outcome access
remain unauthorized.

## Acceptance checklist

- [x] Existing hidden prompts and outcomes remained unopened.
- [x] Candidate artifact, threshold, feature hash, model pool, evidence, metric definitions, and
  promotion rule are SHA-256 frozen.
- [x] Candidate was not retrained and the threshold was not reselected.
- [x] Validation uses 10,000 paired prompt-level bootstrap resamples.
- [x] Best Single/fixed, G7-C, lower-tier-only, share-matched content-blind, and Oracle controls are
  reported.
- [x] Calibration, task/difficulty slices, threshold sensitivity, normalization stability, and
  cross-process determinism are reported.
- [x] No raw prompt is persisted in G7-D output.
- [x] Native candidate p95 remains below 10 ms.
- [x] Exact artifact passes network-disabled Podman inference.
- [x] Rootless Podman is healthy, non-root, read-only, capability-free, and
  `no-new-privileges`-protected.
- [x] Production container remains deterministic-v2 by default.
- [x] Ruff is clean; 70 tests pass; total line coverage is 88%.
- [x] Failed performance criteria are reported without threshold relaxation.

## Non-passing promotion checks

- Quality-retention lower bound: 0.9672, required 0.99.
- Compute-reduction lower bound: 0.0820, required 0.40.
- Utility-vs-fixed lower bound: -0.0002, required above 0.
- Oracle-regret reduction: 4.57%, required at least 20%.
- Untouched confirmatory evidence: unavailable.

## Decision boundary

G7-D is approved as a completed research validation and freeze milestone. This approval does not:

- activate deterministic-v3 or either sparse artifact;
- change the API, dashboard, or CLI production default;
- authorize G7-E or new outcome acquisition;
- open or reconstruct the existing 1,949-row hidden partition; or
- authorize a production-ready, best-in-class, or universal-quality claim.

Work remains stopped. A separate, explicit G7-E authorization is required for the preregistered new
evaluation, and the source-control freeze blocker must be resolved first.
