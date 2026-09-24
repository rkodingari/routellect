# Phase 1 — Revised Architecture Gate

Status: **G1 approved; G2 authorized**  
Date: 2026-09-15  
Approved name: **Routellect**  
Tagline: **Know the right model before you run.**

## Outcome

The project is now **advisory-only**. It analyzes a prompt and recommends the best-fit model configuration for the user's quality, cost, latency, capability, and privacy needs. It never calls, proxies, or executes a target model.

## Key decisions

1. One simple experience: paste prompt, choose a goal, set privacy, receive one recommendation plus two alternatives.
2. Three equivalent interfaces: web, `routellect` CLI, and a small HTTP API.
3. Hybrid prompt intelligence approved: deterministic fast path plus a bounded small local language-model assessor for low-confidence prompts. Deterministic policy/scoring retains final authority.
4. Recommend a model **and configuration**, including reasoning effort or equivalent settings where evidence supports it.
5. Curated, dated, source-linked catalog that works offline; updates are explicit, not silently fetched during advice.
6. Feedback records outcomes without retaining prompts. Interpretable per-task/model learning is replay-tested and manually promoted.
7. Rootless Podman is the primary deployment: one non-root container, one port, one data volume, health checks, read-only-root option, ARM64 and AMD64.
8. Complex adaptive/bandit methods remain optional research upgrades after enough feedback exists; the MVP stays explainable and fast.
9. The assessor runs locally with no tools, network, memory, catalog/ranker access, or target-model execution. Auto/Always/Off modes and deterministic fallback keep the product controllable.

## Research-driven enhancements

- Similar public advisor tools make basic metadata ranking insufficient as a differentiator.
- RouterEval and LLMRouterBench support careful small-pool curation and explicit bias/rare-expert measurements.
- Bandit-feedback research supports learning from the model actually used rather than requiring outcomes from every model.
- Dueling-feedback research supports an optional “I tried both” comparison flow.
- Official OpenAI guidance supports recommending inference settings, not only model names.
- FrugalGPT supports learned cost-aware cascades, while recent common-interface routing evaluation motivates a share-matched content-blind control to verify genuine prompt-specific value.

See [market and research review](./phase-1-market-and-research-review.md).

## Deliverables

- [Revised requirements](./phase-0-discovery-requirements.md)
- [Market and research review](./phase-1-market-and-research-review.md)
- [Advisor architecture](./phase-1-system-architecture.md)
- [Hybrid assessor architecture decision](./phase-1-hybrid-assessor-decision.md)
- [Threat model](./phase-1-threat-model.md)
- [Advisory API contract](./phase-1-openapi.json)
- [Benchmark protocol](./phase-1-benchmark-protocol.md)
- [Delivery and Podman verification plan](./phase-1-delivery-plan.md)

## Acceptance checklist

- [x] Direct model execution removed from product scope and API.
- [x] Simple default user flow defined.
- [x] Prompt analysis, catalog, scoring, explanation, and uncertainty boundaries defined.
- [x] Hybrid local assessor direction approved; isolation, fallback, ablation, and default-activation rules defined.
- [x] Feedback capture, privacy, learning, replay, and promotion controls defined.
- [x] Advisory API and receipt schemas defined.
- [x] Podman packaging and verification requirements defined.
- [x] Research/competitor findings incorporated.
- [x] Benchmark, bias, calibration, and anti-gaming rules defined.
- [x] Product name confirmed as Routellect.
- [x] Multi-provider plus curated local/open-weight catalog confirmed.
- [x] Sponsor approval received on 2026-09-15.

## Approval

G1 was approved on 2026-09-15. G2 implementation of the Podman-containerized Routellect MVP is authorized.
