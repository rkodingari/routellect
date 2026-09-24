# Routellect Phase 7-D Verification Report

Date: 2026-09-22  
Status: Complete; approved as a validation-and-candidate-freeze milestone on 2026-09-22  
Production default changed: **No**  
Existing hidden evidence opened: **No**  
New confirmatory outcomes acquired: **No**

## Outcome

The G7-C2 research candidate is reproducible, deterministic, offline, fast, container-verifiable,
and ready to freeze. It is not ready to promote. A 10,000-resample audit reconfirms that its visible
quality/compute trade-off fails the frozen production criteria, while the visible utility interval
versus the strongest fixed model still includes zero.

The defensible claim is:

> The exact frozen candidate shows prompt-specific value over a share-matched content-blind control,
> deterministic behavior across process hash seeds, 99.95% minimum recommendation stability across
> five normalization transformations, and sub-10-ms p95 inference natively and in network-disabled
> Podman. It retains 98.1% of strongest-fixed quality while reducing compute by 9.5% on already
> inspected evidence. It is an inactive research candidate, not a validated production router.

## Frozen visible-evidence audit

The candidate was not retrained, its `0.30` threshold was not reselected, and the G7-C2
share-matched control assignment was reused. Intervals use 10,000 paired prompt-level bootstrap
resamples over the already visible 2,006-row R2 validation partition.

| Metric | Point | 95% CI | Frozen gate | Result |
|---|---:|---:|---:|---|
| Quality retention vs strongest fixed | 0.9810 | [0.9672, 0.9948] | lower >= 0.99 | fail |
| Compute reduction vs strongest fixed | 0.0947 | [0.0820, 0.1081] | lower >= 0.40 | fail |
| Utility difference vs strongest fixed | +0.0072 | [-0.0002, 0.0147] | lower > 0 | fail |
| Utility difference vs share-matched content-blind | +0.0277 | [0.0186, 0.0370] | lower > 0 | pass |
| Oracle-regret reduction vs strongest fixed | 0.0457 | [-0.0013, 0.0922] | point >= 0.20 | fail |

The candidate assigns the 70B model to 88.93% of prompts. Threshold sensitivity is steep: a 0.25
threshold assigns 70B to 95.96%, while 0.35 assigns it to 79.21%. These are diagnostics only; the
threshold remains frozen at 0.30.

Strong-tier calibration has Brier score 0.2223 and ten-bin expected calibration error 0.0383 on
visible evidence. Calibration alone does not rescue the failed joint quality/compute target.

## Slice and robustness findings

- The reasoning slice is the main quality failure: 669 prompts, 93.67% quality retention, and 28.08%
  compute reduction. This is substantially below the 99% quality requirement.
- The code slice retains 99.09% quality but saves only 4.72% compute.
- The general slice retains 99.63% quality but saves only 1.35% compute.
- Recommendation stability is 100% for case, NFKC-equivalent, line-ending, and collapsed-whitespace
  transformations; outer whitespace is 99.95% stable.
- Three fresh Python processes with different hash seeds produced one byte-identical decision
  digest over 100 prompts.
- Native uncached candidate runtime is p50 0.504 ms and p95 3.882 ms. The p99 is 10.328 ms and the
  maximum is 109.951 ms on a long prompt; only the preregistered p95 criterion passes.
- No prompt cache, network call, provider credential, target-model execution, or raw prompt report
  field is present.

## Hardened Podman verification

Image `localhost/routellect:g7d-candidate` was built and verified with rootless Podman 6.1.0 on
ARM64. The exact artifact hash inside the image matches the freeze artifact.

| Check | Result |
|---|---:|
| Image digest | `sha256:7e6379a7f64d79f231ddbaf8e84cb520dc247d055eda97f7ea368016e9a58243` |
| Image size | 685,198,784 bytes |
| Candidate network | disabled (`none`) |
| Candidate p95, 2,000 calls | 0.219 ms |
| Production API p95, 500 requests | 3.717 ms |
| Ready time | 0.804 s |
| Runtime UID/GID | 10001/10001 |
| Effective capability mask | `0000000000000000` |
| Root filesystem | read-only |
| `no-new-privileges` | enabled |
| Health | healthy |
| Production default | deterministic-v2 |

The QA container and volume were removed; the local image was retained.

## Confirmatory protocol

No current hidden data will be used. If G7-E is separately authorized, the primary exact-pool test
will use R2-Bench prompt IDs 15,001–30,968 at pinned revision
`1b6234647a21705da4c220f339e44fbe72c69bb2`. Candidate decisions must be committed before outcomes
are joined, and frozen duplicate/near-duplicate exclusions must be applied before outcomes are
visible.

R2-Bench does not publish origin-dataset labels, so this test cannot establish source-level
generalization. LLMRouterBench is suitable in structure for an independent source-grouped stress
test, but remains quarantined because its result-data license is not sufficiently clear and its
model pool differs from the frozen Routellect pool.

## Reproducibility identities

| Artifact | SHA-256 |
|---|---|
| Frozen multi-source candidate | `6f32a6242fca4137cb50e515a4012a7bbea6fc01f078a12485016350aae50499` |
| G7-D validation results | `6ab1fb30368f80deeff0ef5bf3c3ecd1f5b04bbea4c789dec5742994373080b3` |
| G7-D Podman results | `ca4eac4c21c2b2c2de5d4351ea4295860aca5840559aee2f68935fc7d6876b94` |
| G7-D freeze manifest | `e39c5e783b908ed4367a263f5af3668baa584cb810e7b289f3dcb58a832cdaf6` |
| G7-D plan | `516dde8e744e5bfbf24e66a89bbb8bf4a7c959499c38f9defc941ff81ca052f1` |

Ruff is clean. The full suite passes with 70 tests and 88% total line coverage.

## Remaining blockers

1. Four of five performance promotion checks fail.
2. The reasoning slice loses 6.33% of strongest-fixed quality.
3. No untouched outcome evidence exists for this frozen candidate.
4. The exact-pool source lacks origin-dataset labels; broad source-generalization claims require a
   separate licensed, source-grouped evaluation.
5. LLMRouterBench data/result licensing and cross-pool tier mapping remain unresolved.
6. The local repository has no commit. File hashes are authoritative for this freeze, but a signed
   source-control commit containing the exact identities is required before G7-E or publication.
7. Existing command-line evidence acquisition still lacks the enterprise TLS trust chain.

## Decision

G7-D is approved as a completed validation-and-freeze milestone while the candidate remains
inactive. G7-E is not authorized. Before a G7-E request, create a source-control commit containing
the exact freeze identities and retain the existing hidden-partition prohibition.
