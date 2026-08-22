from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any, cast

import numpy as np

ATTACKS = (
    "confidence_change",
    "energy_change",
    "margin_change",
    "negative_entropy_change",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _git_has_commit(commit: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def _bootstrap_interval(values: list[float], *, seed: int, samples: int) -> list[float]:
    observations = np.asarray(values, dtype=np.float64)
    rng = np.random.default_rng(seed)
    means = np.mean(
        rng.choice(observations, size=(samples, len(observations)), replace=True), axis=1
    )
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)


def verify_result(
    result_dir: Path,
    *,
    protocol_path: Path = Path("benchmark/sequential-deletion-privacy-v1.json"),
) -> dict[str, object]:
    summary_path = result_dir / "summary.json"
    trials_path = result_dir / "trials.jsonl"
    manifest_path = result_dir / "MANIFEST.sha256.json"
    protocol = cast(dict[str, Any], json.loads(protocol_path.read_text()))
    summary = cast(dict[str, Any], json.loads(summary_path.read_text()))
    manifest = cast(dict[str, str], json.loads(manifest_path.read_text()))
    trials = [json.loads(line) for line in trials_path.read_text().splitlines() if line]

    expected_manifest = {
        "embeddings_sha256": _sha256(Path(protocol["dataset"]["embeddings"])),
        "protocol_sha256": _sha256(protocol_path),
        "summary_sha256": _sha256(summary_path),
        "trials_sha256": _sha256(trials_path),
    }
    if manifest != expected_manifest:
        raise ValueError("result manifest does not match committed artifacts")
    if summary.get("protocol_sha256") != expected_manifest["protocol_sha256"]:
        raise ValueError("summary is bound to a different protocol")

    commit = summary.get("code_revision")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("result must name a full hexadecimal code revision")
    if not _git_has_commit(commit):
        raise ValueError("result code revision is not present in repository history")

    expected_count = len(protocol["random_seeds"]) * int(protocol["sequence_length"])
    if len(trials) != expected_count or int(summary.get("transitions", -1)) != expected_count:
        raise ValueError("transition count does not match the preregistration")
    expected_units = {
        (int(seed), step)
        for seed in protocol["random_seeds"]
        for step in range(1, int(protocol["sequence_length"]) + 1)
    }
    actual_units = {(int(row["seed"]), int(row["step"])) for row in trials}
    if actual_units != expected_units:
        raise ValueError("sequence and step units do not match the preregistration")

    privacy: dict[str, dict[str, object]] = {}
    for offset, attack in enumerate(ATTACKS):
        differences = [
            float(row["candidate_privacy_advantage"][attack])
            - float(row["exact_privacy_advantage"][attack])
            for row in trials
        ]
        privacy[attack] = {
            "ci95": _bootstrap_interval(
                differences,
                seed=20260920 + offset,
                samples=int(protocol["bootstrap_samples"]),
            ),
            "mean_difference": float(np.mean(differences)),
            "transitions": len(differences),
        }
    for attack in ATTACKS:
        published = summary["paired_privacy"][attack]
        recalculated = privacy[attack]
        if not _close(float(published["mean_difference"]), float(recalculated["mean_difference"])):
            raise ValueError(f"mean privacy difference mismatch: {attack}")
        for observed, expected in zip(published["ci95"], recalculated["ci95"], strict=True):
            if not _close(float(observed), float(expected)):
                raise ValueError(f"privacy interval mismatch: {attack}")

    criteria = protocol["success_criteria"]
    endpoints = {
        "max_forgotten_verification_auc_gap": max(
            float(row["forgotten_verification_auc_gap"]) for row in trials
        ),
        "max_privacy_advantage_paired_upper_ci": max(
            float(value["ci95"][1]) for value in privacy.values()
        ),
        "max_retained_embedding_mse_to_exact": max(
            float(row["retained_embedding_mse_to_exact"]) for row in trials
        ),
        "min_retained_accuracy_delta": min(
            float(row["retained_accuracy_delta"]) for row in trials
        ),
    }
    for name, value in endpoints.items():
        if not _close(float(summary["endpoints"][name]), value):
            raise ValueError(f"endpoint mismatch: {name}")

    gates = {
        "all_deleted_classes_absent": all(bool(row["deleted_class_absent"]) for row in trials),
        "candidate_epoch_budget_speedup": min(
            float(row["epoch_budget_speedup"]) for row in trials
        )
        >= float(criteria["candidate_epoch_budget_speedup_min"]),
        "candidate_retained_accuracy_delta": endpoints["min_retained_accuracy_delta"]
        >= float(criteria["candidate_retained_accuracy_delta_min"]),
        "forgotten_verification_auc_gap": endpoints["max_forgotten_verification_auc_gap"]
        <= float(criteria["forgotten_verification_auc_gap_max"]),
        "max_privacy_advantage_paired_upper_ci": endpoints[
            "max_privacy_advantage_paired_upper_ci"
        ]
        <= float(criteria["max_privacy_advantage_paired_upper_ci_max"]),
        "retained_embedding_mse_to_exact": endpoints["max_retained_embedding_mse_to_exact"]
        <= float(criteria["retained_embedding_mse_to_exact_max"]),
    }
    if summary.get("gates") != gates:
        raise ValueError("published gates do not match independently recomputed gates")
    decision = "PASS" if all(gates.values()) else "FAIL"
    if summary.get("decision") != decision:
        raise ValueError("published decision does not match independently recomputed gates")

    return {
        "code_revision": commit,
        "decision": decision,
        "manifest": "PASS",
        "schema_version": "erasemap-sequential-deletion-privacy-verification-v1",
        "transitions_checked": len(trials),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify sequential deletion privacy v1 result")
    parser.add_argument(
        "--result",
        type=Path,
        default=Path("benchmark/results/sequential-deletion-privacy-v1"),
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("benchmark/sequential-deletion-privacy-v1.json"),
    )
    args = parser.parse_args()
    print(json.dumps(verify_result(args.result, protocol_path=args.protocol), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
