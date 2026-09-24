# Routellect Delivery and Verification Plan

Status: Proposed at Gate G1

## Engineering workflow

Every phase follows:

`approved requirements → design/ADR → implementation → automated verification → privacy/security review → demonstration → gate decision`

Work stops at every gate. Approval unlocks only the next phase. Advisory-only scope is a permanent boundary, not a staged gateway feature.

## G2 — Simple advisor MVP

### Build

- Initialize repository standards, architecture decisions, changelog, and license placeholder.
- Create locked Python 3.12 and web build environments without modifying system runtimes.
- Build one modular application serving a minimal web interface and a small advisory API, plus the `routellect advise` CLI.
- Implement deterministic prompt profiling, privacy/capability eligibility, a frozen curated catalog, deterministic scoring, ranked alternatives, transparent reasons, and estimate ranges.
- Run a frozen CPU assessor bake-off and select the smallest local language model/runtime that materially improves task/difficulty/capability analysis within the approved memory and latency bounds.
- Add Auto/Always/Off assessor modes, a calibrated Auto trigger, strict structured output, no network/tools/memory/catalog access, timeout/circuit breaker, and deterministic fallback.
- Store content-free recommendation receipts only; do not store prompts by default.
- Add a multi-stage `Containerfile`, `.containerignore`, non-root runtime user, `/data` volume, `/tmp` temp space, port 8080, and health checks.
- Include no provider SDK, model credentials, inference proxy, or target-model execution adapter. Bundle the pinned local assessor artifact so runtime remains offline.

### Exit evidence

- A new user can build and run it with Podman using documented commands.
- It runs rootless and non-root, supports a read-only root filesystem with writable `/data` and temporary `/tmp`, persists settings through a named volume, and passes its health check.
- Web, CLI, and API return the same recommendation for the same frozen input/catalog.
- The hybrid advisor is compared with assessor Off, Always, and a share-matched content-blind control; Auto becomes default only after demonstrating held-out prompt-specific value.
- Tests prove hard constraints are monotonic: local-only prompts never recommend hosted models, and no-training prompts exclude configurations lacking qualifying dated evidence.
- Assessor injection, malformed-output, timeout, crash, and memory-pressure tests all fall back safely; it cannot access catalog/model scores or weaken policy.
- Network-spy tests prove advice causes zero target-provider calls, credential requests, reservations, or charges.
- Network-spy tests also prove the local assessor makes zero outbound calls and retains no prompt history.
- Deterministic fast-path and assessor-path latency/memory are reported separately against the G1 thresholds.

## G3 — Catalog and private feedback

### Build

- Add a curated multi-provider and local/open-weight catalog with exact model/configuration IDs, dated prices, capability/privacy metadata, evidence references, and freshness warnings.
- Add signed/versioned catalog import, validation, rollback, and offline fallback.
- Add recommendation feedback: used/not used, worked/did not work, optional 1–5 quality, observed cost/latency, and optional pairwise preference.
- Keep feedback content-minimized and local; do not retain raw prompts or free-text feedback by default.
- Add export, delete, reset, and feedback opt-out controls.
- Implement conservative Bayesian task/model adjustments with support counts, shrinkage to global priors, and bounded influence.
- Use consented outcomes to recalibrate the assessor trigger and feature confidence only through the same offline candidate/replay/manual-promotion workflow.

### Exit evidence

- Every recommendation shows catalog/evidence freshness and estimate uncertainty.
- Catalog validation rejects unknown fields, bad signatures/hashes, unsafe URLs, stale unsupported configurations, and invalid prices.
- Feedback improves or safely leaves unchanged the chronological holdout metric; sparse feedback cannot create overconfident advice.
- Feedback deletion and reset are complete and testable.
- Podman upgrade preserves the named-volume data and supports rollback to the previous catalog.

## G4 — Learned advisor and polished dashboard

### Build

- Add calibrated difficulty/task, quality, latency, and cost estimators only where they beat simple rules on validation.
- Add uncertainty penalties, Pareto filtering, specialist-recall guards, and explainable score contributions.
- Train candidates offline; require replay, bias checks, signed versioning, and manual promotion/rollback.
- Add an interactive but focused dashboard: prompt advisor, comparison view, feedback history/control, catalog freshness, and benchmark explorer.
- Add accessible keyboard behavior, responsive design, and exportable recommendation reports.

### Exit evidence

- Learned advice beats or matches deterministic rules on preregistered validation metrics and does not regress hard slices.
- Confidence calibration and quality-floor violation thresholds are chosen without test-set tuning.
- Promotion cannot occur automatically or without an audit record.
- Browser, accessibility, visual-regression, and API parity tests pass.

## G5 — Benchmark evidence

### Build/run

- Acquire license-compatible, outcome-level routing datasets and freeze provenance/hashes.
- Select and freeze a compact complementary candidate pool using development data only.
- Run all baselines using offline replay, catalog validation, feedback holdout, and container performance modes.
- Produce statistical analysis, failure slices, Pareto frontiers, recommendation-share/bias analysis, and reproducible reports.
- Optimize only after profiling and rerun the complete preregistered suite.

### Exit evidence

- Clean-checkout reproduction matches recommendations and metric calculations.
- Primary and secondary results include confidence intervals, sample sizes, exclusions, and limitations.
- Advisor overhead, image size, startup time, memory, and throughput are measured under Podman.
- No “best” claim appears unless it satisfies the G1 protocol.
- Benchmark tooling performs zero target-model calls.

## G6 — Hardening and release

### Build

- Complete dependency/model SBOM and license review, assessor provenance/digest verification, image signing, vulnerability scanning, backup/restore, retention controls, and incident procedures.
- Run load, soak, malformed-input, denial-of-service, feedback-poisoning, and catalog-import tests.
- Publish multi-architecture OCI images, exact Podman instructions, configuration reference, troubleshooting, upgrade/rollback, and offline-use documentation.
- Produce the product walkthrough and benchmark-methodology documentation.

### Exit evidence

- All critical/high threats are mitigated or explicitly accepted.
- Release image runs rootless on supported Podman hosts, as non-root, with read-only root filesystem and no unnecessary capabilities.
- Image provenance, SBOM, checksums/signatures, backup/restore, and clean-up procedures are verified.
- A versioned release can be installed and used in minutes without target-model/provider credentials.

## Definition of done

- Acceptance criterion maps to a test or recorded review.
- Typed behavior and clear user-facing errors.
- Relevant unit, contract, integration, browser, and container tests.
- Privacy, feedback, catalog, and telemetry impact reviewed.
- Migration and rollback documented for state changes.
- No new lint, type, test, security, or container-policy failures.
- User documentation is current and usable.

## Initial work breakdown after G1 approval

1. Repository/toolchain skeleton and architecture decisions.
2. Advisory schemas, SQLite migrations, and frozen sample catalog.
3. Deterministic prompt profiler and hard eligibility engine.
4. Frozen local assessor bake-off and bounded Auto/Always/Off integration.
5. Deterministic, uncertainty-aware score/rank engine.
6. Recommendation API and `routellect advise` CLI.
7. Single-screen web advisor with reasons and three choices.
8. Content-free receipt and privacy controls.
9. Rootless Podman image, health check, volume, and hardening tests.
10. Offline replay fixtures, hybrid ablations, zero-egress proof, and CI evidence.

## Dependency and installation policy

- Lock direct/transitive versions and hashes where supported.
- Prefer small mature dependencies; add ML packages only when evidence justifies them.
- Never install into system Python.
- Do not download target models or request provider credentials. The approved compact assessor is pinned and bundled during the image build; runtime performs no model download.
- Podman is the supported container interface; on macOS, documented setup includes the Podman-managed Linux VM.
- Any external installation, machine startup, network download, or public publication is requested only in the phase that requires it.

## Major risks and responses

| Risk | Response |
|---|---|
| Catalog becomes stale | Dated evidence, freshness warnings, signed updates, and offline snapshot |
| Sparse feedback overfits | Bayesian shrinkage, support counts, bounded influence, replay, manual promotion |
| Large model pool hurts routing | Curated complementary pool, entropy/share monitoring, rare-expert tests |
| Public outcome artifacts are unavailable | Start with transparent project fixtures; add only licensed reproducible imports |
| Historical data is mistaken for current truth | Prominent date/version labels and uncertainty ranges |
| “Best” becomes marketing rather than evidence | Preregistered thresholds and claim-eligibility checks |
| Container setup feels heavy | One image, one port, one volume, one quick-start path |
| Local assessor makes the image slow or large | Frozen CPU bake-off, quantized compact artifact, lazy load, Auto trigger, strict resource cap, deterministic fallback |
| Hybrid gains are only route-mix bias | Share-matched content-blind control and paired prompt-level ablation before default activation |

## Gate policy

Rejection causes revision within the same phase. Approval unlocks only the next phase. Public deployment, publication, external credentials, network-based catalog updates, and destructive migrations each require explicit authorization even when a broader phase is approved.
