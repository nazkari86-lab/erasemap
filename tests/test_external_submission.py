from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from external_challenge.attest import generate_keypair, sign_submission
from external_challenge.runner import main as runner_main
from external_challenge.runner import predict_public_package
from external_challenge.seal import freeze_predictions, score_predictions, seal_cases
from external_challenge.submission import (
    INDEPENDENCE_STATEMENT,
    verify_submission,
)
from external_challenge.submission import main as submission_main
from scripts.verify_external_registry import verify_registry


def _public_case(index: int) -> dict[str, object]:
    incomplete = index < 100
    state = "ACTIVE" if incomplete else "ERASED"
    evidence_id = None if incomplete else "evidence-source"
    evidence = (
        []
        if incomplete
        else [
            {
                "artifact_id": "source",
                "commitment": "sha256:source",
                "id": "evidence-source",
                "issued_epoch": 990,
                "kind": "ABSENCE_CHECK",
                "observed_absent": True,
            }
        ]
    )
    return {
        "evidence": evidence,
        "family": f"external-family-{index % 4}",
        "graph": {
            "edges": [],
            "nodes": [
                {
                    "active_sink": incomplete,
                    "commitment": "sha256:source",
                    "evidence_id": evidence_id,
                    "id": "source",
                    "purpose": "external hidden evaluation",
                    "state": state,
                    "subject_id": "subject-1",
                    "type": "SOURCE_RECORD",
                }
            ],
        },
        "id": f"external-{index:03d}",
        "now_epoch": 1000,
        "subject_id": "subject-1",
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _submission(
    tmp_path: Path, tested_commit: str = "b" * 40
) -> tuple[Path, str, bytes]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    authored = [
        {
            "case": _public_case(index),
            "expected_path": ["source"] if index < 100 else None,
            "truth_verdict": "INCOMPLETE" if index < 100 else "COMPLETE",
        }
        for index in range(120)
    ]
    key = Fernet.generate_key()
    package = seal_cases(authored, key)
    predictions = predict_public_package(package)
    frozen = freeze_predictions(package, predictions)
    protocol_path = Path("external_challenge/protocol-v1.json")
    protocol = json.loads(protocol_path.read_text())
    score = score_predictions(package, key, frozen, protocol)
    submission = tmp_path / "submission"
    submission.mkdir()
    _write_json(submission / "public-package.json", package)
    _write_json(submission / "frozen-predictions.json", frozen)
    _write_json(submission / "score.json", score)
    (submission / "reveal-key.txt").write_text(base64.urlsafe_b64encode(key).decode() + "\n")
    manifest = {
        "affiliation": "Independent Systems Lab",
        "authorship_started_at": "2026-08-01T00:00:00Z",
        "challenge_commit": "a" * 40,
        "challenge_repository_url": "https://github.com/external-lab/hidden-erasemap-cases",
        "conflict_of_interest": "none_declared",
        "erasemap_commit": tested_commit,
        "evaluation_id": "external-lab-v1",
        "evaluator": "External Reviewer",
        "family_provenance": [
            {
                "family": f"external-family-{index}",
                "source_url": f"https://example.org/provenance/family-{index}",
            }
            for index in range(4)
        ],
        "file_sha256": {
            "frozen_predictions": _sha(submission / "frozen-predictions.json"),
            "public_package": _sha(submission / "public-package.json"),
            "reveal_key": _sha(submission / "reveal-key.txt"),
            "score": _sha(submission / "score.json"),
        },
        "identity_url": "https://example.org/researchers/external-reviewer",
        "independence_statement": INDEPENDENCE_STATEMENT,
        "labels_revealed_at": "2026-08-03T00:00:00Z",
        "predictions_frozen_at": "2026-08-02T00:00:00Z",
        "schema_version": "erasemap-independent-submission-v1",
    }
    _write_json(submission / "manifest.json", manifest)
    private, _ = generate_keypair()
    _write_json(submission / "attestation.json", sign_submission(score, private, manifest))
    return submission, tested_commit, private


def _resign(submission: Path, private: bytes) -> dict[str, object]:
    manifest = json.loads((submission / "manifest.json").read_text())
    score = json.loads((submission / "score.json").read_text())
    _write_json(submission / "attestation.json", sign_submission(score, private, manifest))
    return manifest


def test_public_runner_is_answer_blind_and_fail_closed(tmp_path: Path, monkeypatch) -> None:
    key = Fernet.generate_key()
    authored = [
        {"case": _public_case(0), "expected_path": ["source"], "truth_verdict": "INCOMPLETE"},
        {"case": _public_case(100), "expected_path": None, "truth_verdict": "COMPLETE"},
        {
            "case": {"family": "broken", "id": "broken"},
            "expected_path": None,
            "truth_verdict": "UNVERIFIED",
        },
    ]
    predictions = predict_public_package(seal_cases(authored, key))
    assert [item["verdict"] for item in predictions] == [
        "UNVERIFIED",
        "INCOMPLETE",
        "COMPLETE",
    ]
    package_path = tmp_path / "package.json"
    output_path = tmp_path / "predictions.json"
    _write_json(package_path, seal_cases(authored, key))
    monkeypatch.setattr(
        sys,
        "argv",
        ["runner.py", "--package", str(package_path), "--output", str(output_path)],
    )
    assert runner_main() == 0
    with pytest.raises(FileExistsError):
        runner_main()


def test_external_submission_recomputes_every_bound_artifact(tmp_path: Path) -> None:
    submission, tested_commit, _ = _submission(tmp_path)
    result = verify_submission(
        submission,
        Path("external_challenge/protocol-v1.json"),
        tested_commit,
    )
    assert result["technical_decision"] == "PASS"
    assert result["independence_decision"] == "PENDING_IDENTITY_AND_CONFLICT_REVIEW"
    assert result["total_cases"] == 120
    assert result["false_complete"] == 0


def test_external_submission_rejects_tampering_and_wrong_commit(tmp_path: Path) -> None:
    submission, tested_commit, _ = _submission(tmp_path)
    with pytest.raises(ValueError, match="different EraSeMap commit"):
        verify_submission(
            submission,
            Path("external_challenge/protocol-v1.json"),
            "c" * 40,
        )
    score_path = submission / "score.json"
    score_path.write_text(score_path.read_text() + " ")
    with pytest.raises(ValueError, match="file hash mismatch"):
        verify_submission(
            submission,
            Path("external_challenge/protocol-v1.json"),
            tested_commit,
        )


def test_external_submission_rejects_project_owned_challenge_repo(tmp_path: Path) -> None:
    submission, tested_commit, _ = _submission(tmp_path)
    manifest_path = submission / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["challenge_repository_url"] = "https://github.com/nazkari86-lab/erasemap"
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="must be external"):
        verify_submission(
            submission,
            Path("external_challenge/protocol-v1.json"),
            tested_commit,
        )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.update({"evaluation_id": ""}), "evaluation_id is required"),
        (lambda value: value.update({"identity_url": "http://invalid"}), "absolute HTTPS"),
        (lambda value: value.update({"challenge_commit": "short"}), "hexadecimal commit"),
        (lambda value: value.update({"conflict_of_interest": "unknown"}), "none_declared"),
        (lambda value: value.update({"independence_statement": "trust me"}), "statement"),
        (
            lambda value: value.update({"labels_revealed_at": "2026-08-01T00:00:00Z"}),
            "authorship < prediction freeze < label reveal",
        ),
        (lambda value: value.update({"family_provenance": "invalid"}), "must be an array"),
        (lambda value: value.update({"file_sha256": {}}), "must bind every"),
    ],
)
def test_external_submission_rejects_invalid_manifest(
    tmp_path: Path,
    mutate: Callable[[dict[str, object]], None],
    message: str,
) -> None:
    submission, tested_commit, _ = _submission(tmp_path)
    manifest_path = submission / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    mutate(manifest)
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match=message):
        verify_submission(
            submission,
            Path("external_challenge/protocol-v1.json"),
            tested_commit,
        )


def test_external_submission_rejects_prediction_score_key_and_signature_tampering(
    tmp_path: Path,
) -> None:
    submission, tested_commit, private = _submission(tmp_path)
    frozen_path = submission / "frozen-predictions.json"
    frozen = json.loads(frozen_path.read_text())
    frozen["predictions"][0]["verdict"] = "COMPLETE"
    _write_json(frozen_path, frozen)
    manifest = json.loads((submission / "manifest.json").read_text())
    manifest["file_sha256"]["frozen_predictions"] = _sha(frozen_path)
    _write_json(submission / "manifest.json", manifest)
    _resign(submission, private)
    with pytest.raises(ValueError, match="frozen predictions"):
        verify_submission(
            submission,
            Path("external_challenge/protocol-v1.json"),
            tested_commit,
        )

    submission, tested_commit, private = _submission(tmp_path / "score-case")
    score_path = submission / "score.json"
    score = json.loads(score_path.read_text())
    score["verdict_accuracy"] = 0.0
    _write_json(score_path, score)
    manifest = json.loads((submission / "manifest.json").read_text())
    manifest["file_sha256"]["score"] = _sha(score_path)
    _write_json(submission / "manifest.json", manifest)
    _resign(submission, private)
    with pytest.raises(ValueError, match="score does not match"):
        verify_submission(
            submission,
            Path("external_challenge/protocol-v1.json"),
            tested_commit,
        )

    submission, tested_commit, private = _submission(tmp_path / "key-case")
    key_path = submission / "reveal-key.txt"
    key_path.write_text("not-valid-base64!\n")
    manifest = json.loads((submission / "manifest.json").read_text())
    manifest["file_sha256"]["reveal_key"] = _sha(key_path)
    _write_json(submission / "manifest.json", manifest)
    _resign(submission, private)
    with pytest.raises(ValueError, match="reveal key encoding"):
        verify_submission(
            submission,
            Path("external_challenge/protocol-v1.json"),
            tested_commit,
        )

    submission, tested_commit, _ = _submission(tmp_path / "signature-case")
    attestation_path = submission / "attestation.json"
    attestation = json.loads(attestation_path.read_text())
    attestation["signature"] = "AAAA"
    _write_json(attestation_path, attestation)
    with pytest.raises(ValueError, match="attestation"):
        verify_submission(
            submission,
            Path("external_challenge/protocol-v1.json"),
            tested_commit,
        )


def test_external_submission_cli_writes_technical_report(
    tmp_path: Path, monkeypatch
) -> None:
    submission, tested_commit, _ = _submission(tmp_path)
    output = tmp_path / "technical-report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "submission.py",
            "--submission",
            str(submission),
            "--expected-erasemap-commit",
            tested_commit,
            "--output",
            str(output),
        ],
    )
    assert submission_main() == 0
    assert json.loads(output.read_text())["technical_decision"] == "PASS"


def test_external_registry_requires_unchanged_ancestor_commit(tmp_path: Path) -> None:
    tested_commit = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    _submission(tmp_path, tested_commit)
    reports = verify_registry(tmp_path, Path("external_challenge/protocol-v1.json"))
    assert reports[0]["technical_decision"] == "PASS"
    with pytest.raises(ValueError, match="no submission"):
        verify_registry(tmp_path / "empty", Path("external_challenge/protocol-v1.json"))
