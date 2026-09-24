from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from routellect.advisor import Advisor
from routellect.backup import create_backup, restore_backup
from routellect.catalog import CatalogManager
from routellect.learning import FeedbackLearner
from routellect.schemas import (
    AssessorMode,
    FeedbackSettingsUpdate,
    Objective,
    Privacy,
    PromptMessage,
    RecommendationRequest,
)
from routellect.storage import Store


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="routellect", description="Know the right model before you run."
    )
    commands = root.add_subparsers(dest="command", required=True)
    advise = commands.add_parser("advise", help="Recommend a model without executing it")
    advise.add_argument("prompt", help="Prompt to analyze")
    advise.add_argument(
        "--objective", choices=[item.value for item in Objective], default="balanced"
    )
    advise.add_argument(
        "--privacy", choices=[item.value for item in Privacy], default="no_training"
    )
    advise.add_argument("--assessor", choices=[item.value for item in AssessorMode], default="off")
    advise.add_argument("--output-tokens", type=int, default=1000)
    advise.add_argument("--max-cost", type=float)
    advise.add_argument("--feedback-profile")
    advise.add_argument(
        "--policy-version",
        choices=("v2", "v3"),
        default="v2",
        help="Use v2 (production) or the explicit v3 experimental candidate",
    )
    advise.add_argument("--json", action="store_true", dest="as_json")

    catalog = commands.add_parser("catalog", help="Inspect or manage offline catalogs")
    catalog_commands = catalog.add_subparsers(dest="catalog_command")
    catalog_import = catalog_commands.add_parser(
        "import", help="Verify and activate a signed catalog file"
    )
    catalog_import.add_argument("envelope", type=Path)
    catalog_import.add_argument(
        "--public-key",
        type=Path,
        required=True,
        help="File containing the trusted base64 Ed25519 public key",
    )
    catalog_commands.add_parser("rollback", help="Restore the previous catalog snapshot")

    feedback = commands.add_parser("feedback", help="Manage private local feedback")
    feedback_commands = feedback.add_subparsers(dest="feedback_command", required=True)
    feedback_commands.add_parser("status")
    feedback_export = feedback_commands.add_parser("export")
    feedback_export.add_argument("--output", type=Path)
    feedback_reset = feedback_commands.add_parser("reset")
    feedback_reset.add_argument("--yes", action="store_true")
    feedback_toggle = feedback_commands.add_parser("enable")
    feedback_toggle.add_argument(
        "feature", choices=["collection", "personalization"]
    )
    feedback_disable = feedback_commands.add_parser("disable")
    feedback_disable.add_argument(
        "feature", choices=["collection", "personalization"]
    )

    admin = commands.add_parser("admin", help="Back up, restore, or retain local data")
    admin_commands = admin.add_subparsers(dest="admin_command", required=True)
    backup = admin_commands.add_parser("backup", help="Create a checksummed local backup")
    backup.add_argument("archive", type=Path)
    backup.add_argument("--data-dir", type=Path)
    restore = admin_commands.add_parser("restore", help="Restore into an empty data directory")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--data-dir", type=Path, required=True)
    restore.add_argument("--yes", action="store_true")
    purge = admin_commands.add_parser("purge", help="Delete derived records older than a policy")
    purge.add_argument("--older-than-days", type=int, required=True)
    purge.add_argument("--data-dir", type=Path)
    purge.add_argument("--yes", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "admin":
        return _admin_command(args)
    manager = CatalogManager()
    store = Store()
    store.initialize()
    if args.command == "catalog":
        return _catalog_command(args, manager)
    if args.command == "feedback":
        return _feedback_command(args, store)
    request = RecommendationRequest(
        messages=[PromptMessage(role="user", content=args.prompt)],
        objective=Objective(args.objective),
        privacy=Privacy(args.privacy),
        assessor_mode=AssessorMode(args.assessor),
        expected_output_tokens=args.output_tokens,
        max_cost_usd=args.max_cost,
        feedback_profile_id=args.feedback_profile,
    )
    active_advisor = Advisor(
        catalog=manager.current(),
        feedback_signals=FeedbackLearner(store).signals,
        policy_version=args.policy_version,
    )
    try:
        response = active_advisor.recommend(request)
    except ValueError as exc:
        print(f"Unable to recommend: {exc}", file=sys.stderr)
        return 2
    if args.as_json:
        print(response.model_dump_json(indent=2))
        return 0
    primary = response.recommendations[0]
    print(f"Use: {primary.configuration.display_name}")
    print(f"Configuration: {json.dumps(primary.configuration.settings, sort_keys=True)}")
    print(f"Why: {' '.join(primary.reasons)}")
    print(
        f"Expected: quality {primary.quality.expected:.2f}, "
        f"cost ${primary.cost.expected:.6f}, latency {primary.latency.expected:.0f} ms"
    )
    print(
        f"Assessor: {response.analysis.assessor.status} "
        f"({response.analysis.assessor.latency_ms:.1f} ms)"
    )
    for alternative in response.recommendations[1:]:
        print(f"Alternative: {alternative.configuration.display_name}")
    print(f"Catalog: {response.catalog_version} as of {response.catalog_observed_at.date()}")
    print("Advisory only — no model was called.")
    return 0


def _catalog_command(args: argparse.Namespace, manager: CatalogManager) -> int:
    if args.catalog_command is None:
        print(manager.summary().model_dump_json(indent=2))
        return 0
    try:
        if args.catalog_command == "import":
            payload = json.loads(args.envelope.read_text(encoding="utf-8"))
            public_key = args.public_key.read_text(encoding="utf-8").strip()
            previous, summary = manager.import_envelope(
                payload, public_key_b64=public_key, persist_public_key=True
            )
            print(f"Activated {summary.catalog_version}; previous catalog was {previous}.")
        else:
            replaced, summary = manager.rollback()
            print(f"Rolled back {replaced} to {summary.catalog_version}.")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Catalog operation failed: {exc}", file=sys.stderr)
        return 2
    return 0


def _feedback_command(args: argparse.Namespace, store: Store) -> int:
    if args.feedback_command == "status":
        print(store.get_feedback_settings().model_dump_json(indent=2))
        return 0
    if args.feedback_command == "export":
        exported = store.export_feedback().model_dump_json(indent=2)
        if args.output:
            args.output.write_text(exported + "\n", encoding="utf-8")
            print(f"Exported feedback to {args.output}.")
        else:
            print(exported)
        return 0
    if args.feedback_command == "reset":
        if not args.yes:
            print("Refusing to reset without --yes.", file=sys.stderr)
            return 2
        result = store.reset_feedback()
        print(f"Deleted {result.deleted} feedback item(s).")
        return 0
    enabled = args.feedback_command == "enable"
    update = (
        FeedbackSettingsUpdate(feedback_enabled=enabled)
        if args.feature == "collection"
        else FeedbackSettingsUpdate(personalization_enabled=enabled)
    )
    try:
        settings = store.update_feedback_settings(update)
    except ValueError as exc:
        print(f"Feedback setting failed: {exc}", file=sys.stderr)
        return 2
    print(settings.model_dump_json(indent=2))
    return 0


def _admin_command(args: argparse.Namespace) -> int:
    data_directory = args.data_dir or Path(os.getenv("ROUTELLECT_DATA_DIR", "data"))
    try:
        if args.admin_command == "backup":
            result = create_backup(data_directory, args.archive)
        elif args.admin_command == "restore":
            if not args.yes:
                print("Refusing to restore without --yes.", file=sys.stderr)
                return 2
            result = restore_backup(args.archive, data_directory)
        else:
            if not args.yes:
                print("Refusing to purge without --yes.", file=sys.stderr)
                return 2
            store = Store(data_directory / "routellect.sqlite3")
            store.initialize()
            result = store.purge_older_than(args.older_than_days)
    except (OSError, ValueError) as exc:
        print(f"Admin operation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
