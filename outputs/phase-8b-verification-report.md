# Routellect Phase 8-B Single-Policy Verification Report

Date: 2026-09-24
Status: Implementation approved; G8-C authorized
Release authorized: **No**
Container verification: **Authorized at G8-C**

## Outcome

Routellect now has one deterministic recommendation implementation. The dashboard, API, CLI, and
built-in benchmark all instantiate the same `Advisor`, which calls one `deterministic_profile`, one
hard-constraint filter, and one ranking/shortlist path. The resulting audit identifier is
`deterministic-unified-v1+feedback-bayes-v1`; it is not user-selectable.

The implementation preserves the supported v2 constraints, objective weights, relative
cost/latency scoring, Pareto behavior, shortlist guards, evidence penalties, and bounded feedback.
It ports only reviewed interpretation hardening: Unicode normalization, bounded weighted matches,
local negation, expanded privacy canaries, conservative token sizing, and explicit reason codes.

The rejected absolute-ranking experiment and sparse router were not merged. The v3 CLI switch,
alternate advisor branch, second profiler entry point, sparse runtime module, strength artifacts,
and policy-training/validation implementations have been removed. Immutable G7 reports, hashes,
acquisition code, and Git history remain available for audit.

## Acceptance evidence

| Check | Result |
|---|---:|
| Ruff | Passed |
| Python tests | 71 passed, 0 failed |
| Line coverage | 87.47% (80% required) |
| Deterministic invariant corpus | Passed |
| Privacy recall/lookalike canaries | Passed |
| Hard privacy/budget/latency/capability/quality constraints | Passed |
| Score reconciliation | Passed |
| Stable tie-breaking | Passed |
| Cross-process determinism | Passed |
| Frontend TypeScript check | Passed |
| Frontend production build | Passed |
| Local API/dashboard smoke test | Passed; unified policy returned |
| Python wheel build | Passed |
| Alternate policy/sparse files in wheel | 0 |
| Secret findings | 0 unrecognized; 3 exact synthetic canaries acknowledged |

Two warnings come from the pinned FastAPI/Starlette testing stack: Starlette's `httpx` test-client
compatibility layer and an AnyIO alias are deprecated. They do not originate in Routellect code and
do not affect this policy decision.

## Built-in software benchmark

The seven-fixture, non-executing benchmark reports:

- task-family accuracy: 100%;
- Pareto-efficient primary rate: 100%;
- quality-specialist shortlist coverage: 100%;
- maximum score reconciliation error: `1.11e-16`;
- mean advisor latency: 0.616 ms;
- p95 advisor latency: 2.484 ms;
- target-provider calls: zero; and
- persisted raw prompts: zero.

This is a software regression check, not an external model-quality benchmark.

## Distribution inspection

The isolated wheel is 117,514 bytes with SHA-256
`2a17d3bb450db1af160b4959987256ecba1c02205957111b2a889f0541ffade0`. It contains one
`advisor.py`, one `profiler.py`, one `cli.py`, the deterministic invariant corpus, and no sparse
module or G7/G7-C2 strength artifact.

Source identities at verification:

- `advisor.py`: `d9f7324fb2a7e070124487bac62390c419d89e9651205495ccb333aedbdeaccc`
- `profiler.py`: `68e333e98e038370c1d945b6c510b29deffcc526675646504f56322063b4fe5f`

## Evidence boundary

The open G7-E range was not used for tuning, threshold selection, or this verification. No new
external effectiveness claim is made. The valid claim is narrower: Routellect has one deterministic
policy whose software invariants and safety constraints pass the recorded checks.

The architecture plan's validation list accidentally mentioned Podman checks under G8-B while its
phase-gate section reserved the rebuild and hardened container verification for G8-C. The phase-gate
boundary controls: G8-B verifies the wheel; G8-C must rebuild and verify the rootless container
before any release decision. No Podman result is claimed here.

## Recommendation

G8-B was approved on 2026-09-24. G8-C container/release verification is authorized, but a release
tag and benchmark-quality claim remain unauthorized.
