# Routellect Phase 8-C Container and Release Verification Plan

Date: 2026-09-24
Status: G8-B approved; G8-C execution authorized; awaiting verification result
Release tag: Not authorized

## Scope

G8-C verifies the already-built consolidated source as a rootless Podman image. It does not change
the deterministic policy, tune thresholds, acquire benchmark data, publish a release, or create a
release tag.

## Frozen checks

- Build from the current committed `main` source and pinned Containerfile inputs.
- Confirm the image contains one advisor/profiler path and no sparse or G7 strength artifact.
- Run with rootless Podman, non-root UID/GID, read-only root filesystem, dropped capabilities,
  no-new-privileges, and network disabled.
- Verify liveness/readiness and advisory-only API behavior from inside the isolated container.
- Verify no provider calls, prompt persistence, or runtime model-selection artifact downloads.
- Record image ID, digest, size, runtime security state, readiness, throughput, and latency.
- Generate the CycloneDX inventory and license review; record unknown metadata without silently
  treating it as cleared.
- Run the available vulnerability scan and report its exact scope and result.
- Stop for sponsor review before any release tag or public publication.

## Evidence rule

Existing untracked G8-C artifacts were found before execution. They are preserved as user-owned
files and must not be treated as current evidence until their image identity and source boundary are
verified. Fresh verification output will be written to temporary paths first and only promoted into
the repository after review.
