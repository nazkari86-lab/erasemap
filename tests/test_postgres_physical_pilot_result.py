import json
from pathlib import Path


def test_physical_postgres_pilot_detected_and_closed_residuals() -> None:
    result = json.loads(Path("benchmark/results/postgres-physical-pilot-v1.json").read_text())
    assert result["before"]["derived_rows"] == 1
    assert result["before"]["verdict"] == "INCOMPLETE"
    assert result["before"]["shortest_path"] == ["postgres-derived"]
    assert result["before"]["backup_hash"].startswith("sha256:")
    assert result["after"] == {"shortest_path": None, "verdict": "COMPLETE"}
    assert "no organization infrastructure" in result["claim_boundary"]
