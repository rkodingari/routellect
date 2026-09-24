# Routellect Phase 7-E Verification Report

Date: 2026-09-24  
Status: Complete; awaiting sponsor decision  
Promotion recommendation: **Reject**  
Production activated: **No**  
Existing hidden partition opened: **No**

## Outcome

The one-time untouched exact-pool evaluation is complete. The candidate demonstrates real
prompt-specific utility: it beats both the frozen strongest-fixed baseline and the share-matched
content-blind control with positive paired 95% bounds. It nevertheless fails the preregistered
quality-retention, compute-reduction, Oracle-regret, and major-slice requirements. The conjunctive
promotion rule therefore rejects it automatically.

The defensible claim is:

> On 15,634 overlap-screened, previously unused R2-Bench prompts, the frozen deterministic
> candidate improves mean utility over always using Llama-3.1-70B and over random assignment at the
> same model shares. It retains 97.59% of fixed-model quality and reduces normalized compute by
> 9.69%, but both fall far short of the frozen production targets. Reasoning quality retention is
> only 92.79%. The candidate is useful research evidence, not a production router.

## Blinding and evidence sequence

1. Candidate code, overlap rules, threshold, controls, and evaluation code were frozen in local
   commit `d9078239687a86a4b3c2a9ae0babb0db3bad11c5`.
2. R2-Bench prompt IDs 15,001–30,968 were acquired from pinned revision
   `1b6234647a21705da4c220f339e44fbe72c69bb2`.
3. Of 15,968 rows, 63 exact development overlaps, 223 fuzzy lexical overlaps, and 48 duplicate
   evaluation prompts were excluded without replacement.
4. Choices for all 15,634 eligible prompts were committed at SHA-256
   `20938716e9ef0c9ce5501af4cae6db582f2b42139f4a8dc68dc494c0f27528b3` before outcomes were
   acquired.
5. Four aligned minimized model-outcome files produced snapshot SHA-256
   `cb694fc093746365820505186d932139ce7ae6081512a991fcc96ad5989257db`.
6. A one-time receipt was created before metric computation. It records one completed run and
   mechanically prevents rerun.

No raw responses, golden answers, templated prompts, judge rationales, target-model calls, or
provider credentials were retained. The old 1,949-row hidden partition was not used.

## Confirmatory results

Intervals use 10,000 paired prompt-level bootstrap resamples.

| Metric | Point | 95% CI | Frozen gate | Result |
|---|---:|---:|---:|---|
| Quality retention vs frozen strongest fixed | 0.9759 | [0.9710, 0.9808] | lower >= 0.99 | fail |
| Compute reduction vs frozen strongest fixed | 0.0969 | [0.0922, 0.1017] | lower >= 0.40 | fail |
| Utility difference vs frozen strongest fixed | +0.0047 | [0.0021, 0.0072] | lower > 0 | pass |
| Utility difference vs share-matched content-blind | +0.0221 | [0.0189, 0.0254] | lower > 0 | pass |
| Oracle-regret reduction vs frozen strongest fixed | 0.0302 | [0.0134, 0.0462] | point >= 0.20 | fail |

Llama-3.1-70B-Instruct is also the empirical Best Single model for both quality and utility on this
evaluation, validating the frozen baseline choice.

## Policy behavior

| Policy | Mean quality | Normalized compute | Mean utility |
|---|---:|---:|---:|
| Frozen G7-C2 candidate | 0.5229 | 0.8193 | 0.3590 |
| Llama-3.1-70B fixed | 0.5358 | 0.9073 | 0.3544 |
| G7-C single-source | 0.4869 | 0.6655 | 0.3538 |
| Share-matched content-blind | 0.4981 | 0.8060 | 0.3369 |
| Lower-tier only | 0.2609 | 0.0384 | 0.2532 |
| Oracle | 0.6037 | 0.4714 | 0.5095 |

The candidate chooses Llama-3.1-70B for 88.60% of prompts. Strong-tier calibration has Brier score
0.2252 and ten-bin expected calibration error 0.0246. The large remaining Oracle gap shows that the
model-recall problem is not solved by the current sparse strength head.

## Major slices

Every slice with at least 100 rows required a quality-retention lower bound of 0.95.

| Slice | Rows | Quality retention | 95% CI | Result |
|---|---:|---:|---:|---|
| Reasoning | 5,409 | 0.9279 | [0.9114, 0.9444] | fail |
| General | 8,941 | 0.9950 | [0.9933, 0.9967] | pass |
| Code | 506 | 0.9900 | [0.9753, 1.0034] | pass |
| Writing | 478 | 0.9933 | [0.9827, 1.0000] | pass |
| Research | 114 | 1.0000 | [1.0000, 1.0000] | pass |
| Low difficulty | 14,492 | 0.9738 | [0.9685, 0.9792] | pass |
| Medium difficulty | 1,035 | 0.9979 | [0.9926, 1.0024] | pass |
| High difficulty | 107 | 1.0000 | [1.0000, 1.0000] | pass |

The reasoning failure is material and repeats the visible-validation warning. It is not a marginal
threshold miss: its upper interval bound remains below the 0.95 slice floor.

## Decision audit

| Frozen condition | Result |
|---|---|
| Quality retention | fail |
| Compute reduction | fail |
| Utility vs fixed | pass |
| Utility vs content-blind | pass |
| Oracle-regret reduction | fail |
| All major slices | fail |
| G7-D software/Podman checks remain valid | pass |
| Exactly one outcome evaluation | pass |

Promotion recommendation is `false`. No threshold, exclusion, feature, artifact, baseline, or gate
was changed after outcomes became available.

## Evidence identities

| Artifact | SHA-256 |
|---|---|
| Eligible prompt snapshot | `7074270b7d925e29e629cc05c38671742e988dfc98aeb2c1663b5b735b5a1273` |
| Prompt manifest | `323c3e5e2524c3ac43703302154e1e8977dbc463f9ec6203ea98cb27cd4cb619` |
| Prompt-free exclusions | `284445fb1b1a7fe75488e3e56d94deb6910cf0dce06a11aaa1c5143dc0915a03` |
| Recommendation commitment | `20938716e9ef0c9ce5501af4cae6db582f2b42139f4a8dc68dc494c0f27528b3` |
| Recommendation manifest | `b6ada672051dd805c6e63c7ded5d1bc037ea9bdacc1bd7af5a03717240643fd7` |
| Minimized outcomes | `cb694fc093746365820505186d932139ce7ae6081512a991fcc96ad5989257db` |
| Outcome manifest | `4200daccf8f87a9b3e803bd80cad8c9927062c6111682fff7b1bbfa7309df8e6` |
| One-time receipt | `fe191984e9ec06b8fc6c35317a81d54e1bf8dc4a090d9006a2004515ea4ea51e` |
| Machine-readable result | `63d2c8447cb657ac95908850b60ae8ec6f0f4f34f0936f9fcdc8836f62fe66cf` |

## Limitations

1. R2-Bench does not expose origin-dataset labels, so this confirms an untouched prompt range, not
   cross-source generalization.
2. Fuzzy overlap screening is lexical and may miss semantic paraphrases with different wording.
3. Outcomes are historical judge scores for four exact models at one 100-token budget.
4. Parameter-token compute is a stable proxy, not current price, latency, energy, or carbon impact.
5. Command-line source transport still lacks the enterprise TLS trust chain; revision and local
   hashes provide continuity but not normal end-to-end certificate verification.
6. The source-control freeze is local because this checkout has no configured remote.

## Recommendation

Approve G7-E as a completed one-time evaluation with a rejected promotion. Keep deterministic-v2
as production default and retain the candidate only as disabled research evidence. Do not tune on
this now-open evaluation range or proceed to G7-F release hardening for v3.
