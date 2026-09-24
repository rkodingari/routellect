# Routellect — Market and Research Review

Status: Gate G1 design input  
Date: 2026-09-15

## What already exists

| Work | What it demonstrates | Gap Routellect will address |
|---|---|---|
| [llm-advisor-mcp](https://github.com/Daichi-Kudo/llm-advisor-mcp) | An MCP model-advisor tool can combine public pricing, model metadata, benchmarks, and freshness scoring. | Focuses on public-data lookup/ranking. Our product adds local prompt analysis, privacy constraints, confidence, reproducible recommendation receipts, feedback learning, dashboard/CLI/API parity, and Podman delivery. |
| [RouteLLM](https://arxiv.org/abs/2406.18665) | Learned routing can save substantial cost while preserving quality in evaluated settings. | It is designed for routing/execution between model pairs, while this product remains advisory-only and exposes ranked choices to the user. |
| [LLMRouterBench](https://arxiv.org/abs/2601.07206) | More than 400K instances across 21 datasets and 33 models; lightweight routers can be competitive, careful pool selection matters, and rare-expert recall remains difficult. | Use a small curated catalog, uncertainty, and explicit specialist recall rather than a heavyweight opaque agent. |
| [RouterEval](https://arxiv.org/abs/2503.10657) | More than 200M performance records over 8,500 models; reports that 3–10 candidates can be cost-effective and warns about model-selection bias. | Measure recommendation diversity/bias and curate a useful shortlist instead of overwhelming users with hundreds of models. |
| [Learning to Route LLMs from Bandit Feedback](https://arxiv.org/abs/2510.07429) | In deployment, only the outcome of the chosen model is normally observed; preference-tunable bandit learning can use this partial feedback. | Store user-confirmed outcomes and learn cautiously from the model actually used, without requiring all models to answer every prompt. |
| [LLM Routing with Dueling Feedback](https://arxiv.org/abs/2510.00841) | Pairwise/dueling feedback can learn performance–cost preferences with lower regret in the reported experiments. | Offer optional “I tried both” comparison feedback after the basic thumbs-up/down flow, without making the default UX complex. |
| [Official OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model) | Reasoning effort, verbosity, tools, and prompt shape affect the quality/cost/latency balance; evaluation is required. | Recommend a complete model configuration, not only a model name, and attach evidence/freshness to the advice. |
| [FrugalGPT](https://arxiv.org/abs/2305.05176) | A learned cascade can trade model cost against quality and, in its reported experiments, preserve or improve quality at lower cost. | Use a cheap deterministic fast path and invoke semantic assessment only where uncertainty justifies its added overhead. |
| [Common-interface hybrid router evaluation](https://arxiv.org/abs/2608.14641) | In the reported frozen comparison, several routers produced near-constant tiers and apparent gains often tracked tier allocation rather than demonstrated prompt targeting. | Compare hybrid advice with a share-matched content-blind control before claiming semantic value or enabling Auto by default. |

## Podman findings

- Podman builds OCI images from a repository `Containerfile` and supports `.containerignore`: [official build documentation](https://docs.podman.io/en/stable/markdown/podman-build.1.html).
- Podman supports container health checks: [official health-check documentation](https://docs.podman.io/en/latest/markdown/podman-healthcheck.1.html).
- On macOS, Podman runs Linux containers in a Podman machine, and the machine is rootless by default: [official machine documentation](https://docs.podman.io/en/latest/markdown/podman-machine-init.1.html).
- Podman 6.1.0 is already installed on the development Mac. Access to its machine state will require approval when container verification begins.

## Product position

**Routellect is a private, evidence-backed “which model should I use?” assistant. It recommends; it never executes.**

The defensible differentiation is the combination of:

1. Prompt-specific advice rather than a generic leaderboard or questionnaire.
2. Model **and inference configuration** recommendations.
3. Hard privacy, capability, context, and budget filters.
4. Cost ranges that include expected output size and tool fees where known.
5. Versioned evidence, uncertainty, source dates, and clear warnings when data is stale.
6. A local feedback loop that learns a user's workload without storing raw prompts.
7. Identical behavior through a simple web page, CLI, and API.
8. A rootless, single-container Podman deployment that works offline with a bundled catalog.
9. Hybrid prompt intelligence: deterministic safety and reproducibility, with bounded local semantic assessment only when useful.

## Design changes derived from research

- Keep the default shortlist to 3 recommendations: one primary, one cheaper, and one stronger/faster alternative as appropriate.
- Use a small curated candidate pool per task/capability, then expand only when data proves complementarity.
- Measure selection bias and rare-expert recall in addition to aggregate recommendation accuracy.
- Treat current prices and provider claims as versioned catalog data, never timeless constants.
- Start feedback learning with an interpretable hierarchical Bayesian suitability adjustment. Add bandit or pairwise models only after enough consented data exists.
- Never auto-promote feedback-driven scoring. Train/calibrate a candidate version, compare it in replay, then require approval.
- Do not use a hosted LLM to classify the prompt. Core prompt analysis remains local so the advisor stays private and incurs no provider inference fee.
- Use a compact local language-model assessor in Auto/Always/Off modes. It proposes structured semantic features only, cannot see model/catalog scores, and cannot make the final decision.
- Require paired assessor-Off/Auto/Always and share-matched content-blind benchmarks. Auto becomes default only after statistically supported prompt-specific improvement within resource/privacy bounds.

## Naming recommendation

Use **Routellect** as the product name and `routellect` as the repository, image, and CLI. The name combines “route” and “intellect,” while the tagline **Know the right model before you run** makes the advisory-only purpose explicit. Exact-name web searches did not surface a conflicting AI/software product as of 2026-09-15. This is a practical collision check, not trademark clearance.
