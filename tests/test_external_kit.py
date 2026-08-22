from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_external_kit_runs_and_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "records"
    environment = {**os.environ, "PYTHONPATH": "src"}
    command = [
        sys.executable,
        "external_evaluator/run.py",
        "--sources",
        "benchmark/external-sources-v1.json",
        "--output",
        str(output),
    ]
    subprocess.run(command, check=True, env=environment, capture_output=True, text=True)
    records = output / "evaluation-records.json"
    completed = subprocess.run(
        [sys.executable, "external_evaluator/verify.py", str(records)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "625 unique records" in completed.stdout
    refused = subprocess.run(command, env=environment, capture_output=True, text=True)
    assert refused.returncode != 0
    assert "FileExistsError" in refused.stderr
