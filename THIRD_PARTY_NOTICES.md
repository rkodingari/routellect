# Third-Party Notices

Routellect is distributed under Apache License 2.0. Its Python and JavaScript dependencies retain
their respective licenses; the release SBOM and G6 license report provide the exact versioned
inventory used by the release candidate.

## Bundled model artifact

- Artifact: `smollm2-360m-instruct-q8_0.gguf`
- Repository: `HuggingFaceTB/SmolLM2-360M-Instruct-GGUF`
- Immutable revision: `593b5a2e04c8f3e4ee880263f93e0bd2901ad47f`
- SHA-256: `48ab3034d0dd401fbc721eb1df3217902fee7dab9078992d66431f09b7750201`
- Upstream model: `HuggingFaceTB/SmolLM2-360M-Instruct`
- License: Apache License 2.0
- Model card: https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct

The artifact is used only as an optional, bounded local prompt assessor. It has no network, tool,
catalog, or final-decision authority.

## Development-only routing evidence

- Dataset: `routellm/gpt4_judge_battles`
- Revision: `2a1afe8d0659904c0f6f59de6179e086fdb027c7`
- License: Apache License 2.0
- Dataset page: https://huggingface.co/datasets/routellm/gpt4_judge_battles

A minimized 20,000-row snapshot was used only for G7-C2 auxiliary development. Raw model responses
are neither retained nor shipped. The rejected sparse artifact is preserved only in Git history
and prompt-free evaluation records; it is not included in the runtime package.
