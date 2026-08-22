from __future__ import annotations

import json
import sys

from external_challenge.attest import (
    generate_keypair,
    main,
    sign_score,
    sign_submission,
    verify_attestation,
    verify_submission_attestation,
)


def test_external_score_attestation_detects_tampering() -> None:
    private, _ = generate_keypair()
    score = {"decision": "PASS", "false_complete": 0}
    attestation = sign_score(score, private, "reviewer-1", "external-lab")
    assert verify_attestation(score, attestation)
    assert not verify_attestation({"decision": "PASS", "false_complete": 1}, attestation)


def test_external_attestation_cli_round_trip(tmp_path, monkeypatch, capsys) -> None:
    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.txt"
    score_path = tmp_path / "score.json"
    attestation_path = tmp_path / "attestation.json"
    score_path.write_text(json.dumps({"decision": "PASS", "false_complete": 0}))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "attest.py",
            "generate",
            "--private-key",
            str(private_path),
            "--public-key",
            str(public_path),
        ],
    )
    assert main() == 0
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "attest.py",
            "sign",
            "--score",
            str(score_path),
            "--attestation",
            str(attestation_path),
            "--private-key",
            str(private_path),
            "--evaluator",
            "reviewer-1",
            "--affiliation",
            "external-lab",
        ],
    )
    assert main() == 0
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "attest.py",
            "verify",
            "--score",
            str(score_path),
            "--attestation",
            str(attestation_path),
        ],
    )
    assert main() == 0
    assert "attestation verified" in capsys.readouterr().out


def test_submission_attestation_binds_manifest_and_score() -> None:
    private, _ = generate_keypair()
    score = {"decision": "PASS", "false_complete": 0}
    manifest = {"evaluation_id": "external-1", "erasemap_commit": "a" * 40}
    attestation = sign_submission(score, private, manifest)
    assert verify_submission_attestation(score, manifest, attestation)
    assert not verify_submission_attestation(
        score, {**manifest, "erasemap_commit": "b" * 40}, attestation
    )
