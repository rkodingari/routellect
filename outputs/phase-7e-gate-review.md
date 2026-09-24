# Routellect Phase 7-E Gate Review

Date: 2026-09-24
Status: **Approved as complete; production promotion rejected**

## Gate recommendation

Approve G7-E as a completed one-time confirmatory evaluation and accept the automatic
non-promotion decision. Keep deterministic-v2 as the production default and retain the frozen v3
candidate only as disabled research evidence.

## Acceptance checklist

- [x] Evaluation code, overlap rules, candidate, threshold, controls, and criteria were committed
  before prompt acquisition.
- [x] New prompt IDs 15,001–30,968 were used; the existing hidden partition was not opened.
- [x] Exact/fuzzy development overlap and evaluation duplicates were excluded without replacement.
- [x] Candidate and control choices were SHA-256 committed before outcomes were acquired.
- [x] Four model files aligned exactly on 15,634 eligible row identities.
- [x] No prompt, response, golden answer, or judge rationale appears in public result artifacts.
- [x] The one-time receipt records exactly one completed evaluation.
- [x] All preregistered controls, intervals, calibration metrics, and major slices are reported.
- [x] Failed criteria were not relaxed or removed.
- [x] Production behavior was not changed.

## Automatic decision

Passed:

- utility improvement over frozen strongest fixed;
- utility improvement over share-matched content-blind;
- inherited software, privacy, determinism, and Podman checks; and
- one-time-run requirement.

Failed:

- quality-retention lower bound: 0.9710, required 0.99;
- compute-reduction lower bound: 0.0922, required 0.40;
- Oracle-regret reduction: 3.02%, required 20%; and
- reasoning-slice quality lower bound: 0.9114, required 0.95.

Promotion is rejected because every condition was conjunctive.

## Sponsor decision

On 2026-09-24, the sponsor responded `Approve G7-E`. This accepts G7-E as complete with the
candidate rejected for production. The approval does not authorize:

- threshold or feature tuning on the now-open evaluation range;
- a second G7-E run;
- deterministic-v3 or sparse-artifact activation;
- claims of production readiness, universal quality, or best-in-class routing; or
- G7-F release hardening for the rejected candidate.

Recommended disposition: retain the exact candidate and evidence behind the disabled experimental
path for portfolio transparency, while deterministic-v2 remains the supported product.
