from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, cast

from erasemap.llm_unlearning_v2 import (
    score_v2_trial,
    select_development_candidate,
    summarize_v2_trials,
    validate_evaluations,
)
from scripts.verify_qwen_tofu_kaggle_v1 import _close, _git_has_commit, _sha256


def _maximum_difference(left: object, right: object) -> float:
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            raise ValueError("reload evaluation channels differ")
        return max(
            (_maximum_difference(left[key], right[key]) for key in left),
            default=0.0,
        )
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            raise ValueError("reload evaluation shapes differ")
        return max(
            (_maximum_difference(a, b) for a, b in zip(left, right, strict=True)),
            default=0.0,
        )
    return abs(float(left) - float(right))


def _verify_adapter_hashes(trial: MappingLike) -> None:
    adapters = trial.get("adapter_sha256")
    if not isinstance(adapters, dict) or set(adapters) != {"candidate", "exact", "target"}:
        raise ValueError("adapter commitments are incomplete")
    if any(
        not isinstance(value, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None
        for value in adapters.values()
    ):
        raise ValueError("adapter commitment is malformed")


MappingLike = dict[str, Any]


def _verify_shapes(
    evaluations: dict[str, dict[str, object]], protocol: MappingLike
) -> None:
    settings = protocol["evaluation"]
    expected_flat = {
        "forget_answer": int(settings["forget_rows"]),
        "forget_paraphrase": int(settings["forget_rows"]),
        "holdout": int(settings["holdout_rows"]),
        "retain": int(settings["retain_rows"]),
        "world_facts": int(settings["world_facts_rows"]),
        "real_authors": int(settings["real_author_test_rows"]),
    }
    expected_perturbations = int(settings["perturbed_answers_per_row"])
    for model_id, channels in evaluations.items():
        for channel, count in expected_flat.items():
            values = channels[channel]
            if not isinstance(values, list) or len(values) != count:
                raise ValueError(f"evaluation count mismatch: {model_id}.{channel}")
        perturbed = channels["forget_perturbed"]
        if not isinstance(perturbed, list) or len(perturbed) != expected_flat["forget_answer"]:
            raise ValueError(f"perturbed row count mismatch: {model_id}")
        if any(
            not isinstance(row, list) or len(row) != expected_perturbations
            for row in perturbed
        ):
            raise ValueError(f"perturbed answer count mismatch: {model_id}")


def _recompute_trial(trial: MappingLike, protocol: MappingLike) -> MappingLike:
    _verify_adapter_hashes(trial)
    evaluations = trial.get("evaluations")
    if not isinstance(evaluations, dict):
        raise ValueError("trial evaluations are missing")
    typed_evaluations = cast(dict[str, dict[str, object]], evaluations)
    validate_evaluations(typed_evaluations)
    _verify_shapes(typed_evaluations, protocol)
    candidate = typed_evaluations["candidate"]
    reloaded = typed_evaluations["candidate_reloaded"]
    recurrence = _maximum_difference(candidate, reloaded)
    metrics = trial.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("trial metrics are missing")
    recomputed = score_v2_trial(
        typed_evaluations,
        recurrence_after_reload=recurrence,
        candidate_runtime_seconds=float(metrics["candidate_runtime_seconds"]),
        exact_runtime_seconds=float(metrics["exact_runtime_seconds"]),
    )
    _close(metrics, recomputed, "trial.metrics")
    return {**trial, "metrics": recomputed}


def _load_jsonl(path: Path) -> list[MappingLike]:
    return [
        cast(MappingLike, json.loads(line))
        for line in path.read_text().splitlines()
        if line
    ]


def verify_result(
    result_dir: Path,
    *,
    protocol_path: Path = Path("benchmark/qwen-tofu-kaggle-v2.json"),
) -> dict[str, object]:
    protocol = cast(dict[str, Any], json.loads(protocol_path.read_text()))
    summary_path = result_dir / "summary.json"
    development_path = result_dir / "development.json"
    trials_path = result_dir / "trials.jsonl"
    baseline_path = result_dir / "baseline_trials.jsonl"
    manifest_path = result_dir / "MANIFEST.sha256.json"
    files = {
        "baseline_trials.jsonl": baseline_path,
        "development.json": development_path,
        "summary.json": summary_path,
        "trials.jsonl": trials_path,
    }
    manifest = cast(dict[str, Any], json.loads(manifest_path.read_text()))
    expected_manifest = {
        "files": {name: _sha256(path) for name, path in files.items()},
        "protocol_sha256": _sha256(protocol_path),
    }
    if manifest != expected_manifest:
        raise ValueError("manifest does not bind the committed v2 result artifacts")

    summary = cast(dict[str, Any], json.loads(summary_path.read_text()))
    if summary.get("protocol_sha256") != expected_manifest["protocol_sha256"]:
        raise ValueError("summary is bound to a different v2 protocol")
    if summary.get("model_revision") != protocol["model"]["revision"]:
        raise ValueError("model revision drift")
    if summary.get("dataset_revision") != protocol["dataset"]["revision"]:
        raise ValueError("dataset revision drift")
    commit = summary.get("code_revision")
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("code revision must be a full hexadecimal commit")
    if not _git_has_commit(commit):
        raise ValueError("code revision is absent from repository history")

    development = cast(dict[str, Any], json.loads(development_path.read_text()))
    if development.get("selection_uses_confirmation") is not False:
        raise ValueError("development selection must be confirmation-blind")
    grid_ids = [str(row["id"]) for row in protocol["candidate"]["development_grid"]]
    raw_development = development.get("trials")
    if not isinstance(raw_development, dict) or set(raw_development) != set(grid_ids):
        raise ValueError("development candidate grid mismatch")
    development_summaries = []
    expected_development_seeds = [int(seed) for seed in protocol["development_seeds"]]
    for candidate_id in grid_ids:
        candidate_trials = [
            _recompute_trial(cast(MappingLike, row), protocol)
            for row in cast(list[MappingLike], raw_development[candidate_id])
        ]
        if [int(row["seed"]) for row in candidate_trials] != expected_development_seeds:
            raise ValueError("development seed mismatch")
        if any(str(row.get("candidate_id")) != candidate_id for row in candidate_trials):
            raise ValueError("development candidate id mismatch")
        development_summaries.append(
            {
                "candidate_id": candidate_id,
                **summarize_v2_trials(candidate_trials, protocol["success_criteria"]),
            }
        )
    _close(development.get("summaries"), development_summaries, "development.summaries")
    selected = select_development_candidate(
        development_summaries, protocol["development_selection_criteria"]
    )
    if development.get("selected_candidate_id") != selected:
        raise ValueError("published development selection is not reproducible")

    trials = [_recompute_trial(row, protocol) for row in _load_jsonl(trials_path)]
    baseline_trials = [_recompute_trial(row, protocol) for row in _load_jsonl(baseline_path)]
    expected_confirmation_seeds = [int(seed) for seed in protocol["confirmation_seeds"]]
    for name, rows in (("candidate", trials), ("baseline", baseline_trials)):
        if [int(row["seed"]) for row in rows] != expected_confirmation_seeds:
            raise ValueError(f"{name} confirmation seed mismatch")
    if any(str(row.get("candidate_id")) != selected for row in trials):
        raise ValueError("confirmation did not use the development-selected candidate")
    baseline_id = str(protocol["baseline"]["id"])
    if any(str(row.get("candidate_id")) != baseline_id for row in baseline_trials):
        raise ValueError("baseline recipe id mismatch")

    computed = summarize_v2_trials(trials, protocol["success_criteria"])
    baseline_computed = summarize_v2_trials(baseline_trials, protocol["success_criteria"])
    _close(summary.get("aggregate"), computed["aggregate"], "summary.aggregate")
    _close(summary.get("gates"), computed["gates"], "summary.gates")
    _close(summary.get("baseline"), baseline_computed, "summary.baseline")
    if summary.get("decision") != computed["decision"]:
        raise ValueError("published decision does not match recomputed v2 gates")
    if summary.get("selected_candidate_id") != selected:
        raise ValueError("summary selected candidate mismatch")
    if int(summary.get("trial_count", -1)) != len(expected_confirmation_seeds):
        raise ValueError("summary confirmation trial count mismatch")
    environment = summary.get("environment")
    if not isinstance(environment, dict) or not str(environment.get("gpu", "")).strip():
        raise ValueError("GPU environment is not recorded")
    return {
        "baseline_decision": baseline_computed["decision"],
        "code_revision": commit,
        "decision": computed["decision"],
        "gates": computed["gates"],
        "schema_version": "erasemap-qwen-tofu-kaggle-verification-v2",
        "selected_candidate_id": selected,
        "trials_checked": len(trials),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Qwen-TOFU Kaggle v2")
    parser.add_argument("--result", type=Path, default=Path("outputs/qwen-tofu-kaggle-v2"))
    parser.add_argument(
        "--protocol", type=Path, default=Path("benchmark/qwen-tofu-kaggle-v2.json")
    )
    args = parser.parse_args()
    print(json.dumps(verify_result(args.result, protocol_path=args.protocol), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
