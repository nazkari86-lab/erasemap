from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_evidence_chart_manifest_has_sources_and_honest_boundary() -> None:
    data = json.loads(
        (ROOT / "benchmark" / "evidence-charts-v1.json").read_text(encoding="utf-8")
    )
    assert data["schema_version"] == "erasemap-algorithm-comparisons-v2"
    assert len(data["charts"]) == 8
    assert len({chart["id"] for chart in data["charts"]}) == 8
    assert "must not be pooled" in data["claim_boundary"]
    assert all((ROOT / chart["source"]).is_file() for chart in data["charts"])
    unlearning = next(chart for chart in data["charts"] if chart["id"] == "08_unlearning")
    assert unlearning["labels"] == [
        "EraSeMap candidate",
        "Exact retrain",
        "Gradient ascent",
        "Head-only",
        "Stale",
    ]
    dashboard = ROOT / "docs" / "assets" / "erasemap-one-algorithm-comparison.png"
    assert dashboard.is_file()
    assert dashboard.stat().st_size > 100_000
