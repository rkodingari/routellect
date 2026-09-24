# Routellect Phase 8-C Container and Release Verification Plan

Date: 2026-09-24
Status: G8-C verification complete; awaiting sponsor decision
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

Existing untracked G8-C artifacts were found before execution. They were preserved, then matched
against the fresh image identity, component inventory, and source boundary before being used as
supporting evidence. Fresh verification output was written to separate paths. Release publication
remains outside this phase.

## Execution record

The first fresh build used Podman's default OCI output and correctly failed the harness because the
OCI image did not retain the Dockerfile healthcheck metadata. The image was rebuilt with
`--format docker`; the final image passed all hardened-container checks. This build-format
requirement is reflected in the README quick start.

The final scan reports one medium `diskcache==5.6.3` finding in the optional local assessor stack
and eight unknown machine-readable license metadata entries. They are documented residual findings,
not silently waived. No release tag or public publication was created.
