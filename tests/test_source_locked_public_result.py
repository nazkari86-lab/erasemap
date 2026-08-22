from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_committed_source_locked_result_verifies() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/verify_source_locked_holdout.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "decision=PASS" in completed.stdout
    summary = json.loads(Path("outputs/source-locked-holdout-v1/summary.json").read_text())
    assert summary["case_count"] == 125
    assert summary["metrics"]["pcug"]["false_complete"] == 0
    assert summary["metrics"]["pcug"]["false_complete_wilson95"][1] <= 0.05
