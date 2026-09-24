#!/usr/bin/env python3
"""Create the machine-readable G7-D candidate freeze manifest."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from routellect.evidence_benchmark import file_sha256

FROZEN_FILES = (
    "src/routellect/data/g7c2_multisource_strength.json",
    "src/routellect/data/g7_sparse_strength.json",
    "src/routellect/data/catalog.json",
    "src/routellect/data/deterministic_invariants.json",
    "src/routellect/sparse_policy.py",
    "src/routellect/profiler.py",
    "src/routellect/advisor.py",
    "scripts/train_g7_sparse_policy.py",
    "scripts/train_g7c2_multisource_policy.py",
    "scripts/run_g7d_validation.py",
    "scripts/verify_g7d_podman.py",
    "scripts/run_g7d_podman_pipeline.py",
    "scripts/freeze_g7d_candidate.py",
    "outputs/phase-7c-profiler-results.json",
    "outputs/phase-7c2-results.json",
    "outputs/phase-7d-plan.md",
    "outputs/phase-7d-validation-results.json",
    "outputs/phase-7d-podman-results.json",
    "work/g7-evidence/development.jsonl",
    "work/g7-evidence/validation.jsonl",
    "work/g7-evidence/manifest.json",
    "work/g7c2-evidence/routellm-development.jsonl",
    "work/g7c2-evidence/manifest.json",
)


def create_manifest(root: Path) -> dict[str, object]:
    paths = [root / relative for relative in FROZEN_FILES]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"freeze inputs are missing: {missing}")

    artifact_path = root / "src/routellect/data/g7c2_multisource_strength.json"
    result_path = root / "outputs/phase-7d-validation-results.json"
    artifact = json.loads(artifact_path.read_text())
    results = json.loads(result_path.read_text())
    provenance = artifact["provenance"]
    if not isinstance(provenance, dict):
        raise ValueError("candidate provenance is invalid")
    if results["ready_to_freeze"] is not True:
        raise ValueError("G7-D validation did not authorize a candidate freeze")
    if results["promotion_eligible"] is not False:
        raise ValueError("G7-D candidate must remain unpromoted")
    if results["protocol"]["hidden_test_runs"] != 0:
        raise ValueError("hidden-test execution is forbidden during G7-D")

    return {
        "schema_version": "routellect-g7d-freeze-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "research_candidate_frozen_not_promoted",
        "candidate": {
            "name": "deterministic-v3-candidate.1-g7c2-strength",
            "artifact_sha256": file_sha256(artifact_path),
            "schema_version": artifact["schema_version"],
            "strong_model": artifact["strong_model"],
            "strong_threshold": artifact["strong_threshold"],
            "dimensions": artifact["dimensions"],
            "hash_seed": artifact["hash_seed"],
            "model_pool": results["inputs"]["candidate_pool"],
            "cost_weight": results["inputs"]["cost_weight"],
            "hidden_rows_used": provenance["hidden_rows_used"],
            "raw_model_responses_used": provenance["raw_model_responses_used"],
        },
        "frozen_files_sha256": {
            relative: file_sha256(root / relative) for relative in FROZEN_FILES
        },
        "promotion_rule": {
            "all_conditions_conjunctive": True,
            "quality_retention_lower_95ci_minimum": 0.99,
            "compute_reduction_lower_95ci_minimum": 0.40,
            "utility_vs_fixed_lower_95ci_strictly_positive": True,
            "utility_vs_content_blind_lower_95ci_strictly_positive": True,
            "oracle_regret_reduction_minimum": 0.20,
            "zero_hard_constraint_regressions": True,
            "uncached_p95_inference_ms_maximum": 10.0,
            "threshold_relaxation_after_evaluation": False,
        },
        "confirmatory_evaluation": {
            "authorized": False,
            "executed": False,
            "existing_hidden_partition_permitted": False,
            "planned_dataset": "JiaqiXue/R2-Bench",
            "planned_revision": "1b6234647a21705da4c220f339e44fbe72c69bb2",
            "planned_prompt_ids_inclusive": [15001, 30968],
            "outcomes_may_be_acquired_only_after_g7e_approval": True,
        },
        "production": {
            "default": "deterministic-v2+feedback-bayes-v1",
            "v3_active": False,
            "learned_artifact_active": False,
        },
        "source_control": {
            "commit": None,
            "identity_authority": "SHA-256 file identities in this manifest",
            "publication_blocker": (
                "Create a signed source-control commit containing these exact file identities "
                "before any G7-E evaluation or public benchmark claim."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/phase-7d-candidate-freeze.json")
    )
    args = parser.parse_args()
    manifest = create_manifest(args.root.resolve())
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": manifest["status"],
        "artifact_sha256": manifest["candidate"]["artifact_sha256"],
        "confirmatory_authorized": manifest["confirmatory_evaluation"]["authorized"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
