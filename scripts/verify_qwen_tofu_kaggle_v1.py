from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any, cast

from erasemap.llm_unlearning import score_trial, summarize_trials


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _git_has_commit(commit: str) -> bool:
    return (
        subprocess.run(
            ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
            check=False,
            capture_output=True,
        ).returncode
        == 0
    )


def _close(left: object, right: object, path: str = "root") -> None:
    if isinstance(left, bool) or isinstance(right, bool):
        if left is not right:
            raise ValueError(f"boolean mismatch at {path}")
        return
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if not math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError(f"numeric mismatch at {path}")
        return
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            raise ValueError(f"key mismatch at {path}")
        for key in left:
            _close(left[key], right[key], f"{path}.{key}")
        return
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            raise ValueError(f"length mismatch at {path}")
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=True)):
            _close(left_item, right_item, f"{path}[{index}]")
        return
    if left != right:
        raise ValueError(f"value mismatch at {path}")


def verify_result(
    result_dir: Path,
    *,
    protocol_path: Path = Path("benchmark/qwen-tofu-kaggle-v1.json"),
) -> dict[str, object]:
    protocol = cast(dict[str, Any], json.loads(protocol_path.read_text()))
    summary_path = result_dir / "summary.json"
    trials_path = result_dir / "trials.jsonl"
    manifest_path = result_dir / "MANIFEST.sha256.json"
    summary = cast(dict[str, Any], json.loads(summary_path.read_text()))
    trials = cast(
        list[dict[str, Any]],
        [json.loads(line) for line in trials_path.read_text().splitlines() if line],
    )
    manifest = cast(dict[str, str], json.loads(manifest_path.read_text()))
    expected_manifest = {
        "protocol_sha256": _sha256(protocol_path),
        "summary_sha256": _sha256(summary_path),
        "trials_sha256": _sha256(trials_path),
    }
    if manifest != expected_manifest:
        raise ValueError("manifest does not bind the committed result artifacts")
    if summary.get("protocol_sha256") != expected_manifest["protocol_sha256"]:
        raise ValueError("summary is bound to a different protocol")
    if summary.get("model_revision") != protocol["model"]["revision"]:
        raise ValueError("model revision drift")
    if summary.get("dataset_revision") != protocol["dataset"]["revision"]:
        raise ValueError("dataset revision drift")
    commit = summary.get("code_revision")
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("code revision must be a full hexadecimal commit")
    if not _git_has_commit(commit):
        raise ValueError("code revision is absent from repository history")
    expected_seeds = [int(seed) for seed in protocol["random_seeds"]]
    actual_seeds = [int(trial["seed"]) for trial in trials]
    if actual_seeds != expected_seeds or int(summary.get("trial_count", -1)) != len(expected_seeds):
        raise ValueError("trial seeds do not match the preregistration")

    evaluation = protocol["evaluation"]
    expected_counts = {
        "forget": int(evaluation["forget_rows"]),
        "forget_perturbed": int(evaluation["forget_perturbed_rows"]),
        "holdout": int(evaluation["holdout_rows"]),
        "retain": int(evaluation["retain_rows"]),
        "retain_perturbed": int(evaluation["retain_perturbed_rows"]),
        "world_facts": int(evaluation["world_facts_rows"]),
    }
    expected_models = {"base", "target", "exact", "candidate", "candidate_reloaded"}
    recomputed_trials: list[dict[str, Any]] = []
    for trial in trials:
        adapters = trial.get("adapter_sha256")
        if not isinstance(adapters, dict) or set(adapters) != {"candidate", "exact", "target"}:
            raise ValueError("adapter commitments are incomplete")
        if any(
            not isinstance(value, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None
            for value in adapters.values()
        ):
            raise ValueError("adapter commitment is malformed")
        losses = trial.get("losses")
        if not isinstance(losses, dict) or set(losses) != expected_models:
            raise ValueError("loss matrix model set mismatch")
        for model_id, model_losses in losses.items():
            if not isinstance(model_losses, dict) or set(model_losses) != set(expected_counts):
                raise ValueError(f"loss matrix dataset set mismatch: {model_id}")
            for dataset_id, count in expected_counts.items():
                values = model_losses[dataset_id]
                if not isinstance(values, list) or len(values) != count:
                    raise ValueError(f"loss count mismatch: {model_id}.{dataset_id}")
        recurrence = max(
            abs(float(left) - float(right))
            for dataset_id in expected_counts
            for left, right in zip(
                losses["candidate"][dataset_id],
                losses["candidate_reloaded"][dataset_id],
                strict=True,
            )
        )
        metrics = score_trial(losses, recurrence_after_reload=recurrence)
        _close(trial.get("metrics"), metrics, "trial.metrics")
        recomputed_trials.append({**trial, "metrics": metrics})

    recomputed = summarize_trials(recomputed_trials, protocol["success_criteria"])
    _close(summary.get("aggregate"), recomputed["aggregate"], "summary.aggregate")
    _close(summary.get("gates"), recomputed["gates"], "summary.gates")
    if summary.get("decision") != recomputed["decision"]:
        raise ValueError("published decision does not match recomputed gates")
    environment = summary.get("environment")
    if not isinstance(environment, dict) or not str(environment.get("gpu", "")).strip():
        raise ValueError("GPU environment is not recorded")
    return {
        "code_revision": commit,
        "decision": recomputed["decision"],
        "gates": recomputed["gates"],
        "schema_version": "erasemap-qwen-tofu-kaggle-verification-v1",
        "trials_checked": len(trials),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Qwen-TOFU Kaggle v1 result")
    parser.add_argument("--result", type=Path, default=Path("outputs/qwen-tofu-kaggle-v1"))
    parser.add_argument(
        "--protocol", type=Path, default=Path("benchmark/qwen-tofu-kaggle-v1.json")
    )
    args = parser.parse_args()
    print(json.dumps(verify_result(args.result, protocol_path=args.protocol), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
