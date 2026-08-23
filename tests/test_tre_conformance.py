import json
from pathlib import Path

from erasemap.tre_conformance import run_tre_conformance


def test_tre_conformance_matches_committed_summary() -> None:
    expected = json.loads(Path("formal/tre-conformance-v1.json").read_text())
    actual = run_tre_conformance()

    assert actual == expected
    assert actual["mismatches"] == 0
