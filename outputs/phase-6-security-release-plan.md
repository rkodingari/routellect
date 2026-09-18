# Routellect G6 Security and Release Plan

Frozen: 2026-09-16  
Status: Active; G5 sponsor approval recorded

## Release boundary

G6 prepares and verifies a release candidate. It does not publish an image, create a public release,
deploy a service, request provider credentials, or enable target-model execution. Public distribution
requires the G6 sponsor gate.

## Workstreams and exit checks

1. **Supply chain**
   - Produce CycloneDX 1.6 SBOMs for the application/runtime, frontend, assessor artifact, and base
     images with known/unknown completeness made explicit.
   - Produce a license inventory and verify the Apache-2.0 project/model boundary.
   - Pin mutable container bases by digest or record a blocking exception before release.
   - Scan Python, JavaScript, and the final OCI image for known vulnerabilities; record tool versions,
     database timestamps, severities, suppressions, and residual risk.
2. **Provenance and signing**
   - Generate an immutable release manifest containing source-tree, SBOM, benchmark, assessor, and
     image digests.
   - Sign and independently verify that manifest using an offline Ed25519 QA key. Keep no private key
     in source or deliverables. Document Cosign keyless/blob signing as the publication workflow.
3. **Runtime resilience**
   - Verify rootless/non-root/read-only/capability/no-new-privileges controls again.
   - Run advisory load and soak tests, malformed/oversized request tests, rate-limit behavior,
     feedback-poisoning bounds, catalog-signature rejection, and zero-target-call assertions.
   - Record memory, latency, throughput, failures, and recovery.
4. **Data operations**
   - Add safe backup/restore tooling with checksums, path-traversal defense, refuse-overwrite defaults,
     and a verified round trip.
   - Define local retention, deletion, backup encryption, restore, and incident procedures.
5. **Release usability**
   - Prepare multi-architecture OCI commands/workflow for `linux/arm64` and `linux/amd64`; do not push.
   - Verify clean install/start, health, upgrade/rollback, troubleshooting, and removal instructions.
   - Produce a final operator runbook, security review, and release checklist.

## Decision rules

- No known critical vulnerability may ship.
- A known high vulnerability requires a documented non-reachability analysis and sponsor acceptance;
  otherwise G6 is blocked.
- Signature verification, backup/restore integrity, hard privacy boundaries, and container hardening
  are mandatory.
- Load or malformed-input failures must not persist raw prompts, crash the service, bypass hard
  eligibility constraints, or invoke a target model.
- Multi-architecture publication is blocked unless each target architecture is built and smoke-tested
  on native hardware or approved emulation.
- A release remains a candidate until the sponsor explicitly approves G6.

## Standards and primary references

- [CycloneDX SBOM guide](https://cyclonedx.org/guides/sbom/)
- [Sigstore blob signing](https://docs.sigstore.dev/cosign/signing/signing_with_blobs/)
- [Sigstore verification](https://docs.sigstore.dev/cosign/verifying/verify/)
- [Podman multi-platform build](https://docs.podman.io/en/stable/markdown/podman-build.1.html)
- [SmolLM2-360M-Instruct model card and Apache-2.0 license](https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct)

## Required gate artifacts

- SBOM and license report
- Vulnerability report and residual-risk decision
- Signed release manifest and verification receipt
- Abuse/load/soak and backup/restore evidence
- Multi-architecture readiness report
- Operator runbook and incident procedure
- G6 verification report and sponsor gate review
