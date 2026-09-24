# ADR 0005: Keep deterministic-v3 explicit and reject sparse-router promotion

Date: 2026-09-21  
Status: Accepted; reaffirmed by G7-D candidate freeze on 2026-09-22

## Context

G7-C strengthens deterministic prompt profiling and scoring while evaluating whether a frozen,
development-trained sparse model can add prompt-specific routing value. The sparse model uses no
runtime network, target-model call, provider credential, prompt persistence, or hidden evidence.

The profiler passes the project-owned synthetic invariants. The sparse router beats a share-matched
content-blind control on the frozen validation set, but it fails the preregistered quality-retention,
compute-reduction, fixed-baseline utility, and regret-reduction gates.

## Decision

- Keep deterministic-v2 as the API, dashboard, and CLI default.
- Expose deterministic-v3 only through the explicit CLI `--policy-version v3` flag.
- Retain v3 hard-policy improvements for review: boundary-aware weighted matching, negation,
  expanded synthetic privacy patterns, conservative context sizing, stable absolute utility
  transforms, and configuration-ID tie-breaking.
- Retain the sparse artifact and validation output as reproducible evidence, but do not use the
  artifact in live ranking or describe it as production-ready.
- Do not open the committed hidden partition unless a later candidate passes the validation freeze
  gate and receives separate sponsor approval.

G7-D froze the G7-C2 artifact without changing this decision. The candidate passed deterministic,
privacy, runtime, software, and hardened Podman freeze checks, but still failed the quality,
compute, fixed-baseline utility, and regret promotion criteria on visible evidence. The original
hidden partition remains prohibited; any future confirmatory run must use the separately
preregistered untouched range and a new sponsor gate.

## Consequences

The product gains a safer experimental deterministic implementation without silently changing user
advice. The project also preserves an honest negative result. A future candidate needs stronger,
legally usable multi-source evidence or a materially better dependency-free classifier; threshold
relaxation after seeing validation results is not allowed.
