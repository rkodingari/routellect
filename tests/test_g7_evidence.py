import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_script(name: str) -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / f"{name}.py"
    scripts_path = str(path.parent)
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ACQUIRE = _load_script("acquire_g7_evidence")
ACQUIRE_C2 = _load_script("acquire_g7c2_routellm")
BASELINES = _load_script("run_g7_baselines")
G7E_COMMON = _load_script("g7e_common")
G7E_PROMPTS = _load_script("acquire_g7e_prompts")
G7E_EVALUATION = _load_script("run_g7e_evaluation")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_g7_window_does_not_reuse_g5_rows() -> None:
    assert ACQUIRE.ROW_OFFSET == 5_000
    assert ACQUIRE.ROW_COUNT == 10_000


def test_g7_split_groups_normalized_prompt_duplicates() -> None:
    assert ACQUIRE.stable_split("Explain this API\r\ncarefully") == ACQUIRE.stable_split(
        "Explain this API\ncarefully"
    )


def test_g7c2_source_is_pinned_licensed_and_response_minimized() -> None:
    assert ACQUIRE_C2.REVISION == "2a1afe8d0659904c0f6f59de6179e086fdb027c7"
    assert ACQUIRE_C2.DECLARED_LICENSE == "apache-2.0"
    assert ACQUIRE_C2.ROW_COUNT == 20_000
    url = ACQUIRE_C2._page_url(0, 100)
    assert f"revision={ACQUIRE_C2.REVISION}" in url
    assert "response" not in ACQUIRE_C2._normalize_prompt('["safe prompt"]')


def test_g7c2_normalization_keeps_jsonl_one_physical_row() -> None:
    normalized = ACQUIRE_C2._normalize_prompt('["first second third"]')
    assert normalized == "first\nsecond\nthird"


def test_g7_baseline_rejects_digest_mismatch(tmp_path: Path) -> None:
    development = tmp_path / "development.jsonl"
    validation = tmp_path / "validation.jsonl"
    manifest = tmp_path / "manifest.json"
    development.write_text("{}\n")
    validation.write_text("{}\n")
    manifest.write_text(
        json.dumps(
            {
                "persisted_partitions": {
                    "development": {"sha256": "wrong"},
                    "validation": {"sha256": _sha256(validation)},
                },
                "hidden_partition": {"outcomes_persisted": False},
            }
        )
    )

    with pytest.raises(ValueError, match="development digest mismatch"):
        BASELINES.run(development, validation, manifest, bootstrap_repetitions=1)


def test_g7_baseline_refuses_opened_hidden_partition(tmp_path: Path) -> None:
    development = tmp_path / "development.jsonl"
    validation = tmp_path / "validation.jsonl"
    manifest = tmp_path / "manifest.json"
    development.write_text("{}\n")
    validation.write_text("{}\n")
    manifest.write_text(
        json.dumps(
            {
                "persisted_partitions": {
                    "development": {"sha256": _sha256(development)},
                    "validation": {"sha256": _sha256(validation)},
                },
                "hidden_partition": {"outcomes_persisted": True},
            }
        )
    )

    with pytest.raises(ValueError, match="requires an unopened hidden partition"):
        BASELINES.run(development, validation, manifest, bootstrap_repetitions=1)


def test_g7e_protocol_uses_new_range_and_frozen_candidate() -> None:
    assert G7E_COMMON.START_PROMPT_ID == 15_001
    assert G7E_COMMON.END_PROMPT_ID == 30_968
    assert G7E_COMMON.EXPECTED_ROWS == 15_968
    assert _sha256(
        Path("src/routellect/data/g7c2_multisource_strength.json")
    ) == G7E_COMMON.FROZEN_ARTIFACT_SHA256
    assert G7E_COMMON.canonical_prompt("ＡＰＩ\r\n  Review") == "api review"


def test_g7e_overlap_screen_is_deterministic_and_prompt_free() -> None:
    reference = (
        "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi "
        "omicron pi rho sigma tau"
    )
    prompts = [
        {"key": "exact", "prompts_id": "15001", "original_prompt": reference.upper()},
        {
            "key": "fuzzy",
            "prompts_id": "15002",
            "original_prompt": reference.replace("tau", "changed"),
        },
        {
            "key": "unique",
            "prompts_id": "15003",
            "original_prompt": (
                "write a completely unrelated short story about a lighthouse during a winter storm"
            ),
        },
    ]
    eligible, excluded, diagnostics = G7E_PROMPTS._screen(
        prompts, [(reference, "development")]
    )
    assert [row["key"] for row in eligible] == ["unique"]
    assert {row["reason"] for row in excluded} == {
        "development_exact_overlap",
        "development_fuzzy_overlap",
    }
    assert diagnostics["eligible_rows"] == 1
    assert all("original_prompt" not in row for row in excluded)


def test_g7e_result_is_one_time_prompt_free_and_not_promoted() -> None:
    path = Path("outputs/phase-7e-results.json")
    result = json.loads(path.read_text())
    assert result["protocol"]["evaluation_runs"] == 1
    assert result["protocol"]["existing_hidden_partition_runs"] == 0
    assert result["inputs"]["candidate_artifact_sha256"] == (
        G7E_COMMON.FROZEN_ARTIFACT_SHA256
    )
    assert result["promotion_recommended"] is False
    assert result["promotion_checks"]["utility_vs_fixed_lower_above_zero"] is True
    assert result["promotion_checks"]["quality_retention_lower_at_least_0_99"] is False
    assert result["major_slice_checks"]["task:reasoning"] is False
    assert "original_prompt" not in path.read_text()


def test_g7e_run_once_refuses_an_existing_receipt(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "evaluation-run-receipt.json").write_text("{}\n")
    with pytest.raises(RuntimeError, match="rerun is forbidden"):
        G7E_EVALUATION.run_once(evidence, tmp_path / "result.json")
