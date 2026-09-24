# Routellect Phase 5 Gate Review

Status: **G5 approved by sponsor; G6 authorized**  
Date: 2026-09-16

Approval recorded: 2026-09-16 (sponsor response: “Approve G5”).

## Gate recommendation

**Approve G5 with no learned-policy promotion.** The phase achieved its evidence objective: a
license-compatible frozen dataset, reproducible baselines, uncertainty intervals, failure slices,
one-time hidden-test results, and rootless Podman performance evidence. The benchmark also prevented
an unjustified success claim: the hybrid candidate ties the global baseline at the primary point and
adds no routing value.

## Acceptance checklist

- [x] G4 sponsor approval recorded; work stayed within G5 authorization.
- [x] R2-Bench license declaration, revision, source paths, row window, and hashes frozen.
- [x] Candidate pool, split, objectives, λ values, baselines, shrinkage, bootstrap, and promotion rule
  preregistered before score acquisition.
- [x] 5,000 rows align across four candidates; 0 exclusions and 0 missing observations.
- [x] Only minimized evidence fields retained; responses, references, templates, and judge rationale
  discarded.
- [x] Train/validation/hidden-test isolation implemented; hidden test evaluated once.
- [x] Eight policies compared, including simple baselines and a non-deployable oracle.
- [x] Primary means, 2,000-resample 95% intervals, paired differences, sample sizes, quality-floor
  violations, recommendation shares, slices, Pareto sets, and oracle regret reported.
- [x] Benchmark tooling made zero target-model calls and requested no provider credentials.
- [x] Literal hybrid validation gate passed by equality, with no >0.02 eligible-slice regression.
- [x] Practical-value review rejects promotion because hybrid and global make identical decisions.
- [x] Python lint, 42 tests, 88% total coverage, frontend typecheck, and production build pass.
- [x] Version 0.4.0 rootless Podman image builds and passes non-root, read-only, dropped-capability,
  no-new-privileges, readiness, health, memory, latency, and throughput checks.
- [x] No “best router” claim is made; limitations and exploratory results are clearly labeled.

## Decision requested

Approve G5 to authorize G6 only: dependency/model SBOM and license review, image signing,
vulnerability scanning, backup/restore, retention and incident procedures, load/soak and abuse tests,
multi-architecture OCI publication preparation, and final operator/user documentation.

Approval does **not** authorize promotion of the G5 segment policy, tuning against the opened hidden
test, public deployment or publication, external provider credentials, target-model execution,
automatic catalog downloads, or a universal benchmark-superiority claim.

## Evidence package

- [Preregistered benchmark plan](./phase-5-preregistered-benchmark-plan.md)
- [Data provenance](./phase-5-data-provenance.md)
- [Verification report](./phase-5-verification-report.md)
- [Machine-readable benchmark](./phase-5-benchmark-results.json)
- [Podman benchmark](./phase-5-container-benchmark.json)
- [External evidence ADR](../docs/adr/0004-frozen-external-evidence.md)

Decision: **Approved without learned-policy promotion.** Work may proceed through G6 and must stop
at the G6 release gate. All authorization boundaries above remain in force.
