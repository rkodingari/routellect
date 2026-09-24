# Routellect G7-B Evidence License and Terms Review

Date: 2026-09-21  
Status: Completed for G7-B acquisition decision

## Decision

Only the pinned R2-Bench source window was acquired for G7-B. Other sources remain excluded or
reserved until their dataset-level terms permit the intended use.

| Evidence source | Code/repository terms | Dataset terms found | G7-B decision |
|---|---|---|---|
| [R2-Bench](https://huggingface.co/datasets/JiaqiXue/R2-Bench) | R2-Router repository declares MIT | Hugging Face dataset card explicitly declares MIT | **Approved** for minimized offline development and validation replay |
| [RouterBench](https://huggingface.co/datasets/withmartian/routerbench) | [Code repository](https://github.com/withmartian/routerbench) declares MIT | Dataset card describes 30,000+ prompts and 11 model responses but exposes no dataset-license declaration | **Excluded**; a code license is not treated as a data license |
| [LLMRouterBench](https://github.com/ynulihao/LLMRouterBench) | No repository license was exposed during review | Multi-source dataset terms were not sufficiently resolved | **Excluded** pending repository and per-dataset license verification |
| [RouterEval](https://github.com/MilkThink-Lab/RouterEval) | Code repository declares MIT | Aggregates multiple upstream datasets with separate provenance surfaces | **Excluded** from G7-B; requires per-source review and is unnecessary for the compact baseline |
| [RouterArena](https://github.com/RouteWorks/RouterArena) | Repository declares Apache-2.0 | Explicitly evaluation-only; training, fitting, or tuning on evaluation data or labels is prohibited | **Reserved** for a later untouched external evaluation; never a training source |

## R2-Bench approved scope

- Dataset ID: `JiaqiXue/R2-Bench`
- Revision: `1b6234647a21705da4c220f339e44fbe72c69bb2`
- Declared license: MIT
- Approved source window: rows 5,001 through 15,000 of four aligned 100-token result files
- Previously used G5 rows 1 through 5,000: excluded from G7 evidence
- Retained fields: key, prompt ID, original prompt, actual output-token count, correctness score
- Discarded fields: templated prompt, golden answer, model response, raw judge output
- Product/runtime use: prohibited; evidence remains under ignored `work/`
- User-feedback mixing: prohibited
- Target-model calls: prohibited

The exact source paths, URLs, row window, candidate identities, split commitment, and output hashes
are recorded in `work/g7-evidence/manifest.json`.

## Transport note

The development host does not provide its TLS interception CA to command-line `curl`. The approved
pinned sources were therefore streamed with certificate verification disabled, but no new row was
accepted until every allowed field in the first 5,000 rows of each candidate source matched the
previously verified G5 snapshot. The source revision, normalized development and validation
snapshots, hidden key/prompt commitment, and generated results are SHA-256 identified.

This prefix anchor provides strong continuity evidence for local research, but it is not equivalent
to normal end-to-end TLS plus independently published full-file checksums. A trusted CA path or
independent source hashes remain mandatory before publication of the evidence package.

## Claims boundary

The approved data contains historical, judge-derived outcomes for four exact models at a 100-token
budget. It does not establish current provider quality, monetary cost, energy use, latency, or
universal routing performance. Dataset licensing does not imply endorsement by the dataset authors.

## G7-C2 addendum

Date: 2026-09-21  
Scope: auxiliary development evidence only

| Evidence source | Dataset terms found | G7-C2 decision |
|---|---|---|
| [RouteLLM GPT-4 judge battles](https://huggingface.co/datasets/routellm/gpt4_judge_battles) | Hugging Face metadata explicitly declares Apache-2.0 at revision `2a1afe8d0659904c0f6f59de6179e086fdb027c7` | **Approved** for a minimized 20,000-row auxiliary development window |
| [xRouteBench](https://huggingface.co/datasets/ulab-ai/xRouteBench) | Code repository is MIT; dataset card reviewed on 2026-09-21 does not declare a dataset license | **Excluded**; code license is not assumed to cover dataset contents |

For RouteLLM, only prompt text, source row identity, and `strong`/`economical`/`tie` labels are
retained under ignored `work/g7c2-evidence/`. Both model responses are discarded before writing.
The minimized snapshot has SHA-256
`41d7a8147ff633d2f4187cbf77c939bfda4aa32d702eadf04916427c620c7d36`.

The development host still lacks its TLS interception CA. The source revision and license metadata
were checked through the Hugging Face API, and the minimized snapshot is locally hashed, but a
trusted CA path remains required before public evidence publication.

## G7-D confirmatory-source addendum

Date: 2026-09-22  
Scope: evaluation design only; no new evidence acquired

The unused R2-Bench prompt-ID range 15,001–30,968 is approved in principle for a future minimized,
exact-pool confirmatory evaluation under the existing MIT declaration. G7-E must freeze overlap
screening before prompt-only acquisition and must commit candidate decisions before joining model
outcomes. The existing 1,949-row hidden partition remains prohibited.

LLMRouterBench is retained only as a protocol influence and possible source-transfer evaluation.
Its paper and repository support dataset-grouped metrics, Best Single, Random, Oracle, cost, and
latency controls, but the reviewed repository/result bundle does not expose a sufficiently clear
data-license declaration and its model pool differs from Routellect's. No LLMRouterBench data was
downloaded, trained on, or evaluated in G7-D.
