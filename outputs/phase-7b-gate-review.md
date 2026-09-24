# Routellect Phase 7-B Gate Review

Status: **G7-B approved by sponsor; G7-C authorized**  
Date: 2026-09-21

Approval recorded: 2026-09-21 (sponsor response: “Approve G7-B”).

## Gate recommendation

Approve G7-B and authorize deterministic-v3 implementation in G7-C, with development and validation
evidence only. Do not open the committed hidden partition.

The baseline audit provides a clear implementation target: v2 assigns 47.76% of visible prompts to
`general`, all segment policies collapse to the same 70B model, and validation oracle regret remains
0.1565 even though all four candidates contribute to the oracle mix.

## Acceptance checklist

- [x] G7-A sponsor approval is recorded.
- [x] Dataset-level license and usage decisions are documented before ingestion.
- [x] Only R2-Bench's explicit MIT dataset was acquired.
- [x] The selected 10,000 rows do not overlap the 5,000 G5 rows.
- [x] Four candidate files align with zero exclusions and zero missing outcomes.
- [x] Exact normalized prompt duplicates are assigned to one split.
- [x] Development and validation snapshots are minimized and SHA-256 identified.
- [x] Hidden row identities are committed while hidden prompts/outcomes remain unpersisted.
- [x] Hidden-test run count is zero.
- [x] Fixed, random, v2 task/length/hybrid, and oracle baselines are measured.
- [x] Two thousand paired bootstrap resamples quantify validation uncertainty.
- [x] No target-model calls, provider credentials, user prompts, or raw benchmark responses are used.
- [x] G7-B tooling passes lint, compilation, and focused tests.
- [x] Limitations, TLS transport residual, and claim boundaries are explicit.

## Decision requested

Approve G7-B to authorize G7-C only:

1. create the reviewed synthetic invariant corpus;
2. implement boundary-aware lexical and negation policy;
3. train/export a frozen sparse utility/strength artifact using development outcomes only;
4. implement conservative token ranges, stable utility transforms, and calibrated uncertainty;
5. add explanations, migration fallback, and comprehensive tests; and
6. evaluate and iterate on development/validation only.

Approval does not authorize hidden-test reconstruction, production promotion, changing the default
advisor, provider credentials, target-model execution, public deployment, or publication.

## Evidence package

- [G7 plan](./phase-7-deterministic-routing-plan.md)
- [License and terms review](./phase-7-license-review.md)
- [Data provenance](./phase-7-data-provenance.md)
- [Baseline verification](./phase-7-baseline-verification-report.md)
- [Machine-readable baseline](./phase-7-baseline-results.json)

Decision: **Approved.** Work may proceed through G7-C and must stop at the G7-C validation gate.
The hidden partition remains unopened and production promotion remains unauthorized.
