from __future__ import annotations

from pathlib import Path

import pytest

from erasemap.external_cases import build_source_cases
from erasemap.external_evaluator import METHODS, evaluate_public_cases
from erasemap.holdout_commitment import commitment_payload, public_cases, verify_reveal
from erasemap.holdout_report import score_holdout, wilson95
from erasemap.source_lock import load_source_manifest


def _cases():  # type: ignore[no-untyped-def]
    return build_source_cases(load_source_manifest(Path("benchmark/external-sources-v1.json")))


def test_answer_blind_evaluator_and_primary_endpoint() -> None:
    cases = _cases()
    public = public_cases(cases)
    records = evaluate_public_cases(public)
    assert len(records) == len(cases) * len(METHODS)
    result = score_holdout(cases, records)
    assert result["decision"] == "PASS"
    pcug = result["metrics"]["pcug"]  # type: ignore[index]
    assert pcug["false_complete"] == 0
    assert pcug["false_complete_wilson95"][1] < 0.05


def test_commitment_rejects_changed_answer() -> None:
    cases = _cases()
    commitment = commitment_payload(cases, "sha256:protocol")
    changed = list(cases)
    changed.pop()
    with pytest.raises(ValueError):
        verify_reveal(commitment, tuple(changed), "sha256:protocol")


def test_wilson_known_boundary() -> None:
    assert wilson95(0, 100) is not None
    assert wilson95(0, 100)[1] < 0.05  # type: ignore[index]
    assert wilson95(0, 0) is None
