# Routellect Phase 7-E One-Time Confirmatory Evaluation Plan

Date: 2026-09-24  
Status: Authorized; protocol freeze in progress  
Production promotion: **Not authorized**  
Existing hidden partition: **Prohibited**

## Authorization boundary

The sponsor authorized G7-E by responding `proceed` after approving G7-D. G7-E may create the
source-control freeze, acquire the preregistered new R2-Bench range, produce prompt-blind candidate
recommendations, join outcomes once, and publish the automatic pass/fail result. It may not use the
existing 1,949-row hidden partition, tune the candidate, change the threshold or overlap rules after
acquisition, activate v3, or promote any artifact to production.

## Frozen sequence

1. Commit all candidate code, artifacts, tests, protocol documents, acquisition/evaluation scripts,
   and freeze identities to local source control.
2. Acquire prompts from R2-Bench revision
   `1b6234647a21705da4c220f339e44fbe72c69bb2`, prompt IDs 15,001–30,968, using one candidate file.
   The transport parser necessarily sees source CSV fields, but outcome, response, answer, and judge
   fields are discarded and never exposed to the recommendation process or persisted at this stage.
3. Exclude overlap against every locally retained G5, G7 development/validation, and RouteLLM
   development prompt using the rules below. Never load the old G7 hidden partition.
4. Generate candidate, prior, lower-tier, fixed, and share-matched content-blind choices with no
   outcomes present. Persist no raw prompt in the recommendation commitment.
5. Commit the recommendation file and its SHA-256 identity in an ignored evidence manifest.
6. Reacquire the exact four 100-token candidate files once, retain only eligible row identity,
   actual token count, and correctness score, and verify cross-model alignment.
7. Join the frozen choices to outcomes once, run all preregistered metrics, and publish every result.
8. Stop at the G7-E sponsor gate. Production promotion requires another explicit decision even if
   every criterion passes.

## Frozen overlap rules

Prompt canonicalization is Unicode NFKC, case-folding, replacement of control characters with
spaces, and whitespace collapse.

An evaluation row is excluded before recommendation generation when any retained development prompt
meets one of these conditions:

- identical SHA-256 canonical prompt;
- for prompts with at least 12 word tokens, word-trigram Jaccard similarity at least 0.82; or
- for prompts with at least 12 word tokens, word-trigram containment at least 0.92 with token-length
  ratio at least 0.50.

Candidate pairs are found using the ten rarest shared trigram posting lists, then confirmed with
exact set calculations. Fuzzy screening uses at most the first 2,048 word tokens of each prompt.
For prompts shorter than 12 tokens, only exact canonical matches are excluded; fuzzy matching at
that length is too prone to false positives. Exact canonical duplicates inside the evaluation range
are reduced to the lowest numeric prompt ID. Excluded rows are never replaced.

The screening method is deterministic and intentionally conservative. It can detect substantial
lexical overlap, not semantic paraphrases with different wording; that limitation must appear in the
final report.

## Frozen candidate and controls

- Candidate artifact SHA-256:
  `6f32a6242fca4137cb50e515a4012a7bbea6fc01f078a12485016350aae50499`
- Strong threshold: `0.30`
- Cost weight: `0.20`
- Output budget: 100 tokens
- Candidate pool: Qwen3-0.6B, Qwen2.5-Math-1.5B-Instruct,
  Qwen2.5-Math-7B-Instruct, and Llama-3.1-70B-Instruct
- Controls: strongest fixed/Best Single, G7-C single-source, lower-tier-only, share-matched
  content-blind, and per-prompt Oracle
- Content-blind salt: `routellect-g7c2-content-blind-v1|`

## Frozen metrics and decision

Use 10,000 paired bootstrap resamples with seed `2,718,281`. Report point values and 95% intervals
for quality retention, compute reduction, candidate utility versus strongest fixed, candidate
utility versus content-blind, and Oracle-regret reduction. Report recommendation shares, strong-tier
calibration, and task/difficulty slices.

Major slices contain at least 100 rows. Each major slice must have a quality-retention lower 95%
bound of at least 0.95. This slice rule is conjunctive with the G7-D promotion criteria:

- overall quality-retention lower 95% bound at least 0.99;
- overall compute-reduction lower 95% bound at least 0.40;
- utility-difference lower 95% bounds versus fixed and content-blind above zero;
- Oracle-regret reduction point estimate at least 0.20;
- every major slice passes its quality floor;
- all G7-D software, privacy, determinism, and Podman freeze checks remain valid; and
- exactly one outcome evaluation run.

Failure of any condition is automatic non-promotion. No condition may be dropped, weakened, or
reinterpreted after outcomes are available.

## Evidence and privacy boundaries

- Target-model calls: zero; this is historical offline replay.
- Provider credentials: zero.
- Production prompt persistence: unchanged and disabled by default.
- Raw model responses, golden answers, judge rationales, and templated prompts persisted: zero.
- Evaluation prompts: retained only under ignored `work/g7e-evidence/` for the bounded run.
- Public outputs: aggregate metrics, hashes, counts, and prompt-free failure slices only.
- Source TLS residual: command-line acquisition may require the same pinned-revision,
  certificate-verification exception documented in G7-B; it remains a publication blocker.

## Stop condition

After the one-time result, publish the verification and gate reports and stop. G7-F, production
promotion, public release claims, and v3 activation require separate sponsor authorization.
