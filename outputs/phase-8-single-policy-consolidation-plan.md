# Routellect Phase 8 Single-Policy Consolidation Plan

Date: 2026-09-24
Status: G8-B implemented and verified; awaiting sponsor decision
Release status: Not authorized

## 1. Decision

Routellect will expose exactly one deterministic recommendation policy. Research candidates may be
documented in immutable evaluation outputs and Git history, but they must not remain selectable,
importable as alternate production advisors, or bundled as active model-selection artifacts.

The consolidated policy will be identified as
`deterministic-unified-v1+feedback-bayes-v1`. The name is an audit identifier, not a user-selectable
version. Every dashboard, API, and CLI recommendation will use this policy.

## 2. Consolidation boundary

The implementation starts from the supported v2 policy because it is the production baseline and
the G7-E confirmatory evaluation rejected the complete v3 candidate.

### Retain unchanged

- privacy, capability, context-window, budget, latency, and minimum-quality hard constraints;
- objective weights and v2 relative cost/latency ranking until a fresh evaluation supports a
  ranking change;
- Pareto filtering, economical alternative, and quality-specialist recall guard;
- bounded feedback personalization, score reconciliation, evidence penalties, and uncertainty
  penalties;
- deterministic configuration-ID tie-breaking; and
- content-free recommendation receipts and historical policy identifiers.

### Port as correctness hardening

- Unicode NFKC normalization;
- boundary-aware term matching to prevent substring collisions;
- local negation handling for task and capability terms;
- expanded, synthetic-tested privacy patterns;
- conservative token estimation for prose, code, punctuation, and non-ASCII text; and
- explicit reason codes for ambiguity, negation, conservative sizing, and sensitive content.

These changes affect prompt interpretation and hard-constraint safety. They do not activate the
failed sparse router or v3 ranking policy.

### Remove from the supported runtime

- `Advisor(policy_version=...)` and every v2/v3 branch;
- the CLI `--policy-version` option;
- `deterministic_profile_v3` as a second entry point;
- `EXPERIMENTAL_ADVISOR_VERSION` and v3-specific scoring constants;
- importable sparse routing code and packaged G7/G7-C2 strength artifacts; and
- tests that assert an alternate runtime policy is selectable.

Research reports, prompt-free aggregate results, acquisition scripts, hashes, and ADR history may
remain as evidence. Historical `policy_version` fields in feedback and audit records remain because
they describe past data; they must never select recommendation behavior.

## 3. Required architecture after G8-B

```text
Dashboard / API / CLI
          |
          v
       Advisor
          |
          +-- one deterministic_profile()
          +-- optional local assessor fallback
          +-- one hard-constraint filter
          +-- one ranking and shortlist path
          |
          v
  one recommendation response
```

There will be no policy selector in the public interface and no hidden environment variable that
changes the deterministic algorithm.

## 4. Correctness invariants

G8-B must add or preserve machine-enforced tests for all of the following:

1. Identical inputs, catalog, feedback state, and settings produce identical analysis, ranking,
   scores, reasons, and estimates; only receipt ID and creation time may differ.
2. `local_only` never returns a hosted configuration.
3. Sensitive-content detection can tighten `standard` privacy but can never weaken requested
   privacy.
4. Capability, context, budget, latency, and minimum-quality constraints are never bypassed.
5. Negated capabilities do not become requirements, while positive requirements remain detected.
6. Substring lookalikes do not create task or capability matches.
7. Token estimates are positive, conservative for code/non-ASCII content, and monotonic when text
   is appended.
8. Recommendation score contributions reconcile to the reported score, including feedback.
9. Adding an ineligible catalog item does not change existing eligible recommendations.
10. Ties resolve by the documented stable ordering.
11. No target model, provider credential, network call, or prompt persistence is introduced.
12. The built distribution contains one advisor policy and no sparse candidate artifact.

## 5. Validation plan

G8-B implementation is not accepted until it passes:

- the complete Python test suite and configured coverage floor;
- Ruff static checks;
- the deterministic invariant corpus;
- differential regression checks against v2 hard constraints and shortlist behavior;
- privacy false-positive and recall canaries;
- score-reconciliation and cross-process determinism checks;
- secret scanning, dependency verification, and built-wheel inspection; and
- rootless Podman health, read-only filesystem, dropped-capability, and non-root checks in G8-C.

Development and validation evidence may be used to diagnose regressions. The now-open G7-E range
must not be used for tuning, threshold selection, or another confirmatory claim. Consolidation may
be described as simplification and correctness hardening, not as a benchmark quality improvement.

## 6. Compatibility and migration

- Existing stored feedback and receipts remain readable.
- Historical advisor and feedback policy identifiers remain unchanged in old records.
- New responses use only `deterministic-unified-v1+feedback-bayes-v1`.
- CLI callers using `--policy-version` receive a clear unsupported-argument error; no silent alias
  selects old logic.
- The HTTP schema and dashboard require no policy migration because they never exposed the v3
  selector.
- The project version changes only after implementation and release verification are approved.

## 7. Phase gates

### G8-A — Architecture freeze

Approve this single-policy boundary, retained behaviors, removals, invariants, and evidence rules.

### G8-B — Implementation and regression verification

Implement the consolidation, remove alternate runtime paths, execute software and deterministic
regression checks, and publish a verification report. Stop for sponsor review.

### G8-C — Container and release verification

After G8-B approval, rebuild and verify the rootless Podman image, update release inventories and
documentation, and publish the final single-policy evidence. Stop for sponsor review before any
release tag.

## 8. G8-A acceptance record

The sponsor approved G8-A on 2026-09-24 by responding `Approve G8-A`. This approval freezes the
design only. It does not authorize G8-B implementation, a release, a new external benchmark, or a
change to the currently running production policy.

## 9. G8-B execution record

The sponsor approved G8-B on 2026-09-24 by responding `Approve G8-B`. The implementation and
software verification are complete. The verification plan's Podman bullet conflicted with the
explicit G8-C phase boundary; the phase boundary controls. G8-B therefore verifies the built wheel,
while G8-C owns the image rebuild and hardened container checks. G8-C and any release remain
unauthorized pending the G8-B sponsor decision.
