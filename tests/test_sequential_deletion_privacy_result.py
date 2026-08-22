import json
from pathlib import Path

import pytest

from scripts.verify_sequential_deletion_privacy_v1 import verify_result

RESULT = Path("benchmark/results/sequential-deletion-privacy-v1")


def test_committed_sequential_result_independently_verifies() -> None:
    verified = verify_result(RESULT)
    assert verified["decision"] == "PASS"
    assert verified["transitions_checked"] == 25


def test_verifier_rejects_tampered_trial(tmp_path: Path) -> None:
    copied = tmp_path / "result"
    copied.mkdir()
    for name in ("summary.json", "trials.jsonl", "MANIFEST.sha256.json"):
        (copied / name).write_bytes((RESULT / name).read_bytes())
    rows = (copied / "trials.jsonl").read_text().splitlines()
    first = json.loads(rows[0])
    first["retained_accuracy_delta"] = -1.0
    rows[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    (copied / "trials.jsonl").write_text("\n".join(rows) + "\n")
    with pytest.raises(ValueError, match="manifest"):
        verify_result(copied)
