# Routellect G7-B Data Provenance

Date: 2026-09-21  
Status: Frozen development and validation evidence; hidden partition committed but not retained

## Source identity

- Dataset: [R2-Bench](https://huggingface.co/datasets/JiaqiXue/R2-Bench)
- Pinned revision: `1b6234647a21705da4c220f339e44fbe72c69bb2`
- Declared license: MIT
- Fixed source window: rows 5,001–15,000 from each selected 100-token file
- G5 overlap: zero; rows 1–5,000 are explicitly excluded
- Aligned rows: 10,000
- Exclusions: 0
- Missing candidate outcomes: 0

## Candidate files

| Candidate | Parameter proxy | Pinned source path |
|---|---:|---|
| Qwen3-0.6B | 0.6B | `data/Qwen/Qwen3-0.6B/100_judge.csv` |
| Qwen2.5-Math-1.5B-Instruct | 1.5B | `data/Qwen/Qwen2.5-Math-1.5B-Instruct/100_judge.csv` |
| Qwen2.5-Math-7B-Instruct | 7B | `data/Qwen/Qwen2.5-Math-7B-Instruct/100_judge.csv` |
| Llama-3.1-70B-Instruct | 70B | `data/meta-llama/Llama-3.1-70B-Instruct/100_judge.csv` |

Parameter count multiplied by actual output tokens is a normalized compute proxy, not money,
latency, energy, or carbon impact.

## Split and leakage controls

Exact normalized prompt duplicates are grouped using a SHA-256 fingerprint of Unicode-NFC visible
text with whitespace and control characters removed. The split is then assigned by
`SHA-256("routellect-g7-v1|" + prompt_fingerprint)`:

| Partition | Rows | Persisted in G7-B? | Purpose |
|---|---:|---:|---|
| Development | 6,045 | Yes | Fit fixed and segment baselines only |
| Validation | 2,006 | Yes | Baseline comparison and confidence intervals |
| Hidden test | 1,949 | **No** | One-time G7-E confirmation after candidate freeze and approval |

The hidden partition has commitment
`47eca415fa3f57e1578c990773fe882b020fa13a8bda3c264c5a4e688a82e9bc`.
Neither hidden prompts nor hidden model outcomes were written to disk or loaded by the baseline run.
They remain prohibited for this candidate. Any later outcome acquisition requires a separate G7-E
sponsor approval and must use the newly preregistered untouched range rather than this partition.

## Persisted evidence identities

- Development snapshot SHA-256:
  `43ff060dd693bc95fd9311f9b543dbd11dd2a063a1a90bd654138847a2f4ec20`
- Validation snapshot SHA-256:
  `5813d2a164dc2f4d9fb4dfc08853ef238fc5eb66a3f5fc2a75e846131880cfe0`
- Manifest SHA-256:
  `ae2ec7e6f20c9d35c9f877f5c265b9345380c84802bbc16c98ff727872c5c8e5`

The minimized snapshots and manifest remain in `work/g7-evidence/`, which is excluded from source
control and the product container. Aggregate benchmark results contain no prompt text.

## Data minimization

The acquisition process retains only the original public prompt and the minimum fields needed to
join four precomputed outcomes. It discards responses, references, templated prompts, and judge
rationales before writing a snapshot. No user prompts, feedback records, provider credentials, or
live target-model outputs are involved.

## Reproduction

```sh
.venv/bin/python scripts/acquire_g7_evidence.py --output-dir work/g7-evidence
PYTHONPATH=src .venv/bin/python scripts/run_g7_baselines.py \
  --development work/g7-evidence/development.jsonl \
  --validation work/g7-evidence/validation.jsonl \
  --manifest work/g7-evidence/manifest.json \
  --output outputs/phase-7-baseline-results.json \
  --bootstrap-repetitions 2000
```

Acquisition requires network access. Baseline execution is fully offline and verifies both
persisted snapshot hashes before profiling any prompt.
