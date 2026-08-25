from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from erasemap.llm_unlearning_v2 import (
    score_v2_trial,
    select_development_candidate,
    summarize_v2_trials,
)
from experiments.run_qwen_tofu_kaggle_v2 import _semantic_forget_rows
from scripts.verify_qwen_tofu_kaggle_v2 import verify_result

PROTOCOL_PATH = Path("benchmark/qwen-tofu-kaggle-v2.json")


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _evaluations(protocol: dict[str, object]) -> dict[str, dict[str, object]]:
    evaluation = protocol["evaluation"]
    assert isinstance(evaluation, dict)
    flat_counts = {
        "forget_answer": int(evaluation["forget_rows"]),
        "forget_paraphrase": int(evaluation["forget_rows"]),
        "holdout": int(evaluation["holdout_rows"]),
        "retain": int(evaluation["retain_rows"]),
        "world_facts": int(evaluation["world_facts_rows"]),
        "real_authors": int(evaluation["real_author_test_rows"]),
    }
    channels: dict[str, object] = {
        name: [1.0] * count for name, count in flat_counts.items()
    }
    channels["forget_perturbed"] = [
        [2.0] * int(evaluation["perturbed_answers_per_row"])
        for _ in range(int(evaluation["forget_rows"]))
    ]
    result = {
        model: copy.deepcopy(channels)
        for model in ("base", "target", "exact", "candidate", "candidate_reloaded")
    }
    result["base"]["forget_answer"] = [2.0] * flat_counts["forget_answer"]
    result["exact"]["forget_answer"] = [1.8] * flat_counts["forget_answer"]
    result["candidate"]["forget_answer"] = [1.72] * flat_counts["forget_answer"]
    result["candidate_reloaded"]["forget_answer"] = [1.72] * flat_counts[
        "forget_answer"
    ]
    result["exact"]["forget_paraphrase"] = [1.8] * flat_counts["forget_paraphrase"]
    result["candidate"]["forget_paraphrase"] = [1.75] * flat_counts[
        "forget_paraphrase"
    ]
    result["candidate_reloaded"]["forget_paraphrase"] = [1.75] * flat_counts[
        "forget_paraphrase"
    ]
    return result


def _trial(protocol: dict[str, object], candidate_id: str, seed: int) -> dict[str, object]:
    evaluations = _evaluations(protocol)
    return {
        "adapter_sha256": {
            "candidate": "sha256:" + "1" * 64,
            "exact": "sha256:" + "2" * 64,
            "target": "sha256:" + "3" * 64,
        },
        "candidate_id": candidate_id,
        "evaluations": evaluations,
        "metrics": score_v2_trial(
            evaluations,
            recurrence_after_reload=0.0,
            candidate_runtime_seconds=10.0,
            exact_runtime_seconds=20.0,
        ),
        "seed": seed,
        "selected_token_count": 12,
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    )


def _write_result(root: Path) -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    root.mkdir()
    development_trials = {
        str(config["id"]): [
            _trial(protocol, str(config["id"]), int(seed))
            for seed in protocol["development_seeds"]
        ]
        for config in protocol["candidate"]["development_grid"]
    }
    summaries = [
        {
            "candidate_id": candidate_id,
            **summarize_v2_trials(rows, protocol["success_criteria"]),
        }
        for candidate_id, rows in development_trials.items()
    ]
    selected = select_development_candidate(
        summaries, protocol["development_selection_criteria"]
    )
    development = {
        "selected_candidate_id": selected,
        "selection_uses_confirmation": False,
        "summaries": summaries,
        "trials": development_trials,
    }
    _write_json(root / "development.json", development)
    trials = [_trial(protocol, selected, int(seed)) for seed in protocol["confirmation_seeds"]]
    baseline_id = str(protocol["baseline"]["id"])
    baseline = [
        _trial(protocol, baseline_id, int(seed)) for seed in protocol["confirmation_seeds"]
    ]
    _write_jsonl(root / "trials.jsonl", trials)
    _write_jsonl(root / "baseline_trials.jsonl", baseline)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    summary = {
        **summarize_v2_trials(trials, protocol["success_criteria"]),
        "baseline": summarize_v2_trials(baseline, protocol["success_criteria"]),
        "claim_boundary": protocol["evidence_boundary"],
        "code_revision": commit,
        "dataset_revision": protocol["dataset"]["revision"],
        "development_candidate_count": len(development_trials),
        "development_seed_count": len(protocol["development_seeds"]),
        "environment": {"cuda": "12.1", "gpu": "P100", "platform": "linux", "python": "3.12"},
        "model_revision": protocol["model"]["revision"],
        "protocol_sha256": _sha256(PROTOCOL_PATH),
        "schema_version": "erasemap-qwen-tofu-kaggle-result-v2",
        "selected_candidate_id": selected,
        "trial_count": len(trials),
    }
    _write_json(root / "summary.json", summary)
    files = {
        name: _sha256(root / name)
        for name in (
            "baseline_trials.jsonl",
            "development.json",
            "summary.json",
            "trials.jsonl",
        )
    }
    _write_json(
        root / "MANIFEST.sha256.json",
        {"files": files, "protocol_sha256": _sha256(PROTOCOL_PATH)},
    )


def test_v2_protocol_is_locked_and_separates_selection_from_confirmation() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    assert protocol["status"] == "FROZEN_BEFORE_FIRST_V2_GPU_RUN"
    assert len(protocol["candidate"]["development_grid"]) == 6
    assert len(protocol["development_seeds"]) == 2
    assert len(protocol["confirmation_seeds"]) == 5
    assert set(protocol["development_seeds"]).isdisjoint(protocol["confirmation_seeds"])
    assert protocol["success_criteria"]["candidate_exact_normalized_recovery_min"] == 0.8


def test_semantic_perturbed_rows_use_their_real_schema() -> None:
    rows = [
        {
            "answer": "direct",
            "paraphrased_answer": "paraphrase",
            "paraphrased_question": "rewritten?",
            "perturbed_answer": ["wrong-a", "wrong-b"],
            "question": "original?",
        }
    ]
    direct, paraphrase, perturbed = _semantic_forget_rows(rows, expected_perturbations=2)
    assert direct[0]["answer"] == "direct"
    assert paraphrase[0] == {"question": "rewritten?", "answer": "paraphrase"}
    assert [row["answer"] for row in perturbed[0]] == ["wrong-a", "wrong-b"]


def test_v2_verifier_recomputes_selection_metrics_and_manifest(tmp_path: Path) -> None:
    result = tmp_path / "result"
    _write_result(result)
    verified = verify_result(result)
    assert verified["decision"] == "PASS"
    assert verified["trials_checked"] == 5
    development = json.loads((result / "development.json").read_text())
    development["selection_uses_confirmation"] = True
    _write_json(result / "development.json", development)
    with pytest.raises(ValueError, match="manifest"):
        verify_result(result)
