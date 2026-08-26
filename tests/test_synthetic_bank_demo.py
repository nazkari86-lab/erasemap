from __future__ import annotations

import json
from pathlib import Path

import pytest

from erasemap.cli import main
from erasemap.synthetic_bank_demo import (
    SCHEMA_VERSION,
    build_synthetic_bank_demo,
    render_synthetic_bank_demo_html,
    write_synthetic_bank_demo,
)


def test_synthetic_bank_demo_has_clear_scope_and_story() -> None:
    scenario = build_synthetic_bank_demo()

    assert scenario["schema_version"] == SCHEMA_VERSION
    assert scenario["customer"]["customer_id"] == "KZ-DEMO-042"
    assert len(scenario["steps"]) == 6
    assert "No bank" in scenario["scope"]
    assert "not evidence" in scenario["claim_boundary"]

    rendered = render_synthetic_bank_demo_html(scenario)
    assert "Orda Bank" in rendered
    assert "GhostGraph" in rendered
    assert "SYNTHETIC · NO REAL DATA" in rendered
    assert "COMPLETE" in rendered


def test_synthetic_bank_demo_writes_portable_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "bank-demo"
    scenario = write_synthetic_bank_demo(output)

    assert (output / "index.html").is_file()
    assert json.loads((output / "scenario.json").read_text()) == scenario


def test_synthetic_bank_demo_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "bank-demo"
    assert main(["bank-demo", "--output", str(output)]) == 0
    response = json.loads(capsys.readouterr().out)

    assert response["status"] == "READY"
    assert (output / "index.html").is_file()
