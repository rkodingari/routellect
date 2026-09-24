# Routellect Phase 7-C2 Verification Report

Date: 2026-09-21  
Status: Complete; approved as a bounded research milestone on 2026-09-22  
Production default changed: **No**  
Hidden evidence opened: **No**

## Outcome

The multi-source strong-tier gate is materially more conservative than G7-C and recovers most of
the fixed model's quality. It establishes prompt-specific value over a share-matched content-blind
control, but it still fails the frozen production criteria and remains inactive.

The defensible claim is:

> On already visible R2 validation evidence, the G7-C2 auxiliary preference signal improves point
> quality retention from 91.3% to 98.1% and raises mean utility while remaining deterministic,
> offline, and fast. Exploratory three-fold cross-fitting finds a small positive utility difference
> over fixed/v2, but the 97.7% cross-fitted quality retention and 9.3% compute reduction remain far
> below the production gates and no untouched confirmatory evaluation exists.

## Evidence and minimization

- Source: `routellm/gpt4_judge_battles`
- Revision: `2a1afe8d0659904c0f6f59de6179e086fdb027c7`
- Dataset license: Apache-2.0, verified from Hugging Face metadata
- Frozen source window: rows 0–19,999
- Retained locally: prompt, source row ID, derived key, winner label
- Discarded before persistence: both model responses and model-name fields
- Label counts: 1,871 strong, 13,676 economical, 4,453 tie
- Raw model responses persisted: zero
- Hidden R2 prompts or outcomes loaded: zero

The snapshot uses TLS without certificate verification because the corporate interception CA is not
available to the development runtime. Revision/license metadata checks and local SHA-256 identities
provide continuity, but this remains a publication blocker.

## Candidate design

- 8,192-bucket deterministic word unigram/bigram feature hashing.
- Weighted binary AdaGrad head estimates whether a strong tier is needed.
- Existing G7 candidate-specific regression chooses among lower tiers.
- Threshold `0.30`, selected only on the 1,205-row internal R2 development tune split.
- Final evaluated artifact trained on 6,045 R2 development rows and 20,000 auxiliary RouteLLM rows.
- R2 validation rows used for training or threshold tuning: zero.
- No runtime raw-prompt cache; prompt-derived features are computed and released per call.
- No network, model execution, provider credential, or online fitting.

## Visible validation results

This is exploratory evidence because the 2,006-row R2 validation partition was inspected during
G7-C. Intervals use 2,000 paired prompt-level bootstrap resamples.

| Metric | Point | 95% CI | Frozen gate | Result |
|---|---:|---:|---:|---|
| Quality retention vs fixed/v2 | 0.9810 | [0.9666, 0.9946] | lower >= 0.99 | fail |
| Compute reduction vs fixed/v2 | 0.0947 | [0.0813, 0.1078] | lower >= 0.40 | fail |
| Utility difference vs fixed/v2 | +0.0072 | [-0.0002, 0.0146] | lower > 0 | fail |
| Utility difference vs G7-C | +0.0045 | [-0.0036, 0.0127] | lower > 0 | fail |
| Utility difference vs share-matched content-blind | +0.0277 | [0.0183, 0.0372] | lower > 0 | pass |
| Oracle-regret reduction vs fixed/v2 | 0.0457 | diagnostic; point | >= 0.20 | fail |

The candidate selected the 70B tier for 88.93% of prompts. This explains the quality recovery and
the limited compute reduction. It is significantly better than random prompt-independent assignment
at the same model shares, but is not yet a validated improvement over simply using the strongest
fixed model.

## Grouped cross-fitted visible evidence

Three deterministic folds cover all 8,051 visible R2 rows. Each row is predicted by a model trained
without that row. Exact row keys are assigned to one fold; the threshold remains the previously
development-selected `0.30`, so this is exploratory cross-fitting rather than fully nested,
confirmatory cross-validation.

| Metric | Point | 95% CI | Frozen gate | Result |
|---|---:|---:|---:|---|
| Quality retention vs fixed/v2 | 0.9770 | [0.9701, 0.9838] | lower >= 0.99 | fail |
| Compute reduction vs fixed/v2 | 0.0930 | [0.0867, 0.0997] | lower >= 0.40 | fail |
| Utility difference vs fixed/v2 | +0.0046 | [0.0010, 0.0081] | lower > 0 | exploratory pass |
| Utility difference vs share-matched content-blind | +0.0232 | [0.0186, 0.0280] | lower > 0 | exploratory pass |

This supports genuine prompt-specific signal across visible folds. It does not override the failed
quality/cost joint target or substitute for a new untouched evaluation.

## Runtime and safety

- Uncached inference samples: 2,000
- p50: 0.475 ms
- p95: 3.709 ms
- p99: 9.810 ms
- maximum observed: 108.125 ms on a long prompt
- G7-C synthetic task/capability/privacy invariants: unchanged and passing
- Target-model calls: zero
- Raw prompt persistence: zero
- Production activation: false
- Full verification: Ruff clean; 69 tests pass; total line coverage 88%

## Reproducibility identities

| Artifact | SHA-256 |
|---|---|
| Minimized RouteLLM snapshot | `41d7a8147ff633d2f4187cbf77c939bfda4aa32d702eadf04916427c620c7d36` |
| RouteLLM snapshot manifest | `57bf18c0bacbc6afb04733d6d0abc8be3c6c5828797096f44c638c3a2edb1df8` |
| Multi-source sparse artifact | `6f32a6242fca4137cb50e515a4012a7bbea6fc01f078a12485016350aae50499` |
| Machine-readable G7-C2 results | `a488894e85de4d208bd99670744468deca92032efaa6eb410cf4a1eb0c8e09e9` |

## Claim blockers

1. Quality retention, compute reduction, and oracle-regret reduction still fail.
2. The single visible-validation utility comparison includes zero; grouped cross-fitting is positive
   but not fully nested and remains exploratory.
3. The compute target is missed by more than 30 percentage points.
4. The visible partitions are no longer untouched and cannot support a confirmatory claim.
5. Cross-source prompt overlap with the sealed R2 hidden partition cannot be ruled out without
   opening hidden prompts. That partition must not be used for this candidate unless G7-D resolves
   group disjointness safely.
6. GPT-4-versus-Mixtral preference labels are a strength proxy, not direct evidence for the current
   Routellect catalog or the frozen R2 four-model pool.
7. One auxiliary source does not establish broad real-world transfer.
8. The TLS trust-chain residual remains unresolved.

## Decision

G7-C2 is approved as a useful research improvement, with the artifact kept inactive. This decision
does not authorize the existing hidden test. G7-D was later authorized separately and completed on
2026-09-22; it designed a new untouched evaluation and froze the candidate without opening the
current hidden partition or promoting v3.
