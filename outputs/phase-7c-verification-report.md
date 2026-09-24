# Routellect Phase 7-C Verification Report

Date: 2026-09-21  
Status: G7-C approved as an engineering milestone; no subsequent phase authorized  
Production default changed: **No**  
Hidden partition opened: **No**

Sponsor approval recorded: 2026-09-21. Approval does not promote v3 or authorize G7-C2, G7-D, or
hidden-test access.

## Outcome

G7-C materially improves the deterministic software foundation, but the learned sparse router is
not strong enough for promotion. The defensible claim is:

> Routellect's experimental v3 deterministic policy is fast, offline, reproducible, and robust on
> its reviewed synthetic policy invariants. Its current sparse prompt router shows prompt-specific
> signal over a content-blind control, but does not yet preserve enough quality or reduce enough
> compute to qualify as production routing intelligence.

It is not defensible to claim that deterministic-v3 is universally “great,” best in benchmarks, or
ready to replace v2.

## Implemented candidate

- Unicode NFKC normalization and word/phrase boundary matching.
- Weighted task evidence with deterministic task-priority ties.
- Clause-bounded negation for tools, modalities, output formats, and language markers.
- Expanded synthetic detectors for AWS, GitHub, bearer-token, SSN-like, private-key, email, and
  generic key-like values.
- Conservative token upper estimates for prose, code, punctuation-heavy, and non-ASCII inputs.
- Hard context checks using the conservative estimate.
- Frozen absolute cost and latency utility transforms that do not depend on other eligible models.
- Stable configuration-ID tie-breaking throughout ranking and shortlist guards.
- Explicit `Advisor(policy_version="v3")` and CLI `--policy-version v3`; v2 remains default.
- A dependency-free 4,096-bucket sparse AdaGrad artifact trained only on the 6,045-row development
  partition, with 4,840 internal-fit and 1,205 internal-tune rows.
- Eight recorded hyperparameter attempts; no validation row was used for training or tuning.
- A 336-case task matrix plus capability, negation, substring, privacy, benign-lookalike, Unicode,
  and paraphrase fixtures.

The sparse artifact is deliberately not connected to live ranking because its promotion checks fail.

## Synthetic profiler and runtime evidence

Artifact: `g7-c-invariants-v1`  
Cases: 336 task cases, 6 positive capability cases, 6 negated capability cases, 8 synthetic privacy
cases, 6 benign privacy lookalikes, and 10 paraphrase pairs.

| Metric | Result | Gate |
|---|---:|---:|
| Task macro-F1 | 1.000 | >= 0.80 |
| Lowest task-family recall | 1.000 | >= 0.70 |
| Hard-capability recall | 1.000 | >= 0.98 |
| Synthetic privacy recall | 1.000 | = 1.00 |
| Benign privacy false positives | 0 / 6 | diagnostic |
| Eligibility stability | 1.000 | >= 0.95 |
| Recommendation p95, 2,000 runs | 0.313 ms | < 10 ms |
| Repeated stable decision payload | pass | required |
| Target-model calls | 0 | required |
| Raw prompts persisted | 0 | required |

These are project-owned, direct synthetic fixtures. Perfect scores establish regression behavior,
not independent real-world accuracy. The task matrix intentionally contains explicit signals and
must not be presented as an external benchmark.

## Sparse routing validation

Frozen pool: Qwen3-0.6B, Qwen2.5-Math-1.5B-Instruct, Qwen2.5-Math-7B-Instruct, and
Llama-3.1-70B-Instruct. Validation rows: 2,006. Utility is correctness minus 0.20 times normalized
compute. Intervals use 2,000 paired prompt-level bootstrap resamples.

| Metric | Point | 95% CI | Gate | Result |
|---|---:|---:|---:|---|
| Quality retention vs strongest fixed | 0.9130 | [0.8924, 0.9322] | lower >= 0.99 | fail |
| Compute reduction vs strongest fixed | 0.2689 | [0.2484, 0.2888] | lower >= 0.40 | fail |
| Utility difference vs fixed/v2 | +0.0027 | [-0.0081, 0.0128] | lower > 0 | fail |
| Utility difference vs share-matched content-blind | +0.0490 | [0.0370, 0.0616] | lower > 0 | pass |
| Oracle-regret reduction vs fixed/v2 | 0.0172 | [-0.0546, 0.0790] | point >= 0.20 | fail |

The router selected the 70B model for 70.49% of validation prompts, versus 49.15% in the per-query
oracle. It reduced compute, but many switches lost too much correctness. The small positive mean
utility difference over fixed/v2 is not statistically supported.

## Integrity identities

| Artifact | SHA-256 |
|---|---|
| Synthetic invariant corpus | `f6db2e8d037c59bfe5d959d2250338710392c0553b970069b518de373156c5eb` |
| Sparse strength artifact | `8c400afbdadec584ab2ae46a927a1688bf3f62bc29367f0fc6807b93b3a2fd44` |
| Profiler/runtime results | `16d39e34a749d9c3381afe2dbe908429efb4c8f7c45c9a9aebcf1a04b2e0c97a` |
| Sparse validation results | `455d7ae666541d2a97488343ffdcec5f41e2923f76b7519273eae9445fb4a219` |

The sparse artifact contains hashed coefficients, model metadata, and provenance, not raw benchmark
prompts. Its development input digest matches the G7-B manifest. Hidden rows used: zero.

## Claim blockers and residual issues

1. The joint quality/cost target is missed by a wide margin.
2. Utility improvement over fixed/v2 includes zero in its 95% interval.
3. Oracle-regret reduction is 1.7%, not the required 20%.
4. Routing evidence comes from one historical source and one frozen four-model pool; it cannot prove
   transfer to Routellect's current live catalog.
5. Synthetic profiler fixtures are reviewed regression tests, not independently labeled natural
   prompts, so their perfect score cannot establish field accuracy.
6. Regex privacy detection is a guardrail, not a complete DLP or PII classifier.
7. Token estimates are conservative heuristics rather than model-tokenizer-specific counts.
8. The G7-B TLS acquisition residual remains: source consistency was verified against the trusted
   G5 overlap, but a trusted corporate CA or independent full-source digest is still needed before
   public benchmark publication.
9. Container performance and rootless network-disabled replay belong to G7-D and have not been used
   to justify promotion.

## Verification commands

```sh
.venv/bin/ruff check src tests scripts
.venv/bin/pytest --cov=routellect --cov-report=term-missing
PYTHONPATH=src .venv/bin/python scripts/run_g7c_invariants.py
PYTHONPATH=src .venv/bin/python scripts/train_g7_sparse_policy.py
routellect advise --policy-version v3 --json "Review this Python concurrency design"
```

Final local verification: Ruff clean; 66 tests passed; total line coverage 88%.

## Recommendation

Accept the G7-C engineering work and negative result, keep v2 as production default, and reject the
current sparse router for production or hidden-test promotion. If further work is authorized, first
improve evidence diversity and the development-only learner; do not relax thresholds and do not open
the committed hidden partition.
