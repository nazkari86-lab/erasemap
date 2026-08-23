from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_tomography_results_are_verified_and_documented() -> None:
    local = json.loads(
        (ROOT / "outputs/erasure-tomography-v1/result.json").read_text()
    )
    redis = json.loads(
        (ROOT / "outputs/erasure-tomography-redis-v1/result.json").read_text()
    )
    readme = (ROOT / "README.md").read_text()
    report = (ROOT / "docs/ERASURE_TOMOGRAPHY_V1_REPORT.md").read_text()
    scorecard = (ROOT / "docs/COMPETITION_EVIDENCE_SCORECARD.md").read_text()

    assert local["passed"] and redis["passed"]
    assert local["metrics"]["exact_support_recovery_count"] == 8
    assert local["metrics"]["negative_case_pass_count"] == 4
    assert local["metrics"]["false_localization_count"] == 0
    assert redis["metrics"]["exact_support_recovery_count"] == 4
    assert redis["metrics"]["post_control_recurrence_count"] == 0
    assert "8/8" in readme and "4/4" in readme
    assert "3,584/3,584" in report
    assert "Narrow scientific novelty | 9.9/10" in scorecard
    assert "Independence of evidence | 7.8/10" in scorecard


def test_papers_include_tomography_claim_and_limit() -> None:
    english = (
        ROOT / "competition/paper/EraSeMap_scientific_paper_EN.md"
    ).read_text()
    russian = (
        ROOT / "competition/paper/EraSeMap_scientific_paper_RU.md"
    ).read_text()

    assert "### 8.8 Erasure Tomography" in english
    assert "not a new or superior" in english
    assert "### 8.8 Erasure Tomography" in russian
    assert "а не новый или лучший" in russian  # noqa: RUF001 - intentional Russian text
