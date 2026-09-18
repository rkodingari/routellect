# Routellect Phase 6 Gate Review

Status: **G6 approved by sponsor; planned SDLC build complete**  
Date: 2026-09-16

Approval recorded: 2026-09-16 (sponsor response: “Approve G6”).

## Gate recommendation

**Approve G6 as a local release candidate with publication conditions.** Routellect now satisfies
the agreed hardening and release-evidence scope without broadening into target execution, provider
credential storage, public deployment, or unsupported benchmark claims.

## Acceptance checklist

- [x] G5 sponsor approval recorded; work stayed within G6 authorization.
- [x] Version 0.5.0 arm64 image built and passed full rootless resilience checks.
- [x] Version 0.5.0 amd64 image built fully and passed a real emulated health/advice smoke test.
- [x] Local two-platform OCI index assembled; no push or publication performed.
- [x] Base images, model source revision, model artifact, and release image identities pinned.
- [x] CycloneDX 1.6 SBOM generated with 145 components and explicit completeness notes.
- [x] Project/model license boundary and all metadata gaps documented.
- [x] Python, JavaScript, Debian, and source-secret security checks recorded with no suppression.
- [x] Zero known critical/high findings; one medium and unassigned Debian residuals analyzed.
- [x] Runtime package installer removed from the final image.
- [x] Request-size, rate, duplicate-feedback, malformed-input, and security-header controls pass.
- [x] Concurrent load and soak complete with zero failures and healthy recovery.
- [x] Raw-prompt canary absent from SQLite files; zero target calls and provider credentials.
- [x] Backup, restore, archive integrity, traversal defense, and explicit retention pass.
- [x] Release manifest contains source, image, SBOM, benchmark, scanner, model, and lockfile digests.
- [x] Offline Ed25519 QA signature, independent verification, and tamper rejection pass.
- [x] Operator, incident, upgrade/rollback, removal, and troubleshooting procedures delivered.
- [x] Sponsor explicitly approved G6 and accepted the recorded candidate residuals/conditions.

## Residuals requiring sponsor visibility

- Medium `diskcache` pickle issue: no Routellect cache path; retained and monitored.
- Debian: 27 unimportant and 38 not-yet-assigned entries; no known high/critical classification.
- Eight license expressions are not normalized in machine-readable metadata, though shipped
  human-readable notices or aggregate base-image licensing remain available.
- The local Podman build uses an insecure TLS fetch only for the immutable, SHA-256-verified assessor
  because the VM lacks the host intercept CA. This must be corrected before public publication.
- The G5 hybrid policy was not promoted; no “best router” or universal-quality claim is supported.

## Decision requested

Approve G6 to accept Routellect 0.5.0 as the completed local release candidate and close the planned
SDLC build. Approval does **not** itself authorize a registry push, public release, deployment,
provider credentials, target-model execution, or removal of the publication conditions. Any such
external action requires a separate explicit request.

## Evidence package

- [Verification report](./phase-6-verification-report.md)
- [Operator runbook](./phase-6-operator-runbook.md)
- [Vulnerability review](./phase-6-vulnerability-report.md)
- [SBOM](./routellect-0.5.0.cdx.json)
- [License inventory](./phase-6-license-report.md)
- [Resilience results](./phase-6-resilience-results.json)
- [Backup/restore report](./phase-6-backup-restore-report.md)
- [Multi-architecture report](./phase-6-multiarch-report.md)
- [Release manifest](./routellect-0.5.0-release-manifest.json)
- [Signature verification](./routellect-0.5.0-signature-verification.json)

Decision: **Approved.** Routellect 0.5.0 is the accepted local release candidate. No registry push,
public release, or deployment has been authorized or performed.
