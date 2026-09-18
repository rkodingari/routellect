from pathlib import Path

from fastapi.testclient import TestClient

import routellect.api as api
from routellect.advisor import Advisor
from routellect.assessor import LocalAssessor
from routellect.catalog import CatalogManager
from routellect.storage import Store


def client_for(tmp_path: Path) -> TestClient:
    api.store = Store(tmp_path / "test.sqlite3")
    api.catalog_manager = CatalogManager(tmp_path / "catalogs")
    api.advisor = Advisor(assessor=LocalAssessor(model_path=str(tmp_path / "missing.gguf")))
    return TestClient(api.app)


def test_recommendation_receipt_and_feedback_contain_no_prompt(tmp_path: Path) -> None:
    secret = "CANARY-RAW-PROMPT-44229"
    with client_for(tmp_path) as client:
        response = client.post(
            "/v1/model-recommendations",
            json={
                "messages": [{"role": "user", "content": f"Write an email {secret}"}],
                "objective": "balanced",
                "privacy": "no_training",
                "assessor_mode": "off",
            },
        )
        assert response.status_code == 200
        body = response.json()
        receipt = client.get(f"/v1/model-recommendations/{body['recommendation_id']}")
        assert receipt.status_code == 200
        assert secret not in receipt.text
        feedback = client.post(
            f"/v1/model-recommendations/{body['recommendation_id']}/feedback",
            json={
                "used_recommendation": True,
                "used_configuration_id": body["recommendations"][0]["configuration"][
                    "configuration_id"
                ],
                "outcome": "worked",
            },
        )
        assert feedback.status_code == 201
        duplicate = client.post(
            f"/v1/model-recommendations/{body['recommendation_id']}/feedback",
            json={
                "used_recommendation": True,
                "used_configuration_id": body["recommendations"][0]["configuration"][
                    "configuration_id"
                ],
                "outcome": "worked",
            },
        )
        assert duplicate.status_code == 409
        assert feedback.json()["prompt_stored"] is False
        assert secret.encode() not in (tmp_path / "test.sqlite3").read_bytes()


def test_oversized_write_is_rejected_before_parsing(tmp_path: Path) -> None:
    with client_for(tmp_path) as client:
        response = client.post(
            "/v1/model-recommendations",
            content=b"x" * (api.MAX_REQUEST_BYTES + 1),
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 413
        assert response.headers["cache-control"] == "no-store"


def test_builtin_benchmark_is_non_executing(tmp_path: Path) -> None:
    with client_for(tmp_path) as client:
        response = client.post("/v1/benchmarks/runs", json={})
        assert response.status_code == 202
        metrics = response.json()["metrics"]
        assert metrics["target_provider_calls"] == 0
        assert metrics["raw_prompts_persisted"] == 0
        assert metrics["primary_pareto_rate"] == 1
        assert metrics["specialist_shortlist_coverage"] == 1
        assert metrics["score_reconciliation_max_error"] < 1e-9


def test_security_headers_and_catalog(tmp_path: Path) -> None:
    with client_for(tmp_path) as client:
        response = client.get("/v1/catalog/summary")
        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.json()["configuration_count"] >= 8
        assert response.json()["source"] == "builtin"


def test_feedback_api_controls_and_manual_promotion_gate(tmp_path: Path) -> None:
    with client_for(tmp_path) as client:
        recommendation = client.post(
            "/v1/model-recommendations",
            json={
                "messages": [{"role": "user", "content": "Write a welcome email"}],
                "feedback_profile_id": "local-default",
            },
        ).json()
        configuration_id = recommendation["recommendations"][0]["configuration"][
            "configuration_id"
        ]
        feedback = client.post(
            f"/v1/model-recommendations/{recommendation['recommendation_id']}/feedback",
            json={
                "used_recommendation": True,
                "used_configuration_id": configuration_id,
                "outcome": "worked",
            },
        )
        feedback_id = feedback.json()["feedback_id"]
        exported = client.get("/v1/feedback/export")
        assert exported.status_code == 200
        assert exported.json()["prompt_included"] is False
        assert len(exported.json()["items"]) == 1

        promotion = client.post(
            "/v1/feedback/personalization/promote",
            json={"feedback_profile_id": "local-default"},
        )
        assert promotion.json()["decision"] == "insufficient_data"
        assert promotion.json()["personalization_enabled"] is False
        assert promotion.json()["promotion_id"]
        assert client.get("/v1/feedback/history").json()["prompt_included"] is False
        audit = client.get("/v1/feedback/personalization/audit").json()["items"]
        assert audit[0]["decision"] == "insufficient_data"

        rollback = client.post(
            "/v1/feedback/personalization/rollback",
            json={"feedback_profile_id": "local-default"},
        )
        assert rollback.status_code == 200
        assert rollback.json()["decision"] == "rolled_back"

        deleted = client.delete(f"/v1/feedback/{feedback_id}")
        assert deleted.json()["deleted"] == 1
        disabled = client.patch(
            "/v1/feedback/settings", json={"feedback_enabled": False}
        )
        assert disabled.json()["feedback_enabled"] is False
        rejected = client.post(
            f"/v1/model-recommendations/{recommendation['recommendation_id']}/feedback",
            json={
                "used_recommendation": True,
                "used_configuration_id": configuration_id,
                "outcome": "worked",
            },
        )
        assert rejected.status_code == 409
