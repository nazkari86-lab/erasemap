from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from experiments.run_erasure_tomography_v1 import run
from scripts.verify_erasure_tomography_v1 import verify

ROOT = Path(__file__).resolve().parents[1]


def canonical(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def development_inputs(tmp_path: Path) -> tuple[Path, Path]:
    protocol = json.loads(
        (ROOT / "benchmark/erasure-tomography-v1.json").read_text()
    )
    reveal = {
        "schema_version": "erasemap-erasure-tomography-reveal-v1",
        "cases": [
            {
                "case_id": "development-valid-backup",
                "kind": "valid",
                "seed": 9001,
                "active_ids": ["backup_restore"],
            },
            {
                "case_id": "development-safe",
                "kind": "safe",
                "seed": 9002,
                "active_ids": [],
            },
            {
                "case_id": "development-invalid-skipped",
                "kind": "skipped",
                "seed": 9003,
                "active_ids": ["backup_restore"],
                "skipped_probe_index": 1,
            },
        ],
    }
    reveal_bytes = canonical(reveal).encode()
    protocol["protocol_id"] = "erasure-tomography-development"
    protocol["support_schedule"] = {
        "reveal_path": str(tmp_path / "reveal.json"),
        "canonical_sha256": hashlib.sha256(reveal_bytes).hexdigest(),
        "case_count": 3,
        "valid_case_count": 1,
        "safe_case_count": 1,
        "negative_case_count": 1,
    }
    protocol["primary_gates"].update(
        {
            "valid_case_count": 1,
            "exact_support_recovery_count": 1,
            "safe_no_recurrence_count": 1,
            "negative_case_count": 1,
            "negative_case_pass_count": 1,
        }
    )
    protocol_path = tmp_path / "protocol.json"
    reveal_path = tmp_path / "reveal.json"
    protocol_path.write_text(canonical(protocol) + "\n")
    reveal_path.write_text(canonical(reveal) + "\n")
    return protocol_path, reveal_path


def test_development_result_runs_and_verifies(tmp_path: Path) -> None:
    protocol, reveal = development_inputs(tmp_path)
    result = run(protocol, reveal, tmp_path / "output")

    checked = verify(protocol, reveal, tmp_path / "output/result.json")

    assert result["passed"]
    assert checked["passed"]
    assert checked["metrics"]["exact_support_recovery_count"] == 1


@pytest.mark.parametrize(
    "mutation",
    ("protocol_hash", "case_order", "metrics", "gates", "decision"),
)
def test_verifier_rejects_result_mutations(tmp_path: Path, mutation: str) -> None:
    protocol, reveal = development_inputs(tmp_path)
    output = tmp_path / "output"
    run(protocol, reveal, output)
    result = json.loads((output / "result.json").read_text())
    mutated = copy.deepcopy(result)
    if mutation == "protocol_hash":
        mutated["protocol_hash"] = "0" * 64
    elif mutation == "case_order":
        mutated["trials"] = list(reversed(mutated["trials"]))
    elif mutation == "metrics":
        mutated["metrics"]["valid_case_count"] += 1
    elif mutation == "gates":
        mutated["gates"]["false_localization_count_max"] = False
    else:
        mutated["passed"] = not mutated["passed"]
    result_path = tmp_path / f"mutated-{mutation}.json"
    result_path.write_text(canonical(mutated) + "\n")

    with pytest.raises(ValueError):
        verify(protocol, reveal, result_path)
