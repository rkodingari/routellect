# Routellect Phase 5 Verification Report

Date: 2026-09-16  
Version: 0.4.0  
Status: G5 implementation complete; sponsor review required

## Outcome

Routellect now has a reproducible, license-aware external evidence pipeline and an audited offline
advisory benchmark. It remains advisory-only: the entire run used precomputed public observations,
made zero target-model calls, requested no provider credentials, and did not change production
recommendations.

The result is deliberately not marketed as a win. At the preregistered primary cost weight
`λ=0.20`, the hybrid segment candidate exactly ties the global baseline because both recommend
Llama-3.1-70B-Instruct for every validation and hidden-test query. It satisfies the literal
non-regression gate, but adds no decision value. The engineering recommendation is **do not promote
the learned segment policy**; retain the simpler deterministic production advisor.

## External evidence protocol

- Dataset: R2-Bench revision `1b6234647a21705da4c220f339e44fbe72c69bb2`, declared MIT.
- Snapshot: 5,000 fully aligned rows, 0 exclusions, 0 missing observations.
- Stable split: 2,993 train / 1,019 validation / 988 one-time hidden test.
- Candidate pool: Qwen3-0.6B, Qwen2.5-Math-1.5B-Instruct,
  Qwen2.5-Math-7B-Instruct, and Llama-3.1-70B-Instruct.
- Compared policies: cheapest, best-quality, global utility, length segment, task segment, hybrid
  segment, seeded random, and non-deployable per-query oracle.
- Confirmatory point: `λ=0.20`, empirical shrinkage strength 20, 2,000 paired query-bootstrap
  resamples with seed 42.
- Sensitivity points: `λ=0.00`, `0.05`, `0.10`, `0.20`, and `0.40`.

## Primary results at λ=0.20

| Split / policy | Correctness (95% CI) | Normalized compute (95% CI) | Utility (95% CI) | Δ utility vs global (95% CI) |
|---|---:|---:|---:|---:|
| Validation hybrid | 0.5669 (0.5443–0.5890) | 0.9079 (0.8925–0.9230) | 0.3853 (0.3628–0.4076) | 0.0000 (0.0000–0.0000) |
| Validation global | 0.5669 (0.5443–0.5890) | 0.9079 (0.8925–0.9230) | 0.3853 (0.3628–0.4076) | reference |
| Validation cheapest | 0.2021 (0.1845–0.2212) | 0.0086 (0.0086–0.0086) | 0.2003 (0.1828–0.2195) | -0.1850 (-0.2111–-0.1600) |
| Hidden hybrid | 0.5264 (0.5021–0.5500) | 0.9118 (0.8961–0.9268) | 0.3440 (0.3203–0.3675) | 0.0000 (0.0000–0.0000) |
| Hidden global | 0.5264 (0.5021–0.5500) | 0.9118 (0.8961–0.9268) | 0.3440 (0.3203–0.3675) | reference |
| Hidden cheapest | 0.1977 (0.1802–0.2150) | 0.0086 (0.0086–0.0086) | 0.1960 (0.1784–0.2133) | -0.1481 (-0.1754–-0.1214) |
| Hidden oracle | 0.6026 (0.5813–0.6237) | 0.4837 (0.4543–0.5133) | 0.5059 (0.4868–0.5254) | +0.1618 (+0.1460–+0.1783) |

The oracle mix shows that per-query complementarity exists, but the preregistered task/length
segments are too coarse to recover it at the primary operating point. Hidden-test hybrid oracle
regret is 0.1618. The hybrid recommendation share is 100% Llama-3.1-70B-Instruct, which is the key
reason not to promote a more complex policy.

## Sensitivity result, not confirmatory

At `λ=0.40`, hybrid segmentation becomes active. On the hidden test it reaches correctness 0.3190,
normalized compute 0.2346, and utility 0.2252, versus global utility's 0.1977 correctness, 0.0086
compute, and 0.1942 utility. The utility difference is +0.0309 and the hybrid mixes approximately
46.96% Qwen3-0.6B, 31.17% Qwen2.5-Math-7B, and 21.86% Llama-3.1-70B.

This was a preregistered sensitivity point but did not receive confirmatory bootstrap intervals. It
is a useful hypothesis for a new, independently preregistered experiment—not a basis for tuning on
the now-open hidden test or changing production advice.

## Promotion decision

The machine-readable rule reports eligibility for a separate policy review because validation
utility is equal to global, no eligible slice regresses by more than 0.02, policy lookup p95 is below
25 ms, and target calls are zero. Routellect applies an additional simplicity judgment at the review
boundary: exact equality plus identical 100% model share is no practical improvement. Therefore:

- literal protocol safety gate: pass;
- practical-value review: fail;
- production policy changed: no;
- hidden test available for further tuning: no.

## Software verification

- Python lint: pass.
- Python tests: 42 passed; 88% project coverage; evidence benchmark module 96%.
- Frontend typecheck and production build: pass.
- Benchmark result SHA-256 before report generation:
  `ea07ef961d8bcfa37d7fb3bf54e1871f85d5450b1a2d95d5edbd0b07ce492c58`.
- Snapshot SHA-256:
  `5691a7fe187440106e3548a4d6f792babc168d7da5e12463743297fd661ffe7b`.

## Podman release-candidate evidence

Image `localhost/routellect:0.4.0` built successfully under rootless Podman.

| Measure | Result |
|---|---:|
| Image ID | `8d471936784b92a6c68f9bff8ba9cc70169547574e50965ed7b5dccd333b285c` |
| Image digest | `sha256:2c18bdc978b150e90e05e4c6f2d44e7acce1491a565606884bb2c1efa5555212` |
| Image size | 695,412,910 bytes |
| Readiness | 0.885 s |
| Sequential advisory throughput | 394.47 requests/s over 200 requests |
| Advisory latency | 2.27 ms p50 / 3.77 ms p95 |
| Observed container memory | 104.7 MB |
| Health | healthy |

The final container ran as UID/GID 10001, with rootless Podman, read-only root filesystem, all
default capabilities dropped, and `no-new-privileges`. The assessor was Off for this deterministic
throughput run. The QA container and named volume were removed; the versioned image was retained.
The Podman benchmark JSON SHA-256 is
`8a37ea30629191833336d6aabbcc9fdeca7fcc15c2ed4435cabde011c6218d93`.

## Limits and next evidence

- Correctness comes from R2-Bench's existing judge scores; Routellect did not independently rejudge
  responses.
- Compute is a normalized parameter-count × output-token proxy, not money, energy, or target-model
  latency.
- The first 5,000 rows may carry order bias, and tiny research/summarization slices limit subgroup
  conclusions.
- The deterministic Routellect task profiler labels many prompts `general`; richer segmentation must
  prove value on a new untouched evaluation, not this hidden test.
- The candidate pool is intentionally compact and does not represent current provider catalogs.
- Container throughput is single-client, assessor-Off performance on this development host; it is
  not a multi-client load or soak result.
- No universal “best router” or “best model” claim is supported.

G6 should focus on security and release hardening. Any next routing experiment must preregister a new
feature set and preserve a new untouched test source.
