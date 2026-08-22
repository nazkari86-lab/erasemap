from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import warnings
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.datasets import fetch_olivetti_faces
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPClassifier

from erasemap.privacy_attacks import evaluate_attack, score_statistics
from erasemap.verification_metrics import bootstrap_mean_interval, normalize_rows

ATTACKS = (
    "confidence_change",
    "energy_change",
    "margin_change",
    "negative_entropy_change",
)


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, check=False, text=True
    )
    return result.stdout.strip() or "unknown"


def is_dirty() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, check=False, text=True
    )
    return bool(result.stdout.strip())


def _validate_protocol(protocol: dict[str, Any]) -> None:
    required = {
        "bootstrap_samples",
        "candidate",
        "dataset",
        "exact_retraining",
        "far_target",
        "local_model",
        "privacy_attacks",
        "random_seeds",
        "schema_version",
        "sequence_length",
        "success_criteria",
        "test_images_per_subject",
        "train_images_per_subject",
    }
    if set(protocol) != required:
        raise ValueError("sequential protocol schema mismatch")
    if protocol["schema_version"] != "erasemap-sequential-deletion-privacy-v1":
        raise ValueError("unsupported sequential protocol")
    if tuple(protocol["privacy_attacks"]) != ATTACKS:
        raise ValueError("privacy attack suite does not match the registered protocol")
    if int(protocol["sequence_length"]) < 2 or len(protocol["random_seeds"]) < 2:
        raise ValueError("sequential evaluation requires multiple steps and seeds")
    if int(protocol["candidate"]["epochs"]) >= int(protocol["exact_retraining"]["epochs"]):
        raise ValueError("candidate must use a smaller frozen epoch budget")


def train_adapter(
    features: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    *,
    hidden_dimension: int,
    epochs: int,
    learning_rate: float,
    weight_decay: float,
    seed: int,
) -> tuple[MLPClassifier, float]:
    model = MLPClassifier(
        hidden_layer_sizes=(hidden_dimension,),
        activation="relu",
        solver="adam",
        alpha=weight_decay,
        batch_size="auto",
        learning_rate_init=learning_rate,
        max_iter=epochs,
        shuffle=False,
        random_state=seed,
        tol=0.0,
        n_iter_no_change=epochs + 1,
    )
    started = time.perf_counter()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        model.fit(features, targets)
    return model, time.perf_counter() - started


def _embeddings(
    model: MLPClassifier, features: np.ndarray[Any, Any]
) -> np.ndarray[Any, Any]:
    hidden = np.maximum(features @ model.coefs_[0] + model.intercepts_[0], 0.0)
    return normalize_rows(hidden)


def _logits(
    model: MLPClassifier, features: np.ndarray[Any, Any]
) -> np.ndarray[Any, Any]:
    hidden = np.maximum(features @ model.coefs_[0] + model.intercepts_[0], 0.0)
    logits: np.ndarray[Any, Any] = hidden @ model.coefs_[1] + model.intercepts_[1]
    return logits


def _select_logits(
    logits: np.ndarray[Any, Any],
    model_classes: np.ndarray[Any, Any],
    selected_classes: np.ndarray[Any, Any],
) -> np.ndarray[Any, Any]:
    positions = {int(label): index for index, label in enumerate(model_classes)}
    return logits[:, [positions[int(label)] for label in selected_classes]]


def release_difference_attacks(
    previous: MLPClassifier,
    previous_classes: np.ndarray[Any, Any],
    current: MLPClassifier,
    current_classes: np.ndarray[Any, Any],
    features: np.ndarray[Any, Any],
    member_indices: np.ndarray[Any, Any],
    nonmember_indices: np.ndarray[Any, Any],
    *,
    target_fpr: float,
) -> dict[str, float]:
    previous_logits = _select_logits(_logits(previous, features), previous_classes, current_classes)
    current_logits = _logits(current, features)
    previous_stats = score_statistics(previous_logits)
    current_stats = score_statistics(current_logits)
    results: dict[str, float] = {}
    for statistic in ("confidence", "energy", "margin", "negative_entropy"):
        change = np.abs(current_stats[statistic] - previous_stats[statistic])
        attack = evaluate_attack(
            change[member_indices], change[nonmember_indices], target_fpr=target_fpr
        )
        results[f"{statistic}_change"] = attack.advantage
    return results


def _accuracy(
    model: MLPClassifier,
    classes: np.ndarray[Any, Any],
    features: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    indices: np.ndarray[Any, Any],
) -> float:
    predicted = model.predict(features[indices])
    return float(np.mean(predicted == targets[indices]))


def _verification_auc(
    model: MLPClassifier,
    features: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    forgotten: np.ndarray[Any, Any],
    *,
    seed: int,
) -> float:
    embeddings = _embeddings(model, features)
    rng = np.random.default_rng(seed)
    positive_pairs: list[tuple[int, int]] = []
    for label in np.unique(targets[forgotten]):
        members = forgotten[targets[forgotten] == label]
        for left in range(len(members)):
            for right in range(left + 1, len(members)):
                positive_pairs.append((int(members[left]), int(members[right])))
    if len(positive_pairs) > 1000:
        selected = rng.choice(len(positive_pairs), size=1000, replace=False)
        positive_pairs = [positive_pairs[int(index)] for index in selected]
    negative_pairs: list[tuple[int, int]] = []
    while len(negative_pairs) < len(positive_pairs):
        left, right = rng.integers(0, len(targets), size=2)
        if targets[left] != targets[right]:
            negative_pairs.append((int(left), int(right)))
    positive = np.asarray([embeddings[a] @ embeddings[b] for a, b in positive_pairs])
    negative = np.asarray([embeddings[a] @ embeddings[b] for a, b in negative_pairs])
    labels = np.concatenate((np.ones(len(positive)), np.zeros(len(negative))))
    scores = np.concatenate((positive, negative))
    from sklearn.metrics import roc_auc_score

    return float(roc_auc_score(labels, scores))


def _paired_privacy_summary(
    trials: list[dict[str, Any]], *, bootstrap_samples: int
) -> dict[str, dict[str, object]]:
    output: dict[str, dict[str, object]] = {}
    for offset, attack in enumerate(ATTACKS):
        differences = np.asarray(
            [
                float(row["candidate_privacy_advantage"][attack])
                - float(row["exact_privacy_advantage"][attack])
                for row in trials
            ],
            dtype=np.float64,
        )
        interval = bootstrap_mean_interval(
            differences,
            seed=20260920 + offset,
            samples=bootstrap_samples,
        )
        output[attack] = {
            "ci95": list(interval),
            "mean_difference": float(np.mean(differences)),
            "transitions": len(differences),
        }
    return output


def run(protocol_path: Path, output: Path) -> dict[str, Any]:
    if is_dirty():
        raise RuntimeError("sequential evaluation requires a clean working tree")
    protocol = json.loads(protocol_path.read_text())
    _validate_protocol(protocol)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    embeddings_path = Path(protocol["dataset"]["embeddings"])
    features = np.asarray(joblib.load(embeddings_path), dtype=np.float32)
    dataset = fetch_olivetti_faces(
        data_home="data/real", download_if_missing=False, shuffle=False
    )
    targets = np.asarray(dataset.target, dtype=np.int64)
    if len(features) != len(targets):
        raise ValueError("embedding and target counts differ")
    split_protocol = json.loads(Path(protocol["dataset"]["targets_protocol"]).read_text())
    from erasemap.real_model import deterministic_subject_split

    split = deterministic_subject_split(
        targets,
        train_per_subject=int(protocol["train_images_per_subject"]),
        seed=int(split_protocol["random_seed"]),
    )
    train = np.asarray(split.train_indices, dtype=np.int64)
    test = np.asarray(split.test_indices, dtype=np.int64)
    all_classes = np.unique(targets)
    local = protocol["local_model"]
    exact_epochs = int(protocol["exact_retraining"]["epochs"])
    candidate_epochs = int(protocol["candidate"]["epochs"])
    trials: list[dict[str, Any]] = []
    for seed_value in protocol["random_seeds"]:
        seed = int(seed_value)
        rng = np.random.default_rng(seed)
        deletion_order = rng.choice(
            all_classes, size=int(protocol["sequence_length"]), replace=False
        )
        previous, _ = train_adapter(
            features[train],
            targets[train],
            hidden_dimension=int(local["hidden_dimension"]),
            epochs=exact_epochs,
            learning_rate=float(local["learning_rate"]),
            weight_decay=float(local["weight_decay"]),
            seed=seed,
        )
        previous_candidate = previous
        previous_exact = previous
        previous_classes = all_classes
        deleted: list[int] = []
        for step, deleted_value in enumerate(deletion_order, start=1):
            deleted.append(int(deleted_value))
            classes = np.asarray(
                [label for label in all_classes if int(label) not in deleted], dtype=np.int64
            )
            retained_train = train[np.isin(targets[train], classes)]
            retained_test = test[np.isin(targets[test], classes)]
            forgotten = np.flatnonzero(np.isin(targets, deleted))
            step_seed = seed + step * 1000
            exact, exact_runtime = train_adapter(
                features[retained_train],
                targets[retained_train],
                hidden_dimension=int(local["hidden_dimension"]),
                epochs=exact_epochs,
                learning_rate=float(local["learning_rate"]),
                weight_decay=float(local["weight_decay"]),
                seed=step_seed,
            )
            candidate, candidate_runtime = train_adapter(
                features[retained_train],
                targets[retained_train],
                hidden_dimension=int(local["hidden_dimension"]),
                epochs=candidate_epochs,
                learning_rate=float(local["learning_rate"]),
                weight_decay=float(local["weight_decay"]),
                seed=step_seed,
            )
            candidate_privacy = release_difference_attacks(
                previous_candidate,
                previous_classes,
                candidate,
                classes,
                features,
                retained_train,
                retained_test,
                target_fpr=float(protocol["far_target"]),
            )
            exact_privacy = release_difference_attacks(
                previous_exact,
                previous_classes,
                exact,
                classes,
                features,
                retained_train,
                retained_test,
                target_fpr=float(protocol["far_target"]),
            )
            candidate_embeddings = _embeddings(candidate, features[retained_test])
            exact_embeddings = _embeddings(exact, features[retained_test])
            candidate_forgotten_auc = _verification_auc(
                candidate, features, targets, forgotten, seed=step_seed
            )
            exact_forgotten_auc = _verification_auc(
                exact, features, targets, forgotten, seed=step_seed
            )
            candidate_accuracy = _accuracy(candidate, classes, features, targets, retained_test)
            exact_accuracy = _accuracy(exact, classes, features, targets, retained_test)
            trials.append(
                {
                    "candidate_privacy_advantage": candidate_privacy,
                    "candidate_retained_accuracy": candidate_accuracy,
                    "candidate_runtime_seconds": candidate_runtime,
                    "deleted_class_absent": int(deleted_value) not in set(map(int, classes)),
                    "deleted_count": len(deleted),
                    "epoch_budget_speedup": exact_epochs / candidate_epochs,
                    "exact_privacy_advantage": exact_privacy,
                    "exact_retained_accuracy": exact_accuracy,
                    "exact_runtime_seconds": exact_runtime,
                    "forgotten_verification_auc_gap": abs(
                        candidate_forgotten_auc - exact_forgotten_auc
                    ),
                    "retained_accuracy_delta": candidate_accuracy - exact_accuracy,
                    "retained_embedding_mse_to_exact": float(
                        np.mean((candidate_embeddings - exact_embeddings) ** 2)
                    ),
                    "seed": seed,
                    "step": step,
                }
            )
            previous_candidate = candidate
            previous_exact = exact
            previous_classes = classes
    privacy = _paired_privacy_summary(
        trials, bootstrap_samples=int(protocol["bootstrap_samples"])
    )
    criteria = protocol["success_criteria"]
    max_privacy_upper = max(float(value["ci95"][1]) for value in privacy.values())
    gates = {
        "all_deleted_classes_absent": all(bool(row["deleted_class_absent"]) for row in trials),
        "candidate_epoch_budget_speedup": min(
            float(row["epoch_budget_speedup"]) for row in trials
        )
        >= float(criteria["candidate_epoch_budget_speedup_min"]),
        "candidate_retained_accuracy_delta": min(
            float(row["retained_accuracy_delta"]) for row in trials
        )
        >= float(criteria["candidate_retained_accuracy_delta_min"]),
        "forgotten_verification_auc_gap": max(
            float(row["forgotten_verification_auc_gap"]) for row in trials
        )
        <= float(criteria["forgotten_verification_auc_gap_max"]),
        "max_privacy_advantage_paired_upper_ci": max_privacy_upper
        <= float(criteria["max_privacy_advantage_paired_upper_ci_max"]),
        "retained_embedding_mse_to_exact": max(
            float(row["retained_embedding_mse_to_exact"]) for row in trials
        )
        <= float(criteria["retained_embedding_mse_to_exact_max"]),
    }
    summary: dict[str, Any] = {
        "claim_boundary": (
            "Project-authored preregistered sequential-release experiment on external Olivetti "
            "inputs; release-difference attacks use no shadow models and are not independent "
            "evidence."
        ),
        "code_revision": revision(),
        "dataset": {"images": len(features), "name": protocol["dataset"]["name"]},
        "decision": "PASS" if all(gates.values()) else "FAIL",
        "endpoints": {
            "max_forgotten_verification_auc_gap": max(
                float(row["forgotten_verification_auc_gap"]) for row in trials
            ),
            "max_privacy_advantage_paired_upper_ci": max_privacy_upper,
            "max_retained_embedding_mse_to_exact": max(
                float(row["retained_embedding_mse_to_exact"]) for row in trials
            ),
            "min_retained_accuracy_delta": min(
                float(row["retained_accuracy_delta"]) for row in trials
            ),
        },
        "gates": gates,
        "paired_privacy": privacy,
        "protocol_sha256": sha256_file(protocol_path),
        "schema_version": "erasemap-sequential-deletion-privacy-result-v1",
        "sequences": len(protocol["random_seeds"]),
        "transitions": len(trials),
    }
    output.mkdir(parents=True)
    trials_path = output / "trials.jsonl"
    trials_path.write_text("".join(canonical_json(row) + "\n" for row in trials))
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    manifest = {
        "embeddings_sha256": sha256_file(embeddings_path),
        "protocol_sha256": sha256_file(protocol_path),
        "summary_sha256": sha256_file(output / "summary.json"),
        "trials_sha256": sha256_file(trials_path),
    }
    (output / "MANIFEST.sha256.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Sequential deletion privacy evaluation")
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("benchmark/sequential-deletion-privacy-v1.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.protocol, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
