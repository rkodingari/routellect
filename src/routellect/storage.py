from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from routellect.schemas import (
    BenchmarkRun,
    DeletionResult,
    FeedbackExport,
    FeedbackReplayReport,
    FeedbackRequest,
    FeedbackResponse,
    FeedbackSettings,
    FeedbackSettingsUpdate,
    PromotionAudit,
    RecommendationResponse,
)


class FeedbackDisabledError(ValueError):
    pass


class InvalidFeedbackError(ValueError):
    pass


class DuplicateFeedbackError(ValueError):
    pass


def data_dir() -> Path:
    path = Path(os.getenv("ROUTELLECT_DATA_DIR", "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or data_dir() / "routellect.sqlite3"

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS recommendation_receipts (
                    recommendation_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    catalog_version TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    privacy TEXT NOT NULL,
                    task_family TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    assessor_json TEXT NOT NULL,
                    selected_configuration_ids_json TEXT NOT NULL,
                    feedback_received INTEGER NOT NULL DEFAULT 0,
                    advisor_version TEXT NOT NULL DEFAULT 'deterministic-v1'
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    recommendation_id TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(recommendation_id)
                        REFERENCES recommendation_receipts(recommendation_id)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedback_settings (
                    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                    feedback_enabled INTEGER NOT NULL,
                    personalization_enabled INTEGER NOT NULL,
                    minimum_support INTEGER NOT NULL,
                    personalization_policy_version TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedback_promotions (
                    promotion_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    feedback_profile_id TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    policy_digest TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    metrics_json TEXT NOT NULL
                );
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(recommendation_receipts)")
            }
            if "feedback_profile_id" not in columns:
                connection.execute(
                    "ALTER TABLE recommendation_receipts ADD COLUMN feedback_profile_id TEXT"
                )
            if "advisor_version" not in columns:
                connection.execute(
                    """ALTER TABLE recommendation_receipts
                       ADD COLUMN advisor_version TEXT NOT NULL DEFAULT 'deterministic-v1'"""
                )
            setting_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(feedback_settings)")
            }
            if "personalization_policy_version" not in setting_columns:
                connection.execute(
                    """ALTER TABLE feedback_settings
                       ADD COLUMN personalization_policy_version TEXT"""
                )
            now = datetime.now(UTC).isoformat()
            connection.execute(
                """INSERT OR IGNORE INTO feedback_settings (
                       singleton_id, feedback_enabled, personalization_enabled,
                       minimum_support, personalization_policy_version, updated_at
                   ) VALUES (1, 1, 0, 5, NULL, ?)""",
                (now,),
            )

    def save_recommendation(
        self,
        response: RecommendationResponse,
        *,
        objective: str,
        privacy: str,
        feedback_profile_id: str | None = None,
    ) -> None:
        assessor = response.analysis.assessor.model_dump(mode="json")
        selected = [item.configuration.configuration_id for item in response.recommendations]
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO recommendation_receipts (
                    recommendation_id, created_at, catalog_version, objective, privacy,
                    task_family, difficulty, assessor_json, selected_configuration_ids_json,
                    feedback_profile_id, advisor_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response.recommendation_id,
                    response.created_at.isoformat(),
                    response.catalog_version,
                    objective,
                    privacy,
                    response.analysis.task_family,
                    response.analysis.difficulty,
                    json.dumps(assessor, separators=(",", ":")),
                    json.dumps(selected, separators=(",", ":")),
                    feedback_profile_id,
                    response.advisor_version,
                ),
            )

    def get_receipt(self, recommendation_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM recommendation_receipts WHERE recommendation_id = ?",
                (recommendation_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "recommendation_id": row["recommendation_id"],
            "created_at": row["created_at"],
            "non_executing": True,
            "catalog_version": row["catalog_version"],
            "objective": row["objective"],
            "privacy": row["privacy"],
            "task_family": row["task_family"],
            "difficulty": row["difficulty"],
            "assessor": json.loads(row["assessor_json"]),
            "selected_configuration_ids": json.loads(row["selected_configuration_ids_json"]),
            "feedback_profile_id": row["feedback_profile_id"],
            "advisor_version": row["advisor_version"],
            "feedback_received": bool(row["feedback_received"]),
        }

    def save_feedback(
        self, recommendation_id: str, feedback: FeedbackRequest
    ) -> FeedbackResponse | None:
        settings = self.get_feedback_settings()
        if not settings.feedback_enabled:
            raise FeedbackDisabledError("feedback collection is disabled")
        receipt = self.get_receipt(recommendation_id)
        if receipt is None:
            return None
        if receipt["feedback_received"]:
            raise DuplicateFeedbackError(
                "this recommendation already has feedback; delete it before replacing it"
            )
        selected = set(receipt["selected_configuration_ids"])
        if feedback.used_configuration_id and feedback.used_configuration_id not in selected:
            raise InvalidFeedbackError(
                "used_configuration_id must belong to this recommendation"
            )
        if (
            feedback.preferred_over_configuration_id
            and feedback.preferred_over_configuration_id not in selected
        ):
            raise InvalidFeedbackError(
                "preferred_over_configuration_id must belong to this recommendation"
            )
        recorded_at = datetime.now(UTC)
        response = FeedbackResponse(
            feedback_id=f"fb_{uuid4().hex}",
            recorded_at=recorded_at,
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO feedback VALUES (?, ?, ?, ?)",
                (
                    response.feedback_id,
                    recommendation_id,
                    recorded_at.isoformat(),
                    feedback.model_dump_json(),
                ),
            )
            connection.execute(
                """UPDATE recommendation_receipts
                   SET feedback_received = 1 WHERE recommendation_id = ?""",
                (recommendation_id,),
            )
        return response

    def get_feedback_settings(self) -> FeedbackSettings:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM feedback_settings WHERE singleton_id = 1"
            ).fetchone()
        if row is None:
            raise RuntimeError("feedback settings are not initialized")
        return FeedbackSettings(
            feedback_enabled=bool(row["feedback_enabled"]),
            personalization_enabled=bool(row["personalization_enabled"]),
            minimum_support=int(row["minimum_support"]),
            personalization_policy_version=row["personalization_policy_version"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def update_feedback_settings(self, update: FeedbackSettingsUpdate) -> FeedbackSettings:
        current = self.get_feedback_settings()
        feedback_enabled = (
            current.feedback_enabled
            if update.feedback_enabled is None
            else update.feedback_enabled
        )
        personalization_enabled = (
            current.personalization_enabled
            if update.personalization_enabled is None
            else update.personalization_enabled
        )
        if personalization_enabled and not current.personalization_enabled:
            raise ValueError(
                "enable personalization through the offline replay promotion endpoint"
            )
        if personalization_enabled and not feedback_enabled:
            raise ValueError("personalization requires feedback collection to be enabled")
        if not feedback_enabled:
            personalization_enabled = False
        policy_version = (
            current.personalization_policy_version if personalization_enabled else None
        )
        now = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """UPDATE feedback_settings
                   SET feedback_enabled = ?, personalization_enabled = ?,
                       personalization_policy_version = ?, updated_at = ?
                   WHERE singleton_id = 1""",
                (
                    int(feedback_enabled),
                    int(personalization_enabled),
                    policy_version,
                    now.isoformat(),
                ),
            )
        return FeedbackSettings(
            feedback_enabled=feedback_enabled,
            personalization_enabled=personalization_enabled,
            minimum_support=current.minimum_support,
            personalization_policy_version=policy_version,
            updated_at=now,
        )

    def set_personalization_promoted(
        self, enabled: bool, policy_version: str | None = None
    ) -> FeedbackSettings:
        current = self.get_feedback_settings()
        if enabled and not current.feedback_enabled:
            raise ValueError("personalization requires feedback collection to be enabled")
        if enabled and not policy_version:
            raise ValueError("promoted personalization requires a policy version")
        now = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """UPDATE feedback_settings
                   SET personalization_enabled = ?, personalization_policy_version = ?,
                       updated_at = ?
                   WHERE singleton_id = 1""",
                (int(enabled), policy_version if enabled else None, now.isoformat()),
            )
        return FeedbackSettings(
            feedback_enabled=current.feedback_enabled,
            personalization_enabled=enabled,
            minimum_support=current.minimum_support,
            personalization_policy_version=policy_version if enabled else None,
            updated_at=now,
        )

    def record_promotion(self, report: FeedbackReplayReport) -> FeedbackReplayReport:
        promotion_id = f"promo_{uuid4().hex}"
        created_at = datetime.now(UTC)
        metrics = {
            "event_count": report.event_count,
            "training_count": report.training_count,
            "holdout_count": report.holdout_count,
            "baseline_brier": report.baseline_brier,
            "candidate_brier": report.candidate_brier,
            "bias_guard_passed": report.bias_guard_passed,
            "slice_metrics": report.slice_metrics,
        }
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO feedback_promotions VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    promotion_id,
                    created_at.isoformat(),
                    report.feedback_profile_id,
                    report.policy_version,
                    report.policy_digest,
                    report.decision,
                    json.dumps(metrics, separators=(",", ":"), sort_keys=True),
                ),
            )
        return report.model_copy(update={"promotion_id": promotion_id})

    def rollback_personalization(self, profile_id: str) -> PromotionAudit:
        current = self.get_feedback_settings()
        policy_version = current.personalization_policy_version or "feedback-bayes-v1"
        settings = self.set_personalization_promoted(False)
        del settings
        promotion_id = f"promo_{uuid4().hex}"
        created_at = datetime.now(UTC)
        from routellect.learning import feedback_policy_digest

        digest = feedback_policy_digest(self.get_feedback_settings().minimum_support)
        metrics = {"previous_policy_version": current.personalization_policy_version}
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO feedback_promotions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    promotion_id,
                    created_at.isoformat(),
                    profile_id,
                    policy_version,
                    digest,
                    "rolled_back",
                    json.dumps(metrics, separators=(",", ":"), sort_keys=True),
                ),
            )
        return PromotionAudit(
            promotion_id=promotion_id,
            created_at=created_at,
            feedback_profile_id=profile_id,
            policy_version=policy_version,
            policy_digest=digest,
            decision="rolled_back",
            metrics=metrics,
        )

    def list_promotions(self) -> list[PromotionAudit]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM feedback_promotions
                   ORDER BY created_at DESC LIMIT 100"""
            ).fetchall()
        return [
            PromotionAudit(
                promotion_id=row["promotion_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                feedback_profile_id=row["feedback_profile_id"],
                policy_version=row["policy_version"],
                policy_digest=row["policy_digest"],
                decision=row["decision"],
                metrics=json.loads(row["metrics_json"]),
            )
            for row in rows
        ]

    def export_feedback(self) -> FeedbackExport:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT f.feedback_id, f.recorded_at, f.payload_json,
                       r.recommendation_id, r.created_at, r.catalog_version,
                       r.task_family, r.difficulty, r.feedback_profile_id,
                       r.selected_configuration_ids_json
                FROM feedback AS f
                JOIN recommendation_receipts AS r
                  ON r.recommendation_id = f.recommendation_id
                ORDER BY f.recorded_at
                """
            ).fetchall()
        items = []
        for row in rows:
            items.append(
                {
                    "feedback_id": row["feedback_id"],
                    "recorded_at": row["recorded_at"],
                    "recommendation_id": row["recommendation_id"],
                    "recommendation_created_at": row["created_at"],
                    "catalog_version": row["catalog_version"],
                    "task_family": row["task_family"],
                    "difficulty": row["difficulty"],
                    "feedback_profile_id": row["feedback_profile_id"],
                    "selected_configuration_ids": json.loads(
                        row["selected_configuration_ids_json"]
                    ),
                    "outcome": json.loads(row["payload_json"]),
                }
            )
        return FeedbackExport(
            exported_at=datetime.now(UTC),
            settings=self.get_feedback_settings(),
            items=items,
        )

    def delete_feedback(self, feedback_id: str) -> DeletionResult:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT recommendation_id FROM feedback WHERE feedback_id = ?",
                (feedback_id,),
            ).fetchone()
            cursor = connection.execute(
                "DELETE FROM feedback WHERE feedback_id = ?", (feedback_id,)
            )
            if row is not None:
                connection.execute(
                    """UPDATE recommendation_receipts SET feedback_received =
                       EXISTS(SELECT 1 FROM feedback WHERE recommendation_id = ?)
                       WHERE recommendation_id = ?""",
                    (row["recommendation_id"], row["recommendation_id"]),
                )
        return DeletionResult(deleted=cursor.rowcount)

    def reset_feedback(self) -> DeletionResult:
        with self._connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            connection.execute("DELETE FROM feedback")
            connection.execute("UPDATE recommendation_receipts SET feedback_received = 0")
        return DeletionResult(deleted=int(count))

    def feedback_outcomes(
        self, profile_id: str, task_family: str | None = None
    ) -> list[tuple[str, bool]]:
        with self._connect() as connection:
            query = """
                SELECT f.payload_json
                FROM feedback AS f
                JOIN recommendation_receipts AS r
                  ON r.recommendation_id = f.recommendation_id
                WHERE r.feedback_profile_id = ?
            """
            parameters: tuple[str, ...] = (profile_id,)
            if task_family is not None:
                query += " AND r.task_family = ?"
                parameters += (task_family,)
            query += " ORDER BY f.recorded_at"
            rows = connection.execute(query, parameters).fetchall()
        outcomes: list[tuple[str, bool]] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            configuration_id = payload.get("used_configuration_id")
            outcome = payload.get("outcome")
            if (
                payload.get("used_recommendation")
                and configuration_id
                and outcome in {"worked", "did_not_work"}
            ):
                outcomes.append((str(configuration_id), outcome == "worked"))
        return outcomes

    def feedback_events(self, profile_id: str) -> list[dict[str, str | bool]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT f.recorded_at, f.payload_json, r.task_family
                FROM feedback AS f
                JOIN recommendation_receipts AS r
                  ON r.recommendation_id = f.recommendation_id
                WHERE r.feedback_profile_id = ?
                ORDER BY f.recorded_at, f.feedback_id
                """,
                (profile_id,),
            ).fetchall()
        events: list[dict[str, str | bool]] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            configuration_id = payload.get("used_configuration_id")
            outcome = payload.get("outcome")
            if (
                payload.get("used_recommendation")
                and configuration_id
                and outcome in {"worked", "did_not_work"}
            ):
                events.append(
                    {
                        "recorded_at": str(row["recorded_at"]),
                        "task_family": str(row["task_family"]),
                        "configuration_id": str(configuration_id),
                        "success": outcome == "worked",
                    }
                )
        return events

    def save_benchmark(self, run: BenchmarkRun) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO benchmark_runs VALUES (?, ?, ?)",
                (run.run_id, run.created_at.isoformat(), run.model_dump_json()),
            )

    def get_benchmark(self, run_id: str) -> BenchmarkRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM benchmark_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return BenchmarkRun.model_validate_json(row[0]) if row else None

    def list_benchmarks(self) -> list[BenchmarkRun]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM benchmark_runs ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
        return [BenchmarkRun.model_validate_json(row[0]) for row in rows]

    def purge_older_than(
        self, days: int, *, now: datetime | None = None
    ) -> dict[str, int | str]:
        if days < 1:
            raise ValueError("retention days must be positive")
        reference = now or datetime.now(UTC)
        if reference.tzinfo is None:
            raise ValueError("retention reference time must include a timezone")
        cutoff = (reference - timedelta(days=days)).isoformat()
        with self._connect() as connection:
            feedback = connection.execute(
                "SELECT COUNT(*) FROM feedback WHERE recorded_at < ?", (cutoff,)
            ).fetchone()[0]
            receipts = connection.execute(
                """SELECT COUNT(*) FROM recommendation_receipts AS r
                   WHERE r.created_at < ?
                     AND NOT EXISTS (
                         SELECT 1 FROM feedback AS f
                         WHERE f.recommendation_id = r.recommendation_id
                           AND f.recorded_at >= ?
                     )""",
                (cutoff, cutoff),
            ).fetchone()[0]
            benchmarks = connection.execute(
                "SELECT COUNT(*) FROM benchmark_runs WHERE created_at < ?", (cutoff,)
            ).fetchone()[0]
            promotions = connection.execute(
                "SELECT COUNT(*) FROM feedback_promotions WHERE created_at < ?", (cutoff,)
            ).fetchone()[0]
            connection.execute("DELETE FROM feedback WHERE recorded_at < ?", (cutoff,))
            connection.execute(
                """DELETE FROM recommendation_receipts
                   WHERE created_at < ?
                     AND NOT EXISTS (
                         SELECT 1 FROM feedback
                         WHERE feedback.recommendation_id =
                               recommendation_receipts.recommendation_id
                           AND feedback.recorded_at >= ?
                     )""",
                (cutoff, cutoff),
            )
            connection.execute("DELETE FROM benchmark_runs WHERE created_at < ?", (cutoff,))
            connection.execute("DELETE FROM feedback_promotions WHERE created_at < ?", (cutoff,))
        return {
            "cutoff": cutoff,
            "feedback_deleted": int(feedback),
            "receipts_deleted": int(receipts),
            "benchmarks_deleted": int(benchmarks),
            "promotions_deleted": int(promotions),
        }

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection
