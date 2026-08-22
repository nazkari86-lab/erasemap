from __future__ import annotations

import json
import sys

from external_challenge.attest import generate_keypair, main, sign_score, verify_attestation


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
