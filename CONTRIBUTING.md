# Contributing to Routellect

Routellect follows gated SDLC: requirements, design, implementation, verification, security review,
demonstration, and sponsor approval. Do not begin a later gate before the current gate is approved.

## Non-negotiable boundary

Routellect is advisory-only. Changes must not add provider credentials, target-model execution,
proxying, budget reservation, or automatic spending.

## Before a change

1. Link the change to an approved requirement or architecture decision.
2. Add or update tests for behavior, privacy invariants, and safe failure.
3. Run Python lint/tests and the frontend typecheck/build.
4. For container changes, verify rootless Podman, non-root runtime, health, and offline operation.
5. Update the changelog and gate evidence when behavior changes.

Never commit prompts, credentials, generated databases, virtual environments, or downloaded models.
