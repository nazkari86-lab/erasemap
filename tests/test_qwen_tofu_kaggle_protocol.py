from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from erasemap.llm_unlearning import score_trial, summarize_trials
from scripts.verify_qwen_tofu_kaggle_v1 import verify_result

PROTOCOL_PATH = Path("benchmark/qwen-tofu-kaggle-v1.json")


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _matrix(protocol: dict[str, object]) -> dict[str, dict[str, list[float]]]:
    evaluation = protocol["evaluation"]
    assert isinstance(evaluation, dict)
    counts = {
        "forget": int(evaluation["forget_rows"]),
        "forget_perturbed": int(evaluation["forget_perturbed_rows"]),
        "holdout": int(evaluation["holdout_rows"]),
        "retain": int(evaluation["retain_rows"]),
        "retain_perturbed": int(evaluation["retain_perturbed_rows"]),
        "world_facts": int(evaluation["world_facts_rows"]),
    }
    matrix = {
        model_id: {dataset_id: [1.0] * count for dataset_id, count in counts.items()}
        for model_id in ("base", "target", "exact", "candidate", "candidate_reloaded")
    }
    for model_id in matrix:
        matrix[model_id]["holdout"] = [2.0] * counts["holdout"]
    matrix["base"]["forget"] = [2.0] * counts["forget"]
    matrix["target"]["forget"] = [1.0] * counts["forget"]
    matrix["exact"]["forget"] = [1.8] * counts["forget"]
    matrix["candidate"]["forget"] = [1.75] * counts["forget"]
    matrix["candidate_reloaded"]["forget"] = [1.75] * counts["forget"]
    matrix["exact"]["forget_perturbed"] = [1.8] * counts["forget_perturbed"]
    matrix["candidate"]["forget_perturbed"] = [1.75] * counts["forget_perturbed"]
    matrix["candidate_reloaded"]["forget_perturbed"] = [1.75] * counts[
        "forget_perturbed"
    ]
    return matrix


def _write_result(root: Path) -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    trials = []
    for seed in protocol["random_seeds"]:
        matrix = _matrix(protocol)
        trials.append(
            {
                "adapter_sha256": {
                    "candidate": "sha256:" + "1" * 64,
                    "exact": "sha256:" + "2" * 64,
                    "target": "sha256:" + "3" * 64,
                },
                "losses": matrix,
                "metrics": score_trial(matrix, recurrence_after_reload=0.0),
                "seed": seed,
            }
        )
    root.mkdir()
    trials_path = root / "trials.jsonl"
    trials_path.write_text(
        "".join(json.dumps(trial, sort_keys=True, separators=(",", ":")) + "\n" for trial in trials)
    )
    computed = summarize_trials(trials, protocol["success_criteria"])
    summary = {
        **computed,
        "claim_boundary": protocol["evidence_boundary"],
        "code_revision": commit,
        "dataset_revision": protocol["dataset"]["revision"],
        "environment": {"cuda": "12.1", "gpu": "Tesla P100", "platform": "linux", "python": "3.11"},
        "model_revision": protocol["model"]["revision"],
        "protocol_sha256": _sha256(PROTOCOL_PATH),
        "schema_version": "erasemap-qwen-tofu-kaggle-result-v1",
        "trial_count": len(trials),
    }
    summary_path = root / "summary.json"
    summary_path.write_text(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n")
    manifest = {
        "protocol_sha256": _sha256(PROTOCOL_PATH),
        "summary_sha256": _sha256(summary_path),
        "trials_sha256": _sha256(trials_path),
    }
    (root / "MANIFEST.sha256.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    )


def test_protocol_is_source_pinned_and_fail_closed() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    assert protocol["status"] == "PREREGISTERED_BEFORE_FIRST_GPU_RUN"
    assert len(protocol["model"]["revision"]) == 40
    assert len(protocol["dataset"]["revision"]) == 40
    assert len(protocol["random_seeds"]) == 3
    assert len(protocol["success_criteria"]) == 9


def test_synthetic_result_recomputes_and_tampering_fails(tmp_path: Path) -> None:
    result = tmp_path / "result"
    _write_result(result)
    verified = verify_result(result)
    assert verified["decision"] == "PASS"
    assert verified["trials_checked"] == 3
    rows = (result / "trials.jsonl").read_text().splitlines()
    first = json.loads(rows[0])
    first["metrics"]["candidate_forgetting_lift"] = 999.0
    rows[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    (result / "trials.jsonl").write_text("\n".join(rows) + "\n")
    with pytest.raises(ValueError, match="manifest"):
        verify_result(result)
