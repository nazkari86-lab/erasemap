import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from external_temporal_challenge.core import read_object, validate_public_suite
from external_temporal_challenge.runner import current_erasemap_commit, run
from external_temporal_challenge.runner import main as runner_main
from external_temporal_challenge.score import main as score_main
from external_temporal_challenge.score import score
from external_temporal_challenge.seal import main as seal_main
from external_temporal_challenge.seal import seal


def _author(*, independent: bool = False) -> dict:
    return {
        "name": "External Example",
        "organization": "Example Lab",
        "public_identifier": "https://example.org/evaluator",
        "independently_authored": independent,
        "external_repository": "https://example.org/external-suite.git",
        "external_commit": "1" * 40,
    }


def _case(case_id: str, *, initial: list[str], expected: str, cost: int | None) -> dict:
    return {
        "case_id": case_id,
        "family": f"family-{case_id}",
        "initial_facts": initial,
        "residual_facts": ["db"],
        "transitions": [
            {
                "id": "restore",
                "requires": ["backup"],
                "adds": ["db"],
                "removes": [],
                "forbids": [],
            }
        ],
        "coverage": {
            "required_sensor_ids": ["sensor"],
            "observations": [
                {
                    "id": "attestation",
                    "sensor_id": "sensor",
                    "transition_id": "restore",
                    "verified": True,
                }
            ],
        },
        "controls": [
            {
                "id": "filter",
                "cost": 2,
                "guarded_transition_ids": ["restore"],
                "permitted": True,
            }
        ],
        "expected": {"verdict": expected, "minimum_cost": cost},
    }


def test_commit_blind_run_reveal_and_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "external_temporal_challenge.runner.current_erasemap_commit", lambda: "a" * 40
    )
    authored = {
        "schema_version": "erasemap-external-temporal-suite-v1",
        "author": _author(),
        "cases": [
            _case("risk", initial=["backup"], expected="REGENERATION_RISK", cost=2),
            _case("safe", initial=[], expected="RSE_VERIFIED", cost=0),
        ],
    }
    authored_path = tmp_path / "authored.json"
    authored_path.write_text(json.dumps(authored))
    sealed = tmp_path / "sealed"
    seal(authored_path, sealed)
    public_text = (sealed / "public-cases.json").read_text()
    assert "expected" not in public_text
    predictions = tmp_path / "predictions.json"
    run(sealed / "public-cases.json", predictions)
    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "gates": {
                    "minimum_case_count": 2,
                    "minimum_family_count": 2,
                    "minimum_nonverified_case_count": 1,
                    "minimum_accuracy": 1.0,
                    "maximum_false_verified_count": 0,
                    "minimum_cost_accuracy": 1.0,
                }
            }
        )
    )
    result = score(
        sealed / "public-cases.json",
        predictions,
        sealed / "answers.private.json",
        sealed / "commitment-manifest.json",
        protocol,
    )

    assert result["passed"]
    assert result["metrics"]["accuracy"] == 1.0

    strict_protocol = json.loads(protocol.read_text())
    strict_protocol["gates"]["require_independently_authored"] = True
    protocol.write_text(json.dumps(strict_protocol))
    assert not score(
        sealed / "public-cases.json",
        predictions,
        sealed / "answers.private.json",
        sealed / "commitment-manifest.json",
        protocol,
    )["gates"]["require_independently_authored"]


def test_command_entrypoints_and_tamper_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "external_temporal_challenge.runner.current_erasemap_commit", lambda: "a" * 40
    )
    authored = {
        "schema_version": "erasemap-external-temporal-suite-v1",
        "author": _author(),
        "cases": [_case("risk", initial=["backup"], expected="REGENERATION_RISK", cost=2)],
    }
    authored_path = tmp_path / "authored.json"
    authored_path.write_text(json.dumps(authored))
    sealed = tmp_path / "sealed"
    monkeypatch.setattr(
        sys, "argv", ["seal", str(authored_path), "--output", str(sealed)]
    )
    assert seal_main() == 0
    capsys.readouterr()
    predictions = tmp_path / "predictions.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["runner", str(sealed / "public-cases.json"), "--output", str(predictions)],
    )
    assert runner_main() == 0
    capsys.readouterr()
    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "gates": {
                    "minimum_case_count": 1,
                    "minimum_family_count": 1,
                    "minimum_nonverified_case_count": 1,
                    "minimum_accuracy": 1.0,
                    "maximum_false_verified_count": 0,
                    "minimum_cost_accuracy": 1.0,
                }
            }
        )
    )
    report = tmp_path / "score.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "score",
            "--public",
            str(sealed / "public-cases.json"),
            "--predictions",
            str(predictions),
            "--answers",
            str(sealed / "answers.private.json"),
            "--manifest",
            str(sealed / "commitment-manifest.json"),
            "--protocol",
            str(protocol),
            "--output",
            str(report),
        ],
    )
    assert score_main() == 0
    assert json.loads(report.read_text())["passed"]

    tampered = tmp_path / "tampered-answers.json"
    answer_payload = json.loads((sealed / "answers.private.json").read_text())
    answer_payload["answers"][0]["verdict"] = "RSE_VERIFIED"
    tampered.write_text(json.dumps(answer_payload))
    with pytest.raises(ValueError, match="commitment"):
        score(
            sealed / "public-cases.json",
            predictions,
            tampered,
            sealed / "commitment-manifest.json",
            protocol,
        )

    tampered_predictions = tmp_path / "tampered-predictions.json"
    prediction_payload = json.loads(predictions.read_text())
    prediction_payload["public_cases_sha256"] = "sha256:" + "0" * 64
    tampered_predictions.write_text(json.dumps(prediction_payload))
    with pytest.raises(ValueError, match="another public suite"):
        score(
            sealed / "public-cases.json",
            tampered_predictions,
            sealed / "answers.private.json",
            sealed / "commitment-manifest.json",
            protocol,
        )


def test_schema_validation_rejects_malformed_inputs(tmp_path: Path) -> None:
    non_object = tmp_path / "array.json"
    non_object.write_text("[]")
    with pytest.raises(ValueError, match="JSON object"):
        read_object(non_object)
    with pytest.raises(ValueError, match="schema"):
        validate_public_suite({"schema_version": "wrong"})

    valid_case = _case("one", initial=[], expected="RSE_VERIFIED", cost=0)
    valid_case.pop("expected")
    duplicate = {
        "schema_version": "erasemap-external-temporal-public-v1",
        "author": _author(),
        "cases": [valid_case, dict(valid_case)],
    }
    with pytest.raises(ValueError, match="duplicate"):
        validate_public_suite(duplicate)

    invalid_control = json.loads(json.dumps(valid_case))
    invalid_control["controls"][0]["guarded_transition_ids"] = ["unknown"]
    invalid_suite = {**duplicate, "cases": [invalid_control]}
    with pytest.raises(ValueError, match="unknown transition"):
        validate_public_suite(invalid_suite)


def test_commit_resolution_rejects_dirty_worktree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "external_temporal_challenge.runner.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=" M tracked.py\n"),
    )
    with pytest.raises(RuntimeError, match="clean"):
        current_erasemap_commit()
