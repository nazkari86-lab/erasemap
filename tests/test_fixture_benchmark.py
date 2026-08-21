import json
from pathlib import Path

import pytest

from erasemap.fixture_benchmark import run_fixture_suite


def test_manual_pipeline_suite_passes_without_using_generator() -> None:
    result = run_fixture_suite("benchmark/manual-pipelines-v1.json")

    assert result["authorship"] == "project-authored"
    assert result["generator_independent"] is True
    assert result["passed"] is True
    assert result["total"] == 5
    assert len(result["fixture_sha256"]) == 64
    assert {case["status"] for case in result["cases"]} == {
        "COMPLETE",
        "INCOMPLETE",
        "UNVERIFIED",
    }


def test_manual_pipeline_suite_rejects_duplicate_evidence(tmp_path: Path) -> None:
    fixture = json.loads(Path("benchmark/manual-pipelines-v1.json").read_text())
    fixture["cases"][0]["evidence"].append(fixture["cases"][0]["evidence"][0])
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(fixture))

    with pytest.raises(ValueError, match="duplicate evidence"):
        run_fixture_suite(path)


def test_manual_pipeline_suite_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "array.json"
    path.write_text("[]")

    with pytest.raises(ValueError, match="must be an object"):
        run_fixture_suite(path)
