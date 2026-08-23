import json
from pathlib import Path

import pytest

from scripts.verify_topology_robust_erasure_v1 import verify


def test_frozen_topology_robust_result_passes() -> None:
    report = verify(
        Path("benchmark/topology-robust-erasure-v1.json"),
        Path("outputs/topology-robust-erasure-v1/result.json"),
    )

    assert report["passed"]
    assert report["metrics"]["nominal_plan_regeneration_count"] == 35
    assert report["metrics"]["tre_post_control_regeneration_count"] == 0


def test_verifier_rejects_mutated_trial(tmp_path) -> None:
    source = Path("outputs/topology-robust-erasure-v1/result.json")
    payload = json.loads(source.read_text())
    payload["trials"][0]["tre_post_control_regeneration"] = True
    mutated = tmp_path / "mutated.json"
    mutated.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="metrics"):
        verify(
            Path("benchmark/topology-robust-erasure-v1.json"),
            mutated,
        )
