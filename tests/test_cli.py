import json

import pytest

from routellect.advisor import Advisor
from routellect.cli import main
from routellect.schemas import PromptMessage, RecommendationRequest


def test_cli_and_advisor_recommend_the_same_configuration(capsys) -> None:  # type: ignore[no-untyped-def]
    prompt = "Review this Python concurrency design and identify race conditions"
    assert main(["advise", prompt, "--json"]) == 0
    cli_response = json.loads(capsys.readouterr().out)
    direct_response = Advisor().recommend(
        RecommendationRequest(messages=[PromptMessage(role="user", content=prompt)])
    )
    assert cli_response["recommendations"][0]["configuration"]["configuration_id"] == (
        direct_response.recommendations[0].configuration.configuration_id
    )


def test_catalog_command_returns_version(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["catalog"]) == 0
    assert json.loads(capsys.readouterr().out)["catalog_version"]


def test_cli_has_no_alternate_policy_selector(capsys) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SystemExit) as error:
        main(["advise", "Draft a concise email", "--policy-version", "v3", "--json"])
    assert error.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err
