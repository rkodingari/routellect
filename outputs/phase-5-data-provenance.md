# Routellect G5 Data Provenance

Date: 2026-09-16  
Status: Frozen evidence snapshot acquired and verified

## Selected evidence

- Dataset: [R2-Bench](https://huggingface.co/datasets/JiaqiXue/R2-Bench)
- Pinned revision: `1b6234647a21705da4c220f339e44fbe72c69bb2`
- Declared dataset license: MIT
- Source window: first 5,000 rows from each selected 100-token result file
- Fully aligned rows: 5,000
- Exclusions or missing candidate observations: 0
- Snapshot location: `work/g5-r2/r2_subset.jsonl` (intentionally outside the product image)
- Snapshot SHA-256: `5691a7fe187440106e3548a4d6f792babc168d7da5e12463743297fd661ffe7b`
- Manifest SHA-256: `38ed84cf5ec7501590e056c2f7ad11647a7b6d22bb6b3b712f4761605b29a08b`

## Frozen candidate files

| Candidate | Parameter proxy | Pinned source path |
|---|---:|---|
| Qwen3-0.6B | 0.6B | `data/Qwen/Qwen3-0.6B/100_judge.csv` |
| Qwen2.5-Math-1.5B-Instruct | 1.5B | `data/Qwen/Qwen2.5-Math-1.5B-Instruct/100_judge.csv` |
| Qwen2.5-Math-7B-Instruct | 7B | `data/Qwen/Qwen2.5-Math-7B-Instruct/100_judge.csv` |
| Llama-3.1-70B-Instruct | 70B | `data/meta-llama/Llama-3.1-70B-Instruct/100_judge.csv` |

The pool and parameter proxies were preregistered before score acquisition. Parameter count × actual
output tokens is a compute proxy, not provider price, energy use, or measured model latency.

## Data minimization and alignment

The importer retains only `key`, `prompts_id`, canonical `original_prompt`, `actual_token_count`, and
`correctness_score`. It discards `templated_prompt`, `golden_answer`, model `response`, and
`judge_raw`. No benchmark response or judge rationale enters the product image or user-facing
deliverables.

Cross-model alignment requires exact query keys and prompt IDs. Public prompt text is compared after
Unicode NFC normalization while ignoring only whitespace and Unicode control/format characters.
This handles source serialization differences such as collapsed paragraph breaks and a stray
backspace byte while requiring all visible characters to match. A visible-text mismatch would be
excluded for every candidate and counted in the manifest; none remained in this snapshot.

## Research selection review

- [R2-Bench](https://huggingface.co/datasets/JiaqiXue/R2-Bench) was selected because its dataset card
  declares MIT and exposes outcome-level model/budget files suitable for offline replay.
- [RouteLLM](https://github.com/lm-sys/RouteLLM) informed the strong/weak-model and calibration
  baseline design, but its code and benchmark workflow were not copied into Routellect.
- [RouterEval](https://github.com/MilkThink-Lab/RouterEval) provides broad evaluation tooling under
  MIT; its much larger record collection and separate source-provenance surface were not needed for
  this compact phase.
- [LLMRouterBench](https://github.com/ynulihao/LLMRouterBench) was reviewed but not ingested because
  no repository license file was available during the review.
- [RouterBench](https://huggingface.co/datasets/withmartian/routerbench) was reviewed but not ingested
  because the dataset page did not declare a dataset license during the review, even though the code
  repository is MIT.

This is a conservative selection decision, not a judgment about the technical quality of the
unselected projects.

## Reproduction boundary

The acquisition script streams each pinned file, stops at row 5,000, validates alignment, emits the
minimized JSONL snapshot, and hashes it. The benchmark then verifies the digest before profiling any
prompt. The exact commands are:

```sh
.venv/bin/python scripts/acquire_r2_subset.py --output-dir work/g5-r2
PYTHONPATH=src .venv/bin/python scripts/run_g5_benchmark.py \
  --snapshot work/g5-r2/r2_subset.jsonl \
  --manifest work/g5-r2/manifest.json \
  --output outputs/phase-5-benchmark-results.json \
  --bootstrap-repetitions 2000
```

The first-5,000-row choice can carry source-order bias. The snapshot covers one dataset, one output
budget, and four models; it cannot establish a universal router ranking.
