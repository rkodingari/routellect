# Routellect Phase 7 Deterministic Routing Intelligence Plan

Date: 2026-09-21  
Status: G7-A through G7-D approved; G7-E not authorized  
Target: Routellect 0.6.0 candidate

## 1. Objective

Strengthen Routellect's deterministic advisor so that it remains fast, private, auditable, and
policy-controlled while making materially better prompt-specific recommendations than the current
`deterministic-v2+feedback-bayes-v1` baseline.

The phase does not turn Routellect into an inference gateway. It will not call recommended models,
store provider credentials, retain user prompts by default, or permit a semantic assessor or learned
signal to override privacy, capability, context, quality, budget, or latency constraints.

The primary confirmatory question is:

> On a new untouched outcome set, can deterministic-v3 retain at least 99% of the strongest fixed
> model's quality while reducing estimated cost by at least 40%, with zero hard-constraint
> violations and statistically supported prompt-specific value over deterministic-v2?

## 2. Why a new phase is required

The current deterministic path is a strong safety baseline but not a proven prompt router:

- task and capability detection use unweighted substring matching;
- difficulty is inferred from prompt length and six phrases;
- token count is estimated as whitespace-delimited words multiplied by 1.35;
- quality is selected primarily by one task-family key;
- cost and latency utilities are normalized against the currently eligible candidate set;
- confidence is heuristic rather than calibrated against held-out outcomes;
- the seven built-in task fixtures contain obvious keywords and are software checks only; and
- the G5 task/length policy collapsed to the same model as the global baseline at the primary point.

The G5 hidden test is open and cannot be reused for tuning or a new confirmatory claim.

## 3. Research basis and evidence candidates

Phase 7 will use only source revisions and rows whose redistribution and evaluation terms have been
verified and recorded before acquisition.

| Source | Proposed role | Current eligibility decision |
|---|---|---|
| [RouterBench](https://github.com/withmartian/routerbench) | Development outcome corpus and cross-domain replay | Candidate; repository is MIT, but each underlying dataset still needs a license manifest |
| [R2-Bench](https://github.com/UCF-ML-Research/R2-Router) | Additional development data from rows never used in G5 | Candidate; MIT declaration, but unused row identities must be frozen before scores are inspected |
| [LLMRouterBench](https://github.com/ynulihao/LLMRouterBench) | Modern-model and cross-domain external evidence | Quarantined until repository and dataset licenses are verified |
| [RouterArena](https://github.com/RouteWorks/RouterArena) | Untouched external evaluation | Evaluation only; its data or labels must never be used to train, fit, or tune Routellect |
| Project-owned adversarial fixtures | Privacy, capability, negation, ambiguity, token estimation, and harmless paraphrase invariants | Allowed; synthetic values only, no real personal information or credentials |

Research findings shaping the protocol:

- RouterBench provides more than 405,000 recorded inference outcomes for multi-model routing.
- LLMRouterBench reports that no model dominates all domains and that substantial oracle gaps remain.
- RouterArena measures accuracy, cost, optimality, robustness, and latency and explicitly prohibits
  fitting on its evaluation labels.
- RouteLLM shows that preference-conditioned routing must be compared with fixed and random
  baselines at matched quality/cost operating points.

Public benchmark prompts remain evidence artifacts, not user feedback. Raw model answers and judge
rationales will not be retained unless essential for a deterministic metric and explicitly approved.

## 4. Proposed deterministic-v3 design

### 4.1 Lexical policy layer

Replace raw substring counts with a versioned feature specification:

- Unicode-normalized, case-folded token and phrase matching;
- word boundaries for lexical terms;
- weighted exact phrases and unambiguous language/tool markers;
- explicit negation handling such as `do not browse` and `without tools`;
- positive and negative evidence per label;
- multi-label task and capability scores rather than a single early winner;
- stable tie rules independent of dictionary or catalog order; and
- reason codes that identify the features affecting the result without echoing prompt text.

### 4.2 Deterministic sparse classifier

Add a small, frozen, explainable linear classifier trained offline on development-only data:

- word and character n-grams hashed with a fixed seed;
- one-vs-rest task and capability heads;
- candidate-strength or difficulty head derived from development outcomes;
- coefficients, intercepts, feature schema, source manifest, and SHA-256 identity shipped as a
  signed/versioned artifact;
- deterministic standard-library inference or a dependency-free exported representation; and
- no online fitting, remote inference, or runtime dataset access.

The lexical layer remains authoritative for high-precision hard capabilities and privacy signals.
The linear classifier improves semantic recall but cannot remove a requirement found by policy.

### 4.3 Difficulty and uncertainty

Difficulty will use observable requirements rather than prompt length alone:

- number and interaction of requested operations;
- code, mathematics, tool, modality, and structured-output requirements;
- verification, citation, exhaustive-search, and constraint markers;
- estimated input/output size and context pressure;
- conflicting or underspecified instructions; and
- development-only evidence for the least-expensive tier meeting a frozen quality threshold.

Confidence will be calibrated on validation only. Low-confidence prompts will keep an explainable
shortlist and receive a visible `needs_clarification` or `semantic_review_suggested` status instead
of an unjustifiably confident primary claim.

### 4.4 Token, cost, and latency estimates

- Replace the single words-times-1.35 estimate with a conservative estimator that distinguishes
  prose, code, structured data, and non-ASCII text.
- Store an uncertainty range, not only a point estimate.
- Reject a candidate when the conservative upper estimate exceeds its context window.
- Calculate request cost from the configuration's input/output prices and estimated ranges.
- Replace eligible-set max normalization with frozen, documented utility transforms so adding an
  irrelevant expensive model cannot change existing pairwise scores.
- Model advisor-visible latency as a documented function of fixed overhead and input/output size
  when evidence supports it; otherwise expose the estimate as a coarse prior.

### 4.5 Ranking authority

The final ordering remains deterministic and follows this immutable order:

1. effective privacy policy;
2. required capabilities and deployment constraints;
3. conservative context fit;
4. minimum quality, maximum cost, and latency SLO;
5. task/difficulty/capability-conditioned quality evidence;
6. objective utility and uncertainty penalty;
7. Pareto-front restriction for the primary choice;
8. specialist, economical, and private/fast shortlist guards; and
9. stable model/configuration identifier as the final tie-breaker.

Feedback remains off by default, support-gated, manually promoted, bounded, audited, and unable to
alter eligibility.

### 4.6 Optional semantic assessor

The local semantic assessor remains experimental and Off by default during deterministic-v3
development. A dedicated embedding model may later compete as a separate ablation, but it receives
no production promotion from this plan. Its value must exceed deterministic-v3 and a share-matched
content-blind control on untouched evidence.

## 5. Dataset and split protocol

### 5.1 Two distinct evaluation tracks

1. **Profiler track** — task, capability, difficulty/strength, privacy, ambiguity, and paraphrase
   stability.
2. **Routing track** — per-query candidate outcomes, cost, utility, regret, model share, and
   constraint compliance.

Passing one track does not imply passing the other.

### 5.2 Leakage controls

- Freeze source revisions, licenses, row IDs, checksums, model identities, and transformations
  before outcome inspection.
- Keep duplicate and paraphrase groups in one split.
- Use source-grouped evaluation so dataset-specific vocabulary cannot create a hidden shortcut.
- Exclude source/dataset name, answer, judge rationale, target label, and candidate outcome from
  runtime features.
- Separate development, validation, and hidden-test files physically and in code paths.
- Permit one hidden-test run after a signed validation decision.
- Record every exclusion and missing candidate outcome.

### 5.3 Synthetic invariant suite

Add at least 300 reviewed, versioned cases covering:

- substring traps such as `capital`, `rapid`, and `description`;
- negated tools, modalities, formats, and languages;
- mixed tasks and conflicting objectives;
- code, JSON, Unicode, long-context, and terse prompts;
- synthetic API keys, private-key markers, emails, and benign lookalikes;
- harmless paraphrases whose eligibility and recommendation should remain stable; and
- prompts that should explicitly remain `general` or low confidence.

Synthetic cases test invariants and failure handling; they cannot establish routing superiority.

## 6. Compared systems

All systems receive the same frozen candidates, constraints, evidence, and split:

1. strongest fixed model selected on development only;
2. cheapest fixed model;
3. seeded random eligible model;
4. current `deterministic-v2`;
5. lexical-policy-only v3;
6. sparse-classifier-only diagnostic;
7. full `deterministic-v3`;
8. share-matched content-blind control;
9. optional embedding-assisted v3 ablation; and
10. per-query oracle, which is never deployable.

## 7. Metrics

### 7.1 Profiler

- task macro-F1 and per-family precision/recall;
- capability precision/recall, with recall emphasized for hard requirements;
- difficulty/strength accuracy and ordinal error;
- privacy detector precision/recall on synthetic values;
- uncertainty calibration, Brier score, and expected calibration error;
- selective risk at 50%, 70%, 80%, 90%, and 100% coverage;
- recommendation and eligibility stability under harmless paraphrases; and
- failure slices for length, code, Unicode, mixed tasks, ambiguity, and negation.

### 7.2 Routing

- quality retention versus validation-selected strongest fixed model;
- estimated cost reduction at matched quality;
- utility and paired difference versus fixed, v2, and content-blind controls;
- top-1 success and top-3 oracle coverage;
- regret to the eligible per-query oracle and regret reduction versus v2;
- model-selection share and collapse diagnostics;
- rare-specialist recall and worst supported task-family utility;
- hard-constraint violations; and
- score stability when irrelevant dominated catalog entries are added.

### 7.3 Product

- deterministic p50/p95/p99 latency and throughput;
- startup time, peak memory, and container image size;
- raw prompts persisted, provider calls, credentials requested, and network attempts;
- byte-stable ranking, scores, and reason codes across repeated runs, excluding IDs/timestamps; and
- compatibility with rootless, network-disabled Podman operation.

## 8. Frozen acceptance criteria

Production promotion requires all of the following on untouched evidence:

1. zero privacy, capability, context, budget, or latency hard-constraint violations;
2. lower 95% confidence bound for quality retention versus the strongest fixed model at least 0.99;
3. lower 95% confidence bound for estimated cost reduction at least 0.40;
4. paired utility improvement over deterministic-v2 with lower 95% confidence bound above zero;
5. paired utility improvement over the share-matched content-blind control with lower bound above
   zero;
6. at least 20% reduction in mean oracle regret versus deterministic-v2;
7. profiler task macro-F1 at least 0.80 and no supported task-family recall below 0.70;
8. hard-capability recall at least 0.98 and privacy-sensitive synthetic recall equal to 1.00;
9. at least 95% eligibility stability under harmless paraphrases;
10. deterministic recommendation p95 below 10 ms on the named reference machine;
11. zero target-provider calls, zero raw-prompt persistence, and successful air-gapped operation; and
12. complete reproducibility from a frozen manifest and checksums.

If the quality/cost joint target is infeasible for the selected candidate pool, no threshold will be
relaxed after hidden-test inspection. The report will record the miss, and deterministic-v2 remains
the production default.

Final confidence intervals use at least 10,000 paired prompt-level bootstrap resamples, grouped by
source/paraphrase identity where applicable. Secondary comparisons use Holm correction.

## 9. Gated delivery plan

### G7-A — Protocol and architecture approval (current gate)

Deliver this plan, research references, scope boundaries, risks, and acceptance criteria. No
production implementation or benchmark acquisition occurs before sponsor approval.

### G7-B — Evidence acquisition and baseline audit

After G7-A approval:

- resolve per-dataset licenses and terms;
- freeze source revisions and row manifests;
- acquire content-minimized evidence;
- create duplicate-safe splits and checksums;
- run deterministic-v2 and fixed/random/oracle baselines; and
- stop for sponsor review before feature or rule development.

### G7-C — Deterministic-v3 implementation

After G7-B approval, implement lexical policy, sparse classifier artifact, conservative token
estimation, calibrated uncertainty, stable utility transforms, tests, and dashboard explanations.
Development and validation data only; hidden test remains inaccessible. Stop for review.

### G7-D — Validation and candidate freeze

Run all validation ablations, robustness tests, software tests, and Podman performance checks.
Freeze code, catalog/evidence adapter, thresholds, artifact identities, promotion rule, and a new
untouched evaluation protocol. The existing hidden partition remains prohibited. Separate sponsor
approval is required before G7-E can acquire or join any new outcomes.

### G7-E — One-time hidden test and promotion decision

Acquire the newly preregistered untouched range, commit candidate recommendations before outcomes
are joined, execute the outcome evaluation once, publish every metric and failure slice, and make
an automatic pass/fail recommendation. The existing hidden partition is not eligible. Production
promotion still requires explicit sponsor approval.

### G7-F — Release hardening

If promoted, update documentation, architecture diagrams, SBOM/model-data inventory, release
manifest, migration/rollback plan, and multi-architecture Podman evidence. If rejected, retain the
candidate behind a disabled experimental flag or remove it according to sponsor direction.

## 10. Risks and controls

| Risk | Control |
|---|---|
| Dataset-license ambiguity | Quarantine source until a per-dataset license and terms record exists |
| Dataset identity leakage | Source-grouped splits and dataset name excluded from features |
| Hidden-test tuning | One-time execution after signed candidate freeze |
| Model-pool mismatch with live catalog | Claims limited to exact frozen pool; no automatic transfer |
| Rules overfit benchmark vocabulary | Paraphrase groups, cross-source tests, and adversarial invariants |
| Classifier becomes opaque | Sparse linear artifact, coefficient/reason audit, bounded influence |
| Candidate-set normalization instability | Frozen absolute transforms and dominated-entry stability test |
| Privacy regression | Policy authority, synthetic secret/PII tests, air-gapped execution |
| Added operational complexity | Dependency-free runtime artifact and explicit rollback to v2 |

## 11. Non-goals

- Calling or proxying a recommended model.
- Storing cloud-provider credentials.
- Online reinforcement learning or automatic policy promotion.
- Tuning on RouterArena evaluation labels.
- Reusing the opened G5 hidden test for a new confirmatory claim.
- Claiming universal or current-provider superiority from historical benchmark outcomes.
- Replacing deterministic hard policy with an LLM decision.

## 12. Gate decision requested

Approve G7-A to authorize G7-B only: dataset license verification, content-minimized evidence
acquisition, frozen split creation, and baseline measurement. Approval does not authorize
deterministic-v3 implementation, hidden-test access, production promotion, provider credentials,
target-model execution, public deployment, or publication.
