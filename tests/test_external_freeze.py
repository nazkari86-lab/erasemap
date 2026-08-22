import json
from pathlib import Path

import pytest

from scripts.verify_external_freeze import verify_freeze


def test_committed_external_evaluator_freeze_verifies() -> None:
    result = verify_freeze(Path("external_challenge/evaluator-freeze-v2.json"))
    assert result["status"] == "PASS"
    assert len(result["artifacts_checked"]) == 5


def test_external_evaluator_freeze_rejects_false_result_claim(tmp_path: Path) -> None:
    source = Path("external_challenge/evaluator-freeze-v2.json")
    value = json.loads(source.read_text())
    value["status"] = "INDEPENDENT_PASS"
    altered = tmp_path / "freeze.json"
    altered.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="must not claim"):
        verify_freeze(altered)
