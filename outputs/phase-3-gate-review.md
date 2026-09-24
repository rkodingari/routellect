# Routellect Phase 3 Gate Review

Status: **G3 approved by sponsor; G4 authorized**  
Date: 2026-09-16

Approval recorded: 2026-09-16 (sponsor response: “Approve G3”).

## Gate recommendation

**Approve G3 with recorded deferrals.** Signed catalog lifecycle, content-minimized feedback control,
and conservative replay-gated personalization are implemented and supported by automated and real
rootless-Podman upgrade evidence. The tool remains simple, local-first, and strictly advisory-only.

## Acceptance checklist

- [x] G2 sponsor approval recorded; work stayed within the G3 authorization boundary.
- [x] Strict dated catalog schema covers model/configuration IDs, prices, capabilities, privacy,
  evidence references, uncertainty inputs, observed time, expiry, and monotonic sequence.
- [x] SHA-256 + Ed25519 signed local import with explicitly trusted public keys.
- [x] Unknown fields, bad hashes/signatures, unsafe URLs, stale imports, replayed versions, invalid
  prices, incoherent timestamps, and malformed configurations are rejected.
- [x] Atomic activation, previous-snapshot rollback, and visible builtin offline fallback.
- [x] Structured used/outcome/rating/cost/latency/pairwise feedback without prompt/free-text storage.
- [x] Dashboard/API/CLI controls for opt-out, export, reset, and catalog rollback; API supports
  individual feedback deletion.
- [x] Profile-scoped Bayesian adjustments with global shrinkage, visible support, five-outcome gate,
  and ±0.04 maximum score effect.
- [x] Chronological replay and manual promotion gate; personalization remains off by default.
- [x] Sparse feedback is inert; synthetic holdout improves or remains within non-regression tolerance.
- [x] Hard constraints execute before feedback, so learning cannot weaken privacy or feasibility.
- [x] 29 tests pass, 85% coverage, lint/typecheck/production frontend build pass.
- [x] Rootless Podman image is healthy, non-root, read-only, capability-dropped, and
  no-new-privileges.
- [x] Named-volume upgrade from 0.1.0 preserves feedback and migrates state; signed catalog rollback
  and restart persistence are verified.
- [ ] Real-world feedback benefit — deferred to G5; no superiority claim is made.
- [ ] Threshold signatures/key delegation — deferred unless release threat analysis justifies the
  added complexity.
- [ ] Full visual/accessibility dashboard QA — deferred to G4.
- [ ] Multi-architecture, SBOM, image signing, and vulnerability scan — deferred to G6.

## Material decisions requiring sponsor visibility

1. **Simple trust model:** local-file updates plus explicitly trusted Ed25519 public keys. There is no
   automatic network updater and no private-key handling.
2. **Slow learning:** collection is on, ranking personalization is off, ten events are needed for
   replay, and each task/model pair needs five outcomes before any bounded effect.
3. **Honest evidence:** synthetic replay verifies mechanics only. It does not prove better real-world
   recommendations.
4. **Assessor unchanged:** G3 feedback does not alter assessor triggering or confidence because no
   replay candidate earned promotion.
5. **Container health format:** documented Podman builds use `--format docker`, because OCI image
   format does not retain Dockerfile health-check metadata in Podman 6.1.0.

## Evidence package

- [G3 verification report](./phase-3-verification-report.md)
- [G3 architecture decision](../docs/adr/0002-signed-catalog-and-bounded-feedback.md)
- [G2 gate approval](./phase-2-gate-review.md)
- [Requirements](./phase-0-discovery-requirements.md)
- [Architecture](./phase-1-system-architecture.md)
- [Threat model](./phase-1-threat-model.md)
- [Benchmark protocol](./phase-1-benchmark-protocol.md)
- [Delivery plan](./phase-1-delivery-plan.md)

## Approval boundary

Approving G3 authorizes G4 only: learned-advisor candidates that must beat simple rules before use,
plus the polished comparison/history/benchmark dashboard and accessibility/browser verification. It
does not authorize public deployment, publication, provider credentials, target-model execution,
network catalog fetching, release signing, or “best in benchmarks” claims.

Decision: **Approved without additional conditions.** Work may proceed through G4 and must stop at
the G4 review gate. All exclusions in the approval boundary remain in force.
