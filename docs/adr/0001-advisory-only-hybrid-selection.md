# ADR 0001: Advisory-only hybrid model selection

- Status: Accepted at G1; implementation refined at G2
- Date: 2026-09-15

## Context

Users need model/configuration advice that balances quality, cost, latency, capabilities, and
privacy without creating spend or exposing prompts to another provider. Keywords are fast and
auditable but miss paraphrases. Small generative classifiers can introduce output and label bias.

## Decision

Routellect is advisory-only. Deterministic hard policy and scoring retain final authority. Off is
the G2 default. Auto and Always can invoke a pinned local SmolLM2-360M artifact as a bounded semantic
embedding signal. Versioned task prototypes produce a deterministic similarity score; the model
does not generate classifications, receive catalog data, or name a target model. Low-margin results
leave the deterministic profile unchanged. Timeout, invalid data, or runtime failure falls back.

Auto can become the default only after the preregistered G5 evaluation shows statistically supported
prompt-specific utility over Off and a share-matched content-blind control without privacy or latency
regression.

## Consequences

- Advice remains available without the assessor and can run with networking disabled.
- Embeddings add semantic recall while avoiding free-form JSON generation and prompt-injection
  instructions.
- The image is larger because it bundles a checksum-pinned 386 MB model and llama.cpp runtime.
- Current task prototypes are an experimental candidate, not evidence of universal routing quality.
