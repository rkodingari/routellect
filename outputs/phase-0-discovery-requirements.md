# Phase 0 — Revised Discovery and Requirements

Status: **G0 through G6 approved; planned SDLC build complete**  
Date: 2026-09-15  
Product name: **Routellect**  
Tagline: **Know the right model before you run.**

## 1. Product statement

Routellect is a private, evidence-backed tool that answers one question:

> Given this prompt and my priorities, which model and configuration should I use?

It analyzes the prompt locally with a hybrid profiler, filters models by privacy/capability/context/budget, and recommends one model configuration with two useful alternatives. A deterministic fast path handles clear prompts; an optional small local language-model assessor adds semantic task/difficulty signals when confidence is low. Deterministic policy and scoring make the final decision. The product estimates quality, cost, and latency, explains the recommendation, learns from explicit user feedback, and never invokes a target model.

## 2. Scope

### Included

- Advisory-only web application, CLI, and HTTP API with the same recommendation engine.
- Hybrid prompt analysis inside the application container: deterministic fast path plus a bounded local assessor for uncertain prompts.
- Curated, versioned catalog of hosted and local/open-weight model configurations.
- Model and inference-setting recommendation, including reasoning effort/verbosity where applicable.
- Primary recommendation, cheaper/stronger/faster alternatives, fallback, confidence, reasons, evidence, and freshness warnings.
- Hard privacy, capability, context, provider allow-list, availability, latency, and maximum estimated-cost filters.
- Transparent cost estimation from input size, expected output, cache/tool charges where known, and dated pricing.
- Privacy-preserving feedback loop and versioned advisor improvement.
- Reproducible replay benchmarks and interactive accuracy–cost–latency analysis.
- Rootless Podman packaging with a single production container, health check, persistent data volume, and ARM64/AMD64 support.

### Explicitly excluded

- Calling, proxying, routing to, or executing any target model.
- Storing or managing provider API credentials.
- OpenAI-compatible Chat Completions or Responses proxy endpoints.
- Automatic spending, budget reservation, retries, streaming, fallbacks, or provider failover.
- Training foundation models or claiming that any recommendation is universally best.
- Raw prompt retention by default or external telemetry without opt-in.
- Hosted prompt-assessment services, autonomous tool use, or allowing the local assessor to bypass hard policy.

## 3. Simple user experience

The default screen has only:

1. A prompt box.
2. Four goals: **Balanced**, **Best quality**, **Lowest cost**, and **Fastest**.
3. A privacy choice—**Standard**, **No training**, or **Local only**—defaulting to **No training**.
4. An **Advise me** action.

The result leads with:

- **Use:** model, provider/runtime, and recommended settings.
- **Why:** up to three plain-language reasons.
- **Expected:** quality/confidence, cost range, and latency range.
- **Alternatives:** one cheaper and one stronger/faster option when eligible.
- **Freshness:** catalog date and warnings.
- **Feedback:** “Used it?” and “Did it work?” controls.

Context length, output length, required tools/modalities, allow-lists, and scoring details remain under an Advanced section.

The assessor supports **Auto**, **Always**, and **Off**. G2 defaults to Off until Auto proves
statistically supported held-out value; Auto runs only for ambiguous or low-confidence prompts. If
the assessor is disabled, unavailable, invalid, or too slow, advice safely falls back to the
deterministic path.

## 4. Functional requirements

### Recommendation engine

- Detect task family, difficulty, approximate input/output size, required capabilities, privacy indicators, and ambiguity with deterministic local features first.
- Invoke a pinned, CPU-capable local assessor only when a calibrated uncertainty trigger fires, unless the user selects Always or Off.
- Constrain assessor output to a validated feature schema; it has no tools, network, memory, catalog access, or authority to select the final model.
- Merge assessor signals conservatively. They may add privacy/capability restrictions but cannot remove deterministic or user-specified restrictions.
- Filter candidates before scoring; a scoring weight cannot bypass a hard constraint.
- Rank model configurations by calibrated expected utility for the selected goal.
- Use confidence lower bounds and show `insufficient evidence` rather than inventing certainty.
- Return stable reason codes and a concise explanation.
- Remain deterministic for the same prompt, constraints, catalog, advisor version, and seed.
- Complete deterministic fast-path recommendations under 100 ms p95 excluding browser/network overhead, with a stretch target below 25 ms.
- Publish separate fast-path and assessor-path latency; cap assessor runtime and fall back cleanly on timeout or malformed output.
- Keep warmed assessor-path recommendations under 2 seconds p95 on the development CPU unless the G2 bake-off justifies and obtains approval for a different bound.

### Catalog

- Record provider/runtime, model version, modalities, context/output limits, supported features, prices, data handling, public benchmark evidence, observed latency ranges, source links, effective date, and expiry.
- Treat each model plus inference settings as a distinct configuration when settings change cost/quality/latency.
- Bundle a usable offline catalog and provide an explicit `catalog update` command; runtime recommendations never require internet access.
- Validate imported catalog data and preserve immutable snapshots for reproducibility.

### Feedback loop

- Capture whether the recommendation was used, which model was actually used, success/thumbs rating, optional 1–5 quality rating, and optional observed cost/latency.
- Never store the raw prompt. Store only derived task/features, policy-safe metadata, recommendation IDs, and feedback.
- Start with benchmark-informed priors and interpretable per-task/model Bayesian adjustments with shrinkage and minimum-sample thresholds.
- Optionally accept pairwise “I tried both” preference feedback.
- Detect selection bias, repeated/poisoned feedback, and low-sample overconfidence.
- Produce candidate advisor versions offline; replay-test and manually approve before activation.
- Allow feedback export, deletion, reset, and learning opt-out.

### Interfaces

- Web: paste a prompt and receive one clear answer plus expandable evidence.
- CLI: `routellect advise`, `routellect feedback`, `routellect catalog`, and `routellect benchmark`.
- API: recommendations, recommendation receipts, feedback, catalog summary, and benchmark runs.
- Export a copy-ready model configuration snippet without any API key.

### Podman

- OCI-compatible multi-stage `Containerfile` and `.containerignore`.
- Run as a non-root user with a read-only root filesystem option.
- One exposed application port and one named data volume.
- Built-in liveness/readiness health check.
- No Docker-only features; `podman build` and `podman run` are the primary documented path.
- Native image builds for `linux/arm64` and `linux/amd64`.
- The container works without network access after image build unless the user explicitly updates the catalog.

## 5. Quality targets

- Zero target-model/provider calls, credentials, reservations, or charges from every advisory operation.
- Zero assessor network/tool calls; the pinned local assessor must run entirely inside the container.
- Zero raw prompts or detected secret values in default logs, receipts, feedback, SQLite, browser storage, or exports.
- 99% quality retention with at least 40% estimated cost reduction versus the validation-selected best single model on the preregistered replay workload.
- Statistically supported top-1/top-3 recommendation quality, regret, calibration, bias, and rare-expert recall reporting.
- Deterministic recommendation latency below 100 ms p95, warmed assessor-path latency below 2 seconds p95, and container readiness below 10 seconds on the development host.
- Hybrid advice must beat deterministic-only and content-blind/fixed-tier controls on held-out prompt-specific utility before the assessor is enabled by default; otherwise Auto behaves as Off until improved.
- Identical recommendations and metrics from the same frozen manifest.
- One-command rootless Podman start after the Podman machine is available.

These are exit targets, not advance claims. “Best” is used only for a result supported against declared baselines under the same frozen evidence.

## 6. Product differentiation

Routellect is intentionally simpler than an AI gateway and more rigorous than a static model picker:

- It is advisory-only and therefore safe to try without credentials or spend.
- It recommends configuration as well as model.
- It is personalized by private local feedback.
- It combines an auditable deterministic decision core with optional local semantic understanding.
- It explains uncertainty and data freshness.
- It works offline in one rootless container.
- It benchmarks its own recommendations and reports failures honestly.

See [the market and research review](./phase-1-market-and-research-review.md).

## 7. Revised SDLC gates

| Gate | Phase | Exit condition |
|---|---|---|
| G0 | Discovery | Initial vision approved; later scope revisions recorded here. |
| G1 | Advisory architecture | Advisory-only scope, UX, feedback, data model, API, threat model, benchmark protocol, Podman design, and name approved. |
| G2 | Simple advisor MVP | Web/CLI/API recommend from a frozen catalog; Podman image, non-execution/privacy proofs, tests, and CI pass. |
| G3 | Catalog and feedback | Provider-neutral catalog update flow, feedback capture/export/delete, interpretable learning candidate, and governance tests pass. |
| G4 | Learned advisor and dashboard | Calibrated advisor, replay/promotion workflow, evidence UI, Pareto analysis, and accessibility tests pass. |
| G5 | Benchmarks and optimization | Baselines run, targets measured with confidence intervals, bias/failure slices reported, and Podman performance verified. |
| G6 | Hardening and release | Security, supply chain, multi-architecture image, documentation, operations, and release checklist approved. |

No phase begins before the previous gate is explicitly approved.

## 8. Environment

The development host is an Apple M4 Pro with 24 GB memory. Podman 6.1.0 is installed; macOS requires a Podman-managed Linux VM. The repository will not require Docker, a target-model runtime, or provider credentials; its compact assessor runtime/artifact will be pinned and bundled. Accessing/starting the Podman machine will be requested during G2 verification.

## 9. Gate G1 decisions

Approved on 2026-09-15:

1. Product name **Routellect**, repository/image `routellect`, CLI `routellect`.
2. Initial catalog covers major hosted providers plus a curated set of local/open-weight models.
3. Hybrid deterministic plus bounded local-assessor architecture.

## Sources

- [Research and competitor review](./phase-1-market-and-research-review.md)
- [Official OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model)
- [Podman build documentation](https://docs.podman.io/en/stable/markdown/podman-build.1.html)
- [Podman machine documentation](https://docs.podman.io/en/latest/markdown/podman-machine-init.1.html)
