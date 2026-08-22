from __future__ import annotations

import json
import sys

import pytest
from cryptography.fernet import Fernet

from external_challenge.seal import (
    freeze_predictions,
    reveal_answers,
    score_predictions,
    seal_cases,
)
from external_challenge.seal import main as seal_main


def test_blind_package_hides_and_commits_answers() -> None:
    key = Fernet.generate_key()
    authored = [
        {
            "case": {
                "family": "external-family",
                "id": "external-001",
                "nodes": ["source", "backup"],
            },
            "expected_path": ["source", "backup"],
            "truth_verdict": "INCOMPLETE",
        }
    ]
    package = seal_cases(authored, key)
    assert "truth_verdict" not in str(package["public_cases"])
    assert "INCOMPLETE" not in str(package)
    answers = reveal_answers(package, key)
    assert answers[0]["truth_verdict"] == "INCOMPLETE"
    with pytest.raises(ValueError):
        reveal_answers(package, Fernet.generate_key())


def test_freeze_and_score_enforce_blind_statistical_gate() -> None:
    key = Fernet.generate_key()
    authored = [
        {
            "case": {"family": f"family-{index % 4}", "id": f"external-{index:03d}"},
            "expected_path": ["subject", "residual"] if index < 100 else None,
            "truth_verdict": "INCOMPLETE" if index < 100 else "COMPLETE",
        }
        for index in range(120)
    ]
    package = seal_cases(authored, key)
    predictions = [
        {
            "id": f"external-{index:03d}",
            "shortest_path": ["subject", "residual"] if index < 100 else None,
            "verdict": "INCOMPLETE" if index < 100 else "COMPLETE",
        }
        for index in reversed(range(120))
    ]
    frozen = freeze_predictions(package, predictions)
    protocol = {
        "maximum_false_complete_wilson95_upper": 0.05,
        "minimum_cases": 120,
        "minimum_distinct_families": 4,
        "minimum_exact_path_rate": 0.8,
        "minimum_noncomplete_cases": 100,
        "minimum_verdict_accuracy": 0.9,
        "schema_version": "erasemap-external-challenge-protocol-v1",
    }
    result = score_predictions(package, key, frozen, protocol)
    assert result["decision"] == "PASS"
    assert result["false_complete"] == 0
    assert result["false_complete_wilson95"][1] < 0.05
    assert result["verdict_accuracy"] == 1.0
    assert result["exact_path_rate"] == 1.0


def test_freeze_rejects_missing_case_and_score_rejects_tampering() -> None:
    key = Fernet.generate_key()
    authored = [
        {
            "case": {"family": "external-family", "id": "external-001"},
            "expected_path": None,
            "truth_verdict": "COMPLETE",
        }
    ]
    package = seal_cases(authored, key)
    with pytest.raises(ValueError, match="cover every public case"):
        freeze_predictions(package, [])
    frozen = freeze_predictions(
        package, [{"id": "external-001", "shortest_path": None, "verdict": "COMPLETE"}]
    )
    frozen["predictions"][0]["verdict"] = "INCOMPLETE"
    protocol = {
        "maximum_false_complete_wilson95_upper": 0.05,
        "minimum_cases": 1,
        "minimum_distinct_families": 1,
        "minimum_exact_path_rate": 0.0,
        "minimum_noncomplete_cases": 1,
        "minimum_verdict_accuracy": 0.0,
        "schema_version": "erasemap-external-challenge-protocol-v1",
    }
    with pytest.raises(ValueError, match="prediction commitment"):
        score_predictions(package, key, frozen, protocol)


def test_seal_rejects_invalid_truth_contract() -> None:
    key = Fernet.generate_key()
    invalid = [
        {
            "case": {"family": "external", "id": "case-1"},
            "expected_path": "not-a-path",
            "truth_verdict": "COMPLETE",
        }
    ]
    with pytest.raises(ValueError, match="expected_path"):
        seal_cases(invalid, key)
    invalid[0]["expected_path"] = None
    invalid[0]["truth_verdict"] = "MAYBE"
    with pytest.raises(ValueError, match="truth verdict"):
        seal_cases(invalid, key)


def test_score_rejects_invalid_threshold_protocol() -> None:
    key = Fernet.generate_key()
    authored = [
        {
            "case": {"family": "external", "id": "case-1"},
            "expected_path": ["source"],
            "truth_verdict": "INCOMPLETE",
        }
    ]
    package = seal_cases(authored, key)
    frozen = freeze_predictions(
        package,
        [{"id": "case-1", "shortest_path": ["source"], "verdict": "INCOMPLETE"}],
    )
    protocol = {
        "maximum_false_complete_wilson95_upper": 0.05,
        "minimum_cases": 1,
        "minimum_distinct_families": 1,
        "minimum_exact_path_rate": 0.0,
        "minimum_noncomplete_cases": 1,
        "minimum_verdict_accuracy": 0.0,
        "schema_version": "erasemap-external-challenge-protocol-v1",
    }
    protocol["minimum_cases"] = 0
    with pytest.raises(ValueError, match="positive integers"):
        score_predictions(package, key, frozen, protocol)
    protocol["minimum_cases"] = 1
    protocol["minimum_verdict_accuracy"] = 2.0
    with pytest.raises(ValueError, match="between zero and one"):
        score_predictions(package, key, frozen, protocol)
    protocol["minimum_verdict_accuracy"] = 0.0
    protocol["minimum_noncomplete_cases"] = 2
    with pytest.raises(ValueError, match="cannot exceed"):
        score_predictions(package, key, frozen, protocol)


def test_external_challenge_cli_round_trip(tmp_path, monkeypatch) -> None:
    authored = [
        {
            "case": {"family": f"family-{index % 4}", "id": f"case-{index:03d}"},
            "expected_path": ["source", "residual"] if index < 100 else None,
            "truth_verdict": "INCOMPLETE" if index < 100 else "COMPLETE",
        }
        for index in range(120)
    ]
    predictions = [
        {
            "id": f"case-{index:03d}",
            "shortest_path": ["source", "residual"] if index < 100 else None,
            "verdict": "INCOMPLETE" if index < 100 else "COMPLETE",
        }
        for index in range(120)
    ]
    authored_path = tmp_path / "authored.json"
    predictions_path = tmp_path / "predictions.json"
    package_path = tmp_path / "package.json"
    frozen_path = tmp_path / "frozen.json"
    score_path = tmp_path / "score.json"
    reveal_path = tmp_path / "reveal.json"
    key_path = tmp_path / "key.txt"
    authored_path.write_text(json.dumps(authored))
    predictions_path.write_text(json.dumps(predictions))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "seal.py",
            "seal",
            "--input",
            str(authored_path),
            "--output",
            str(package_path),
            "--key-file-out",
            str(key_path),
        ],
    )
    assert seal_main() == 0
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "seal.py",
            "freeze",
            "--package",
            str(package_path),
            "--input",
            str(predictions_path),
            "--output",
            str(frozen_path),
        ],
    )
    assert seal_main() == 0
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "seal.py",
            "score",
            "--package",
            str(package_path),
            "--input",
            str(frozen_path),
            "--key-file",
            str(key_path),
            "--protocol",
            "external_challenge/protocol-v1.json",
            "--output",
            str(score_path),
        ],
    )
    assert seal_main() == 0
    assert json.loads(score_path.read_text())["decision"] == "PASS"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "seal.py",
            "reveal",
            "--input",
            str(package_path),
            "--key-file",
            str(key_path),
            "--output",
            str(reveal_path),
        ],
    )
    assert seal_main() == 0
    assert len(json.loads(reveal_path.read_text())) == 120
