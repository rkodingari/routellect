# Routellect Phase 7-C2 Gate Review

Date: 2026-09-21  
Decision date: 2026-09-22  
Status: **Approved as a bounded research milestone**

## Sponsor decision

G7-C2 was approved on 2026-09-22 with the gate recommendation below. This approval accepts the
completed research evidence and its limitations. It does not authorize production activation,
opening the existing hidden partition, changing the deterministic-v2 default, or starting G7-D.

## Gate recommendation

Approve G7-C2 as a bounded research milestone while rejecting production activation. Keep v2 as
the default, leave both learned artifacts inactive, and keep the current hidden partition sealed.

## Acceptance checklist

- [x] Second source has an explicit dataset-level Apache-2.0 declaration.
- [x] Exact source revision, window, label counts, and snapshot hashes are recorded.
- [x] No model responses are retained.
- [x] No hidden prompt or outcome is loaded.
- [x] Threshold selection uses only internal development evidence.
- [x] Candidate is compared with fixed/v2, G7-C, share-matched content-blind, and oracle controls.
- [x] Prompt-specific value over the content-blind control has a positive lower 95% bound.
- [x] Three-fold grouped cross-fitting over all 8,051 visible R2 rows has a positive exploratory
  utility lower bound versus fixed/v2.
- [x] Runtime raw-prompt feature cache was removed after privacy review.
- [x] Uncached p95 inference remains below 10 ms.
- [x] Hard deterministic policy remains authoritative and unchanged.
- [x] Ruff is clean; 69 tests pass; total line coverage is 88%.
- [x] Failed promotion criteria are machine-readable and reported without threshold relaxation.

## Non-passing promotion checks

- Quality-retention lower bound: 0.9666, required 0.99.
- Compute-reduction lower bound: 0.0813, required 0.40.
- Untouched utility evidence versus fixed/v2: unavailable; the visible-validation lower bound is
  -0.0002, while exploratory grouped cross-fitting is positive.
- Oracle-regret reduction: 4.57%, required at least 20%.

## Decision boundary

G7-C2 is complete and approved as a research milestone. Further work requires separate G7-D
authorization and is limited to new untouched evaluation design, candidate freeze,
Podman/air-gap hardening, and a fresh gate. The existing hidden partition remains sealed and v3
remains experimental and inactive.

Follow-on status: G7-D was separately authorized on 2026-09-22 and is now complete at its own
sponsor gate. That later authorization did not open the existing hidden partition or activate v3.
