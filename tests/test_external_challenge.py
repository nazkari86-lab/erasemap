from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from external_challenge.seal import reveal_answers, seal_cases


def test_blind_package_hides_and_commits_answers() -> None:
    key = Fernet.generate_key()
    authored = [
        {
            "case": {"id": "external-001", "nodes": ["source", "backup"]},
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
