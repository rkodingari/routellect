# Routellect Phase 4 Verification Report

Date: 2026-09-16  
Version: 0.3.0  
Advisor: `deterministic-v2+feedback-bayes-v1`  
Scope: explainable learned-advisor safeguards and polished evidence dashboard

## Executive result

G4 implementation is complete and ready for sponsor review. Routellect remains advisory-only: it
does not execute a recommended model, request provider credentials, proxy prompts, or incur target
model cost. The primary recommendation is now restricted to the quality/cost/latency Pareto front;
the shortlist protects a lowest-cost option and the highest-quality specialist when distinct; and
every displayed score reconciles to visible contributions.

The only learned ranking signal is still conservative local feedback. It is off by default, bounded
to ±0.04, manually promoted, checked on chronological aggregate and per-task slices, identified by a
stable policy version and SHA-256 digest, audited on every attempt, and explicitly reversible.

## Delivered behavior

- Uncertainty penalties combine prompt ambiguity and model-prior uncertainty.
- Pareto dominance is computed after all privacy, capability, context, cost, latency, and quality
  hard constraints.
- The primary choice must be Pareto-efficient.
- Three useful roles replace three near-duplicate ranks: objective winner, economic alternative, and
  quality specialist or local/fast alternative.
- Quality, cost, latency, evidence risk, uncertainty, and optional feedback contributions exactly sum
  to the published score.
- Confidence falls as prompt/prior uncertainty rises and is capped at 0.92.
- Feedback policy promotion uses a chronological Brier replay and rejects aggregate or per-task
  regression beyond 0.005.
- Promotion attempts—including insufficient-data and rejection decisions—receive immutable audit
  receipts. Rollback is explicit and audited.
- Dashboard now has Advisor and Evidence & Learning views, comparison table, score explanations,
  catalog provenance/freshness, prompt-free feedback history, promotion audit, rollback, local
  benchmark explorer, and prompt-free Markdown/JSON recommendation exports.
- Keyboard focus styling, semantic headings/navigation/tables, a skip link, live status regions,
  reduced-motion support, and responsive breakpoints are included.

## Automated verification

| Check | Result |
|---|---:|
| Python tests | 34 passed |
| Statement coverage | 86% total |
| Feedback learner coverage | 100% |
| Lint | Passed |
| TypeScript + production build | Passed |
| Production JS | 239.63 kB / 74.24 kB gzip |
| Production CSS | 12.96 kB / 3.92 kB gzip |

Focused tests prove:

- recommendation scores equal the sum of their explanation contributions;
- every built-in-fixture primary is Pareto-efficient;
- a quality specialist remains in a cost-focused shortlist;
- prompt uncertainty reduces confidence;
- sparse feedback is inert and profile-isolated;
- successful/unchanged replays can be promoted only through the manual endpoint;
- a regressing task slice is rejected and personalization stays off;
- every promotion attempt is audited and rollback disables the policy;
- legacy receipts migrate with the prior advisor identity;
- raw prompt canaries do not enter receipts, feedback exports, or SQLite;
- advice makes zero target-provider network calls.

## Built-in benchmark

The frozen software fixture produced:

| Metric | Result |
|---|---:|
| Fixtures | 7 |
| Task-family accuracy | 100% |
| Pareto-safe primary rate | 100% |
| Specialist shortlist coverage | 100% |
| Score reconciliation maximum error | 1.11e-16 |
| Mean advisor latency | 0.219 ms |
| P95 advisor latency | 0.549 ms |
| Target-provider calls | 0 |
| Raw prompts persisted | 0 |

This is a software-integrity benchmark, not evidence that Routellect identifies the universally best
model. The frozen machine-readable result is in `phase-4-benchmark-result.json`.

## Live browser review

A production build was served locally and exercised through a real desktop browser:

- advisor page loaded catalog/settings/history/audit/benchmark APIs successfully;
- submitting the default concurrency prompt produced three distinct options with Pareto badges,
  reasons, confidence, estimate ranges, score details, and the comparison table;
- the browser accessibility tree exposed navigation, labeled text area, radio group, selects,
  submit control, expandable explanations, data table, feedback actions, and both dashboard views;
- Evidence & Learning exposed catalog status, private-learning controls, benchmark, prompt-free
  history, and audit sections;
- the benchmark action completed in-page and rendered 100% task classification, Pareto-safe primary,
  and specialist coverage plus measured p95 latency;
- desktop visual inspection found no overlap, clipping of decision content, inaccessible unlabeled
  controls, or broken hierarchy.

Responsive behavior is implemented at 1050, 720, and 600 px breakpoints. This run establishes the G4
desktop visual baseline; automated multi-viewport pixel-diff infrastructure remains release tooling,
not model-advice logic.

## Podman verification

Final image: `localhost/routellect:0.3.0`  
Image ID: `1e1a942b642a3e6c49461e6a04fe8b1d2491c16569e662ec2873424d6b74f876`  
Digest: `sha256:d72ad8b41d81cd96ecf2d6c3c2eac40fc24e1eb151cdc7033d22a437f2858a8c`  
Size: 695,354,030 bytes

The final source built successfully in rootless Podman 6.1.0. The hardened runtime was also verified
on the 0.3.0 application payload: healthy state, UID/GID `10001:10001`, read-only root filesystem,
all default capabilities dropped, `no-new-privileges`, writable isolated `/data`, and readiness
reporting application version 0.3.0. Temporary QA container and volume were removed; the versioned
local image remains available. The Podman VM was stopped after verification.

## Research-informed design checks

- [RouteLLM](https://arxiv.org/abs/2406.18665) demonstrates preference-data routing as a
  cost/quality optimization problem.
- [RouterEval](https://aclanthology.org/2025.findings-emnlp.208.pdf) motivates evaluation across
  datasets, candidate pools, and routing methods rather than relying on one aggregate score.
- [LLMRouterBench](https://arxiv.org/abs/2601.07206) reports that sophisticated routers often do not
  reliably dominate simple baselines and highlights model-pool and latency sensitivity. Routellect
  therefore retains deterministic authority and specialist protection.
- [Calibrated Selective Classification](https://openreview.net/pdf?id=zFhNBs8GaV) supports explicit
  calibration/selective-decision evaluation rather than treating raw confidence as correctness.

## Evidence boundary and recorded deferrals

1. No learned task/quality/cost/latency estimator beyond bounded feedback was activated. There is no
   license-frozen outcome dataset yet on which such a candidate can beat the deterministic baseline;
   acquiring and evaluating that evidence is G5.
2. Current confidence is a conservative uncertainty-derived indication, not outcome-calibrated model
   correctness. Formal calibration error and quality-floor violation thresholds require G5 outcomes.
3. The feedback policy has immutable version + SHA-256 identity and audit receipts, but is not
   independently Ed25519-signed. Release/image signing and provenance remain G6. The signed catalog
   trust path is unchanged.
4. The built-in benchmark is intentionally small and makes no “best router” claim. Statistical
   confidence intervals, public routing datasets, failure slices, and Pareto-frontier model-quality
   comparisons are G5.

These are evidence boundaries, not hidden failures. Learned candidates remain inactive until their
prerequisites exist.
