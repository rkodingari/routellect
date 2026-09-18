# Routellect Phase 6 Verification Report

Date: 2026-09-16  
Version: 0.5.0  
Status: G6 approved by sponsor; local release candidate accepted

Approval recorded: 2026-09-16 (sponsor response: “Approve G6”).

## Outcome

Routellect is a signed, multi-architecture, rootless Podman release candidate with an explicit SBOM,
license inventory, dependency and OS security evidence, abuse controls, verified backup/restore, and
an operator runbook. It remains advisory-only: no target model was called, no provider credential was
requested or supplied, and no image, manifest, release, or service was published.

## Release identity

| Item | Identity |
|---|---|
| arm64 image | `sha256:7afa312429314eef520a6fb62da6347631e6c0655e81311ccd71cfc44151ca11` |
| amd64 image | `sha256:c344f83f15771cc5b81139aeb2cb5220e66446facc79b44561341c5d3a8873a7` |
| local multiarch index ID | `8d5be01961a74aacead75183e83fa843dda140c08548ebdfa4b018022fc25806` |
| source tree | `2cd921ce4a05671c1beb68bc32c110b5bb43f5f97e5138fe6190cba0ad60301c` |
| release manifest | `86cd4339bfe2da40f60002353d89cb39874d32315942902eda5b98c44274c6ec` |
| assessor artifact | `48ab3034d0dd401fbc721eb1df3217902fee7dab9078992d66431f09b7750201` |

The offline Ed25519 QA signature verified independently, its receipt matched the manifest digest,
and a modified payload was rejected. The private key is mode `0600` under ignored `work/`; it is not
in the deliverables. The public key fingerprint is
`1a1b294ea54601e7812992bfbbde088bb33efcaeba77691f75b95faebf74623d`.

## Software verification

- Python lint: pass across application, tests, and release scripts.
- Python tests: 49 passed; 87.05% total coverage.
- Two dependency deprecation warnings are visible and recorded: FastAPI/Starlette TestClient's
  current `httpx` bridge and AnyIO's `BlockingPortal` alias. Neither is a runtime failure.
- Frontend typecheck and production Vite build: pass inside both clean arm64 and amd64 container
  builds using the frozen pnpm lockfile.
- Runtime version: 0.5.0; runtime `pip`: absent.
- Bundled model digest checked during build and again from the final image: exact match.

## Security and supply chain

- CycloneDX 1.6 inventory: 145 components, parsed successfully by Trivy.
- License metadata: 137 normalized or human-declared entries; 8 explicit metadata gaps, including
  two aggregate base references. Project and model are Apache-2.0.
- Known critical/high vulnerabilities: 0.
- Python: one medium (`diskcache` CVE-2025-69872), retained with a documented non-reachability
  analysis; runtime `pip` removal eliminated six medium and one low finding.
- JavaScript production audit: 0 findings.
- Debian official tracker: 27 unimportant and 38 not-yet-assigned open/undetermined records; 35 of
  the latter have Debian no-DSA/minor/point-release notes. The three without notes have documented
  non-reachable paths and remain monitored unknowns.
- Source secret-pattern scan: 0 findings across 65 files / 435,747 UTF-8 bytes.
- Base indexes, application version, model revision, model hash, and scanner image are pinned.
- No vulnerability suppression or hidden allow-list was used.

## Runtime resilience

The native arm64 image ran rootless as UID/GID 10001 with a read-only root filesystem, all default
capabilities dropped, no-new-privileges, and a healthy container check.

| Measure | Result |
|---|---:|
| Readiness | 0.662 s |
| Concurrent load | 200 requests, 12 workers, 0 failures |
| Throughput | 427.66 requests/s |
| Latency | 12.97 ms p50 / 54.91 ms p95 / 243.74 ms p99 |
| Soak | 15.02 s, 137 requests, 0 failures, 7.90 ms p95 |
| Observed memory | 61.43 MB |

Malformed JSON returned 422, an oversized body returned 413, duplicate feedback returned 409,
write throttling returned 429 with `Retry-After`, and health remained 200 after throttling. Security
headers were present on error paths. A canary raw prompt was absent from SQLite, WAL, and SHM files.
Target-model calls and supplied provider credentials were both zero.

## Recovery and architecture

- Live backup and empty-target restore completed with matching archive SHA-256 and SQLite integrity.
- Traversal, symlink, duplicate, malformed, oversize, checksum, overwrite, and retention behaviors
  are enforced and tested.
- arm64 received the full resilience suite.
- amd64 compiled fully under Podman/QEMU, reported `x86_64`, became healthy, and served 20/20 advice
  requests with all hardening controls active.
- A local OCI index contains exactly arm64/v8 and amd64. It was not pushed.

## Residual conditions before public publication

1. Re-run SBOM, Debian, npm, and secret checks immediately before publication because advisory data
   changes over time.
2. Replace the Podman-VM `curl --insecure` assessor fetch by injecting the trusted CA or using a
   verified internal mirror. The immutable SHA-256 currently enforces artifact identity, but TLS
   server authentication is weakened during this local build step.
3. Review the eight non-normalized license records against their shipped copyright text.
4. Use native amd64 and arm64 CI runners for the final registry artifacts, then sign the registry
   digest or release manifest with Cosign keyless signing and retain its Sigstore bundle.
5. Select a registry, public security contact, authentication/TLS boundary, and deployment target
   only under a separate explicit publication/deployment request.

## Verification decision

**G6 approved as a local, gated release candidate.** The mandatory safety, integrity, privacy,
recovery, and two-architecture checks pass. The visible medium and unassigned residuals are accepted
for this candidate while the five publication conditions above remain mandatory.
