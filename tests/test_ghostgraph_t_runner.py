from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.verify_ghostgraph_t_v1 import verify


def test_verifier_accepts_only_complete_frozen_result(tmp_path: Path) -> None:
    result = {
        "schema_version": "erasemap-ghostgraph-t-result-v1",
        "success": True,
        "case_count": 300,
        "trial_count": 2400,
        "gates": {"one": True, "two": True},
    }
    path = tmp_path / "result.json"
    path.write_text(json.dumps(result))

    assert verify(path)["valid"] is True

    result["gates"]["two"] = False
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="failed gate"):
        verify(path)
