from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np
from run_resnet18_face_unlearning import extract_embeddings
from sklearn.datasets import fetch_olivetti_faces

from erasemap.real_model import (
    deterministic_subject_split,
    evaluate_models,
    train_face_model,
)


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol", default="benchmark/real-face-resnet18-protocol-v1.json"
    )
    parser.add_argument("--data-home", default="data/real")
    parser.add_argument("--output", default="outputs/real-face-resnet18-sweep-v1")
    args = parser.parse_args()
    protocol = json.loads(Path(args.protocol).read_text())
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    dataset = fetch_olivetti_faces(
        data_home=args.data_home, download_if_missing=False, shuffle=False
    )
    images = np.asarray(dataset.images, dtype=np.float32)
    targets = np.asarray(dataset.target, dtype=np.int64)
    seed = int(protocol["random_seed"])
    split = deterministic_subject_split(
        targets,
        train_per_subject=int(protocol["train_images_per_subject"]),
        seed=seed,
    )
    embeddings = extract_embeddings(images)
    components = int(protocol["head"]["pca_components"])
    max_iter = int(protocol["head"]["max_iter"])
    stale = train_face_model(
        embeddings[list(split.train_indices)],
        targets[list(split.train_indices)],
        pca_components=components,
        max_iter=max_iter,
        seed=seed,
    )
    threshold = float(protocol["success_criteria"]["minimum_retained_accuracy_delta"])
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for subject in range(40):
        retained = [
            index for index in split.train_indices if int(targets[index]) != subject
        ]
        exact = train_face_model(
            embeddings[retained],
            targets[retained],
            pca_components=components,
            max_iter=max_iter,
            seed=seed,
        )
        comparison = evaluate_models(
            stale, exact, embeddings, targets, split, forget_subject=subject
        )
        delta = (
            comparison.exact.retained_test_accuracy
            - comparison.stale.retained_test_accuracy
        )
        rows.append(
            {
                "exact_deleted_class_present": comparison.exact.deleted_class_present,
                "exact_forgotten_class_probability": (
                    comparison.exact.forgotten_class_probability
                ),
                "exact_retained_accuracy": comparison.exact.retained_test_accuracy,
                "forgotten_subject": subject,
                "passed_frozen_criteria": (
                    not comparison.exact.deleted_class_present
                    and comparison.exact.forgotten_class_probability == 0.0
                    and delta >= threshold
                ),
                "retained_accuracy_delta": delta,
                "retained_prediction_disagreement": (
                    comparison.retained_prediction_disagreement
                ),
                "stale_forgotten_class_probability": (
                    comparison.stale.forgotten_class_probability
                ),
                "stale_retained_accuracy": comparison.stale.retained_test_accuracy,
            }
        )
    stale_probabilities = [
        float(row["stale_forgotten_class_probability"]) for row in rows
    ]
    exact_accuracies = [float(row["exact_retained_accuracy"]) for row in rows]
    deltas = [float(row["retained_accuracy_delta"]) for row in rows]
    result = {
        "claim_boundary": (
            "Exploratory all-subject robustness sweep on one small public dataset; "
            "not a locked holdout or production validation."
        ),
        "failed_subjects": [
            int(row["forgotten_subject"])
            for row in rows
            if not row["passed_frozen_criteria"]
        ],
        "per_subject": rows,
        "summary": {
            "exact_deleted_class_present_count": sum(
                bool(row["exact_deleted_class_present"]) for row in rows
            ),
            "exact_retained_accuracy_mean": statistics.mean(exact_accuracies),
            "exact_retained_accuracy_min": min(exact_accuracies),
            "passed_subjects": sum(bool(row["passed_frozen_criteria"]) for row in rows),
            "retained_accuracy_delta_mean": statistics.mean(deltas),
            "retained_accuracy_delta_min": min(deltas),
            "stale_forgotten_probability_max": max(stale_probabilities),
            "stale_forgotten_probability_median": statistics.median(
                stale_probabilities
            ),
            "stale_forgotten_probability_min": min(stale_probabilities),
            "subjects": len(rows),
            "sweep_runtime_seconds": time.perf_counter() - started,
        },
    }
    (output / "result.json").write_text(canonical_json(result) + "\n")
    print(canonical_json(result["summary"]))
    return 0 if not result["failed_subjects"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
