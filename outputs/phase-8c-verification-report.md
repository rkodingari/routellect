# Routellect Phase 8-C Verification Report

Date: 2026-09-24
Source commit: `f225e00489942df854023ce28b5f11431de6bacd`
Status: **Verified with documented dependency findings; release still gated**

## Outcome

The current consolidated source was rebuilt as `localhost/routellect:g8c-unified-docker` using the
pinned `Containerfile` inputs and Docker image format. The image starts successfully under the
approved hardened boundary and serves advisory-only recommendations. No release tag or public
publication was performed.

## Container acceptance

The fresh image was verified by `scripts/verify_g8c_podman.py` with rootless Podman and:

- network mode `none`;
- UID/GID `10001:10001`;
- read-only root filesystem;
- all capabilities dropped;
- `no-new-privileges` enabled;
- writable state limited to the dedicated `/data` volume and a no-exec `/tmp` tmpfs;
- Docker-format healthcheck reporting `healthy`.

Image identity:

| Field | Value |
|---|---|
| Reference | `localhost/routellect:g8c-unified-docker` |
| Image ID | `8b8878c98debdb37c5073de4fe601eaed7947cc362b9be60e7181f2eee50b017` |
| Digest | `sha256:e6aeee4591d3c19e064f723d02619fb9944557f5efe4b7608e16dbef58141dbb` |
| Size | 683,692,989 bytes |

## Runtime acceptance

Readiness returned `ok` with version `0.5.0` and catalog `2026-09-15.g2-starter.1`. One hundred
in-container advisory requests returned the unified policy version
`deterministic-unified-v1+feedback-bayes-v1`; mean latency was 1.681 ms, p50 1.322 ms, and p95
2.322 ms. The harness observed zero target-provider calls. The sparse module and both packaged
G7 strength artifacts were absent.

This is a runtime and packaging result, not an external quality claim.

## Supply-chain review

The fresh CycloneDX 1.6 inventory contains 145 components and matches the prior G8-C component
inventory by normalized component identity. Eight base-image or system-package entries expose
unknown machine-readable license metadata; they are listed in the license inventory and are not
silently treated as cleared.

The available Trivy SBOM report found no Node.js vulnerability and one medium Python finding:
`CVE-2025-69872` in `diskcache==5.6.3`, concerning pickle deserialization. Routellect has no
diskcache code path, and the optional local assessor is off by default, but the dependency remains
in the assessor stack. This is a documented residual finding requiring sponsor disposition before
public release; it is not described as a clean scan.

## Evidence

- [Fresh container verification](phase-8c-fresh-build-podman-results.json)
- [Aggregate G8-C results](phase-8c-results.json)
- [Fresh CycloneDX SBOM](routellect-g8c-fresh.cdx.json)
- [Fresh license inventory](phase-8c-fresh-license-inventory.md)
- [Available Trivy SBOM report](phase-8c-trivy-sbom-report.json)
- [Verification harness](../scripts/verify_g8c_podman.py)

G8-C stops here for sponsor review. Release tagging, publication, and any security-finding waiver
remain unauthorized.
