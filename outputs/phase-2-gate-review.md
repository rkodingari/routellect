# Routellect Phase 2 Gate Review

Status: **G2 approved by sponsor; G3 authorized**  
Date: 2026-09-15

Approval recorded: 2026-09-15 (sponsor response: “Approve G2”).

## Gate recommendation

**Approve G2 with recorded deferrals.** The advisory-only MVP is implemented and its central privacy,
determinism, fallback, feedback-capture, API/CLI, and Podman claims are supported by executable
evidence. The assessor bake-off also caused a responsible design change: semantic embeddings replaced
unreliable generated classifications, and Off remains the default.

## Acceptance checklist

- [x] Catchy product name and tagline adopted: Routellect — “Know the right model before you run.”
- [x] Git repository, standards, ADR, security policy, changelog, and Apache-2.0 license added.
- [x] Exact Python/frontend direct dependencies and lock artifacts established.
- [x] Advisory-only deterministic profiler, eligibility policy, scoring, alternatives, and estimates.
- [x] Auto/Always/Off local assessor modes with timeout, circuit breaker, validation, and fallback.
- [x] Safer semantic-embedding assessor selected after a measured candidate bake-off.
- [x] Off retained as default because Auto promotion evidence is not yet statistically sufficient.
- [x] Prompt-free receipts and structured feedback capture implemented.
- [x] Web dashboard, HTTP API, and CLI implemented; deterministic parity tested.
- [x] Dated multi-provider/local starter catalog with evidence and freshness metadata.
- [x] Rootless Podman build verified as non-root, read-only, capability-dropped, healthy, and air-gapped.
- [x] Local-only requests return only local configurations.
- [x] Advice requires zero target-provider calls and no credentials.
- [x] Prompt-retention canary and database-column inspection passed.
- [x] 17 tests pass; 85.12% coverage; lint/typecheck/frontend build pass.
- [ ] Full visual/accessibility browser capture — deferred to G4; localhost is blocked by the available
      in-app browser, while HTTP assets and production build are verified.
- [ ] Statistically powered external hybrid/routing benchmark — intentionally deferred to G5; no
      superiority claim is made.
- [ ] AMD64 runtime execution — deferred to multi-architecture G6 verification.

## Material decisions requiring sponsor visibility

1. **Name:** Routellect is the proposed durable project name. A focused collision search found no
   obvious exact-name conflict, but this is not legal trademark clearance.
2. **Default mode:** deterministic Off is the honest default. Hybrid Auto/Always is usable and fully
   local, but marked experimental.
3. **Feedback:** G2 captures content-minimized outcomes. Learning from feedback begins only after G2
   approval, with the G3 replay/manual-promotion controls.
4. **Catalog:** current values are a dated starter snapshot; they are visible estimates, not a claim
   that one provider is universally best.

## Evidence package

- [G2 verification report](./phase-2-verification-report.md)
- [Requirements](./phase-0-discovery-requirements.md)
- [Architecture](./phase-1-system-architecture.md)
- [Hybrid assessor decision](./phase-1-hybrid-assessor-decision.md)
- [Threat model](./phase-1-threat-model.md)
- [API contract](./phase-1-openapi.json)
- [Benchmark protocol](./phase-1-benchmark-protocol.md)
- [Delivery plan](./phase-1-delivery-plan.md)

## Approval boundary

Approving G2 authorizes G3 only: signed/versioned catalog updates and private feedback controls plus
conservative learning. It does not authorize public deployment, publication, provider credentials,
target-model execution, or “best in benchmarks” claims.

Decision: **Approved without additional conditions.** Work may proceed through G3 and must stop at
the G3 review gate. All exclusions in the approval boundary remain in force.
