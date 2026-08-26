from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from erasemap.llm_unlearning_v2 import score_v2_trial, summarize_v2_trials
from erasemap.llm_unlearning_v3 import (
    NoRobustCandidateError,
    PathPoint,
    select_robust_point,
    summarize_path_point,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "benchmark/qwen-tofu-kaggle-v3.json"
V2_PROTOCOL = ROOT / "benchmark/qwen-tofu-kaggle-v2.json"


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return cast(Mapping[str, Any], value)


def _jsonl(path: Path) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for index, line in enumerate(path.read_text().splitlines()):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path.name} row {index} must be an object")
        rows.append(cast(Mapping[str, Any], value))
    if not rows:
        raise ValueError(f"{path.name} must not be empty")
    return rows


def _sha(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("sha256:")
        or len(value) != 71
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{name} must be a SHA-256 commitment")
    return value


def verify_protocol(protocol_path: Path = DEFAULT_PROTOCOL) -> dict[str, object]:
    protocol = _json(protocol_path)
    v2 = _json(V2_PROTOCOL)
    if protocol.get("status") != "FROZEN_BEFORE_FIRST_V3_GPU_RUN":
        raise ValueError("protocol is not frozen")
    for field in ("model", "training", "evaluation", "success_criteria"):
        if protocol.get(field) != v2.get(field):
            raise ValueError(f"protocol {field} drifted from v2")
    dataset = cast(Mapping[str, object], protocol.get("dataset"))
    v2_dataset = cast(Mapping[str, object], v2.get("dataset"))
    if (dataset.get("repository"), dataset.get("revision")) != (
        v2_dataset.get("repository"),
        v2_dataset.get("revision"),
    ):
        raise ValueError("protocol dataset pin drifted from v2")
    blocks = cast(Mapping[str, Any], protocol.get("author_blocks"))
    commitments = blocks.get("commitments")
    if not isinstance(commitments, list) or len(commitments) != 20:
        raise ValueError("protocol must bind exactly twenty author blocks")
    for index, commitment in enumerate(commitments):
        _sha(commitment, name=f"author commitment {index}")
    if len(set(commitments)) != len(commitments):
        raise ValueError("author commitments must be unique")
    development = blocks.get("development_pairs")
    if not isinstance(development, list) or len(development) != 5:
        raise ValueError("protocol must contain five development pairs")
    development_indices = {
        value
        for pair in development
        if isinstance(pair, list)
        for value in pair
        if isinstance(value, int)
    }
    primary = set(cast(Sequence[int], blocks.get("primary_confirmation")))
    replication = set(cast(Sequence[int], blocks.get("replication_confirmation")))
    reserve = set(cast(Sequence[int], blocks.get("future_reserve")))
    if (
        len(development_indices) != 10
        or len(primary) != 2
        or len(replication) != 2
        or len(reserve) != 6
        or development_indices & primary
        or development_indices & replication
        or development_indices & reserve
        or primary & replication
        or primary & reserve
        or replication & reserve
    ):
        raise ValueError("protocol author split is not disjoint and complete")
    method = cast(Mapping[str, Any], protocol.get("method"))
    if method.get("minimum_contiguous_feasible_alphas") != 3:
        raise ValueError("protocol robust interval width drift")
    development_seeds = cast(Sequence[int], protocol.get("development_seeds"))
    confirmation_seeds = cast(Sequence[int], protocol.get("confirmation_seeds"))
    if len(development_seeds) != 2 or len(confirmation_seeds) != 5:
        raise ValueError("protocol seed counts drifted")
    if set(development_seeds) & set(confirmation_seeds):
        raise ValueError("development and confirmation seeds overlap")
    return {
        "author_block_count": len(commitments),
        "primary_gate_count": 12,
        "protocol_sha256": _sha256(protocol_path),
        "status": "PROTOCOL_VALID",
    }


def _verify_manifest(root: Path, protocol_sha256: str) -> None:
    manifest = _json(root / "MANIFEST.sha256.json")
    if manifest.get("protocol_sha256") != protocol_sha256:
        raise ValueError("manifest protocol hash mismatch")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("manifest files mapping is missing")
    actual_names = {
        path.name
        for path in root.iterdir()
        if path.is_file() and path.name != "MANIFEST.sha256.json"
    }
    if set(files) != actual_names:
        raise ValueError("manifest file set mismatch")
    for name, expected in files.items():
        path = root / name
        if not path.is_file() or _sha256(path) != expected:
            raise ValueError(f"manifest hash mismatch: {name}")


def _verify_state_chain(root: Path) -> str:
    states = sorted(root.glob("state-*.json"))
    if len(states) < 3:
        raise ValueError("state chain is incomplete")
    previous: Path | None = None
    last_state = ""
    for path in states:
        value = _json(path)
        expected = _sha256(previous) if previous is not None else None
        if value.get("previous_state_sha256") != expected:
            raise ValueError(f"state chain digest mismatch: {path.name}")
        last_state = str(value.get("state"))
        previous = path
    if last_state != "SEALED":
        raise ValueError("state chain is not sealed")
    return last_state


def _close(left: object, right: object, *, path: str) -> None:
    if isinstance(left, dict) and isinstance(right, Mapping):
        if set(left) != set(right):
            raise ValueError(f"{path} key mismatch")
        for key in left:
            _close(left[key], right[key], path=f"{path}.{key}")
        return
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            raise ValueError(f"{path} length mismatch")
        for index, (a, b) in enumerate(zip(left, right, strict=True)):
            _close(a, b, path=f"{path}[{index}]")
        return
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if not math.isclose(float(left), float(right), rel_tol=1e-10, abs_tol=1e-12):
            raise ValueError(f"{path} numeric mismatch")
        return
    if left != right:
        raise ValueError(f"{path} mismatch")


def _recompute_trial(trial: Mapping[str, Any]) -> Mapping[str, Any]:
    evaluations = trial.get("evaluations")
    runtime = trial.get("runtime")
    if not isinstance(evaluations, Mapping) or not isinstance(runtime, Mapping):
        raise ValueError("raw trial evaluations or runtime are missing")
    recomputed = score_v2_trial(
        cast(Mapping[str, Mapping[str, object]], evaluations),
        recurrence_after_reload=float(trial.get("recurrence_after_reload")),
        candidate_runtime_seconds=float(runtime.get("candidate_seconds")),
        exact_runtime_seconds=float(runtime.get("exact_seconds")),
    )
    _close(recomputed, trial.get("metrics"), path="trial metrics")
    hashes = trial.get("adapter_sha256")
    if not isinstance(hashes, Mapping):
        raise ValueError("adapter hash mapping is missing")
    for key, value in hashes.items():
        _sha(value, name=f"adapter hash {key}")
    return trial


def _replay_selection(
    root: Path, criteria: Mapping[str, object], minimum_width: int
) -> PathPoint:
    development = _json(root / "development.json")
    raw_points = development.get("points")
    if not isinstance(raw_points, list) or not raw_points:
        raise ValueError("development points are missing")
    points_by_path: dict[str, list[PathPoint]] = {}
    for index, raw in enumerate(raw_points):
        if not isinstance(raw, Mapping):
            raise ValueError(f"development point {index} is invalid")
        path_id = str(raw.get("path_id"))
        alpha = float(raw.get("alpha"))
        trials = raw.get("trials")
        if not isinstance(trials, list) or not trials:
            raise ValueError("development point trials are missing")
        verified_trials = [_recompute_trial(cast(Mapping[str, Any], row)) for row in trials]
        point = summarize_path_point(path_id, alpha, verified_trials, criteria)
        published = raw.get("summary")
        _close(
            {
                "feasible": point.feasible,
                "minimum_margin": point.minimum_margin,
                "minimum_speedup": point.minimum_speedup,
                "worst_exact_gap": point.worst_exact_gap,
            },
            published,
            path="development point summary",
        )
        points_by_path.setdefault(path_id, []).append(point)
    return select_robust_point(points_by_path, minimum_width=minimum_width)


def verify_result(
    result_root: Path,
    *,
    protocol_path: Path = DEFAULT_PROTOCOL,
    allow_smoke: bool = False,
) -> dict[str, object]:
    protocol_result = verify_protocol(protocol_path)
    protocol_sha256 = str(protocol_result["protocol_sha256"])
    if not result_root.is_dir():
        raise ValueError("result directory is missing")
    _verify_manifest(result_root, protocol_sha256)
    _verify_state_chain(result_root)
    summary = _json(result_root / "summary.json")
    if summary.get("protocol_sha256") != protocol_sha256:
        raise ValueError("summary protocol hash mismatch")
    decision = summary.get("decision")
    if decision == "NON_SCIENTIFIC_SMOKE":
        if not allow_smoke:
            raise ValueError("smoke output is not a scientific result")
        if (
            summary.get("scientific") is not False
            or summary.get("confirmation_loaded") is not False
        ):
            raise ValueError("smoke boundary is invalid")
        return {"decision": decision, "scientific": False, "verified": True}
    if decision == "NO_CANDIDATE":
        if (result_root / "selection.json").exists() or (result_root / "trials.jsonl").exists():
            raise ValueError("NO_CANDIDATE result contains confirmation evidence")
        development = _json(result_root / "development.json")
        try:
            _replay_selection(
                result_root,
                cast(Mapping[str, object], _json(protocol_path)["success_criteria"]),
                int(_json(protocol_path)["method"]["minimum_contiguous_feasible_alphas"]),
            )
        except NoRobustCandidateError:
            pass
        else:
            raise ValueError("NO_CANDIDATE selection replay found a candidate")
        if development.get("decision") != "NO_CANDIDATE":
            raise ValueError("NO_CANDIDATE development decision mismatch")
        return {"decision": decision, "scientific": True, "verified": True}
    if decision not in {"PASS", "FAIL"}:
        raise ValueError("unknown scientific decision")
    protocol = _json(protocol_path)
    criteria = cast(Mapping[str, object], protocol["success_criteria"])
    method = cast(Mapping[str, object], protocol["method"])
    selected = _replay_selection(
        result_root,
        criteria,
        int(method["minimum_contiguous_feasible_alphas"]),
    )
    selection = _json(result_root / "selection.json")
    if selection.get("selected_path_id") != selected.path_id or not math.isclose(
        float(selection.get("selected_alpha")), selected.alpha, abs_tol=1e-12
    ):
        raise ValueError("selection replay mismatch")
    trials = [_recompute_trial(row) for row in _jsonl(result_root / "trials.jsonl")]
    seeds = set(cast(Sequence[int], protocol["confirmation_seeds"]))
    expected = {(block, seed) for block in ("primary", "replication") for seed in seeds}
    actual = {(str(row.get("block")), int(row.get("seed"))) for row in trials}
    if actual != expected or len(trials) != 10:
        raise ValueError("confirmation seed or block coverage mismatch")
    combined = summarize_v2_trials(trials, criteria)
    expected_decision = combined["decision"]
    _close(combined, summary.get("combined"), path="combined summary")
    if decision != expected_decision:
        raise ValueError("scientific decision mismatch")
    _jsonl(result_root / "baseline_trials.jsonl")
    _jsonl(result_root / "secondary_trials.jsonl")
    return {
        "decision": decision,
        "scientific": True,
        "selected_alpha": selected.alpha,
        "selected_path_id": selected.path_id,
        "trials_checked": len(trials),
        "verified": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independently verify Qwen-TOFU v3")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--result", type=Path, default=ROOT / "outputs/qwen-tofu-kaggle-v3")
    parser.add_argument("--protocol-only", action="store_true")
    parser.add_argument("--allow-smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.protocol_only:
        result = verify_protocol(args.protocol)
    else:
        result = verify_result(
            args.result,
            protocol_path=args.protocol,
            allow_smoke=args.allow_smoke,
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
