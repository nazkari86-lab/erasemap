from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from external_ghostgraph_challenge.schema import public_suite, validate_suite
from external_ghostgraph_challenge.seal import seal_suite
from external_ghostgraph_challenge.verify import status


def _suite() -> dict[str, object]:
    kinds = (
        "in-catalogue-recurrence",
        "missing-evidence",
        "outside-catalogue",
        "path-equivalent",
        "safe",
    )
    return {
        "schema_version": "erasemap-external-ghostgraph-suite-v1",
        "author": {
            "name": "External Evaluator",
            "contact": "evaluator@example.org",
            "affiliation": "Example Lab",
            "project_member": False,
        },
        "cases": [
            {
                "case_id": f"case-{index}",
                "kind": kind,
                "observations": [],
                "evidence": {},
                "truth": {"expected_verdict": "UNVERIFIED"},
            }
            for index, kind in enumerate(kinds)
        ],
    }


def test_public_bundle_is_answer_blind_and_commitment_binds_truth() -> None:
    suite = _suite()
    sealed, commitment = seal_suite(suite, Fernet.generate_key())
    public = public_suite(suite)

    assert sealed
    assert commitment["case_count"] == 5
    assert "truth" not in json.dumps(public)
    assert all("truth" not in case for case in public["cases"])  # type: ignore[index]


def test_rejects_duplicate_or_project_authored_suite() -> None:
    suite = _suite()
    suite["cases"][1]["case_id"] = "case-0"  # type: ignore[index]
    with pytest.raises(ValueError, match="duplicate"):
        validate_suite(suite)

    suite = _suite()
    suite["author"]["project_member"] = True  # type: ignore[index]
    with pytest.raises(ValueError, match="not a project member"):
        validate_suite(suite)


def test_missing_external_bundle_is_explicitly_not_collected(tmp_path: Path) -> None:
    report = status(tmp_path / "absent")

    assert report["status"] == "NOT_COLLECTED"
    assert report["independent_evidence"] is False
