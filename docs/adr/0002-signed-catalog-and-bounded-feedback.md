# ADR 0002: Signed offline catalogs and bounded private feedback

- Status: Implemented; G3 approved
- Date: 2026-09-15

## Context

Model identifiers, prices, capabilities, and privacy terms change. Blind network refresh would weaken
Routellect's private, offline operating model, while an unsigned local import could silently alter
advice. Outcome feedback can improve recommendations, but sparse or poisoned clicks can also create
unstable rankings and false confidence.

## Decision

Catalog updates are local-file imports only. Each envelope contains strict schema version 1.0
metadata, a monotonic sequence, observed/expiry timestamps, a SHA-256 digest, signer key ID, and an
Ed25519 signature over Routellect's documented canonical JSON encoding. Only explicitly trusted
public keys are accepted. Activation is atomic, the prior signed snapshot is retained, a monotonic
high-water sequence survives rollback/corruption, rollback is one command, and the package's builtin
snapshot is the offline fallback. Inspired by TUF, a client will not activate an older/equal sequence
or an already expired snapshot.

Feedback stores structured outcomes but no prompt or free text. Collection is locally controllable.
Personalization is profile-scoped and off by default. Manual promotion first runs a chronological
holdout replay and rejects regression beyond a 0.005 Brier tolerance. Even after promotion, a
task/model pair needs five usable outcomes; estimates shrink toward a Beta(8,2) empirical global
prior and ranking influence is capped at ±0.04. Feedback never changes privacy, capability, context,
budget, latency, or quality-floor eligibility.

Assessor-trigger and feature-confidence calibration remain unchanged in G3. Any future candidate
must use offline replay and explicit promotion rather than learning online.

## Consequences

- Runtime remains network-free and advisory-only.
- Catalog corruption, tampering, replay, expiry, malformed estimates, and unsafe links fail closed to
  the builtin snapshot or leave the current signed snapshot untouched.
- Users can inspect, export, delete, reset, or stop collecting all feedback.
- Learning is intentionally slow and modest; it favors safety and auditability over rapid adaptation.
- A single public-key dependency is added; no provider SDK or target-model adapter is introduced.

## Research basis

- The `cryptography` project recommends Ed25519 when legacy interoperability is not needed and
  specifies verify-or-raise behavior.
- The Update Framework requires trusted metadata versions not to move backward and expired metadata
  not to be activated, providing the rollback/freeze-defense pattern adapted here without adding a
  network updater.
