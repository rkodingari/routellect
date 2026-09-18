# Routellect Threat Model

Status: Proposed at Gate G1

## Assets and boundaries

Protected assets are prompt content in memory, derived prompt features, the local assessor model/configuration, feedback, personalized scoring, catalog/evidence integrity, benchmark test splits/results, audit receipts, container data, and admin state.

Trust boundaries are: user to web/CLI/API; process to SQLite/benchmark artifacts; operator-triggered catalog updater to external sources; benchmark worker to candidate advisor versions; and host to rootless Podman VM/container.

The product has no model-provider execution boundary because it never calls target models.

## Threat register

| ID | Threat | Main controls | Verification |
|---|---|---|---|
| T01 | Prompt leaks through logs, receipts, feedback, errors, browser storage, or exports | Allow-list telemetry; in-memory analysis; no prompt fields in persisted schemas; error redaction | Inject canary secrets and scan every artifact/store |
| T02 | Advisor accidentally calls a target model or incurs charges | No provider SDK/credentials/execution module; outbound-network spy; production egress disabled during advice | Assert zero target calls for every API/CLI/web scenario |
| T03 | Confidential prompt is sent to a hosted classifier or assessor | Deterministic profiler and pinned local assessor only; assessor network denied | Network-denied end-to-end recommendation test |
| T04 | Unsalted prompt hash enables recovery | Optional tenant-keyed HMAC only; disabled by default | Dictionary-attack test and schema review |
| T05 | Caller weakens declared/system privacy | Monotonic merge; effective class is the strictest signal | Property tests over all class combinations |
| T06 | Local-only prompt recommends hosted model, or no-training prompt recommends an ineligible policy | Hard privacy/data-use eligibility rules | Adversarial privacy corpus and invariant test |
| T07 | Stale/incorrect price or capability creates bad advice | Versioned sources, effective dates, expiry, validation, stale warnings, rollback | Catalog expiry/change tests and golden price vectors |
| T08 | Malicious catalog import changes code or injects UI content | Data-only schema, signatures/checksums where available, URL allow-list, no eval, strict rendering | Malicious import and XSS fixtures |
| T09 | Catalog updater performs SSRF | Fixed source allow-list, HTTPS, redirect/DNS checks, size/time limits | SSRF corpus including loopback/private/redirect targets |
| T10 | User feedback poisons recommendations | Local scope, rate/dedup checks, bounded influence, shrinkage, minimum samples, anomaly flags, manual promotion | Poisoning simulation and promotion test |
| T11 | Sparse feedback causes overconfident personalization | Uncertainty, minimum evidence, global-prior shrinkage, sample count shown | Low-sample calibration tests |
| T12 | Selection bias makes one popular model dominate | Diversity/entropy metrics, counterfactual replay, per-task slices, rare-expert recall | Bias report is a benchmark release requirement |
| T13 | Cross-user feedback or receipts are exposed | Tenant/workspace authorization and scoped queries | Negative multi-tenant tests |
| T14 | Prompt injection changes policy/scoring code | Prompt is data; no instruction-following LLM in core; deterministic parser; fixed feature schema | Injection/metamorphic corpus |
| T15 | Recommendation is presented as guaranteed “best” | Estimate labels, confidence, alternatives, source/freshness, no guarantee language | Response/UI content tests and failure-case review |
| T16 | User follows an expired recommendation | `catalog_as_of` and `expires_at`; stale banner; copy includes version | Expiry tests |
| T17 | Benchmark leakage/cherry-picking creates false superiority | Hidden test, preregistered primary metric, immutable manifests, all baselines/configs reported | Clean reproduction and manifest audit |
| T18 | Benchmark content/output executes code | Data-only loaders; no eval; code benchmarks only in an isolated test sandbox | Malicious dataset fixture |
| T19 | Dependency/container supply-chain compromise | Locked dependencies, minimal images, pinned bases/digests for release, SBOM, scans | Clean build, SBOM, vulnerability and secret scans |
| T20 | Container runs with excess privilege or exposes data | Non-root user, rootless Podman, read-only root, one volume, no host mounts by default, least capabilities | Container structure and runtime tests |
| T21 | Denial of service from huge/adversarial prompts | Request size/token/time limits, bounded parsers, rate/concurrency limits | Boundary/fuzz/load tests |
| T22 | Feedback deletion does not remove personalization | Feedback lineage and deterministic rebuild; delete/reset invalidates derived snapshot | Delete/rebuild acceptance test |
| T23 | Prompt injection makes the assessor select a model or bypass policy | Assessor cannot see catalog/ranker; constrained feature schema; deterministic policy owns final decision | Injection corpus and package-access test |
| T24 | Assessor hallucinates capabilities or difficulty with high confidence | Conservative merge, calibration, confidence threshold, deterministic fallback, visible assessor use | Calibration and adversarial ambiguity suite |
| T25 | Assessor timeout/crash blocks advice | Strict CPU/memory/time limits, circuit breaker, deterministic fallback | Kill, malformed-output, timeout, and memory-pressure tests |
| T26 | Assessor artifact/runtime is tampered with | Pinned digest, local-only load, provenance, SBOM/license review, signature/checksum verification | Corrupt/substitute artifact tests |
| T27 | Assessor causes hidden prompt retention | Stateless inference, bounded memory lifecycle, no prompt cache/history, store/log canary scans | Repeated canary and process-restart tests |

## Release-blocking invariants

1. An advisory operation makes no target-model/provider request and needs no provider credential.
2. Raw prompts, responses, secrets, and free-text feedback are absent from persistent state by default.
3. Local-only prompts cannot recommend hosted models; no-training prompts cannot recommend configurations lacking qualifying dated evidence.
4. A user cannot weaken a stricter policy.
5. Unvalidated or expired catalog data cannot be presented as fresh evidence.
6. Feedback cannot change the active advisor until a candidate passes replay checks and receives approval.
7. Feedback export/delete/reset is complete and testable.
8. The production container runs as non-root and supports read-only root filesystem operation.
9. The assessor has no network, tools, memory, catalog/ranker access, or final-decision authority and always has a deterministic fallback.

## Residual risks

- Prompt classification and quality prediction remain imperfect; confidence and alternatives communicate this rather than guaranteeing correctness.
- Public benchmarks may not represent a user's workload. Local feedback improves personalization only after enough representative outcomes.
- Provider prices, limits, and model availability change rapidly. Advice is valid only for its catalog snapshot and time window.
- Rootless containers reduce host risk but do not protect a compromised host or Podman VM.
- A compact local assessor can misclassify novel or adversarial prompts. Its contribution remains bounded, disclosed, calibrated, and benchmarked against the deterministic path.
- A user can manually send a sensitive prompt to a hosted model after receiving advice. The advisor warns and filters, but cannot control actions outside the product.

## Required evidence by G6

- Privacy-canary scan, target-model and assessor network proof, assessor isolation/fallback/calibration tests, multi-tenant tests, catalog-import security tests, feedback poisoning/deletion tests, benchmark reproducibility report, locked dependency/model SBOM/license inventory, container vulnerability scan, and rootless/read-only runtime report.
