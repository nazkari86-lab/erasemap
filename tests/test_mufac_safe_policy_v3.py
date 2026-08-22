import json
from pathlib import Path


def test_v3_policy_accepts_candidate_without_disabling_fallback() -> None:
    result = json.loads(Path("benchmark/results/mufac-safe-policy-v3-summary.json").read_text())
    protocol = json.loads(Path("benchmark/mufac-safe-policy-v3.json").read_text())
    assert result["decision"] == "CANDIDATE_ACCEPTED"
    assert all(result["gates"].values())
    assert result["selected_method"] == protocol["candidate"]
    assert protocol["fallback"] == "exact_retrain"
