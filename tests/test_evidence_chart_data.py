from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_evidence_chart_manifest_has_sources_and_honest_boundary() -> None:
    data = json.loads(
        (ROOT / "benchmark" / "evidence-charts-v1.json").read_text(encoding="utf-8")
    )
    assert data["schema_version"] == "erasemap-evidence-charts-v1"
    assert len(data["charts"]) == 7
    assert len({chart["id"] for chart in data["charts"]}) == 7
    assert "must not be pooled" in data["claim_boundary"]
    assert all((ROOT / chart["source"]).is_file() for chart in data["charts"])
