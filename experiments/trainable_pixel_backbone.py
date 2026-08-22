from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.datasets import fetch_olivetti_faces
from torch import nn

from erasemap.real_model import deterministic_subject_split
from erasemap.verification_metrics import bootstrap_mean_interval, verification_metrics


class TrainableFaceCNN(nn.Module):
    def __init__(self, classes: int, embedding_dimension: int = 32) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(1, 4, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(4, 8, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.AdaptiveAvgPool2d((4, 4)),
            nn.Flatten(),
            nn.Linear(8 * 4 * 4, embedding_dimension),
            nn.ReLU(),
        )
        self.classifier = nn.Linear(embedding_dimension, classes)

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.encoder(images))


@dataclass(frozen=True, slots=True)
class TrainableFaceFit:
    model: TrainableFaceCNN
    runtime_seconds: float
    parameters_with_gradient: int
    trainable_parameters: int


def mapped_targets(
    targets: np.ndarray[Any, Any], classes: np.ndarray[Any, Any]
) -> torch.Tensor:
    positions = {int(label): index for index, label in enumerate(classes)}
    return torch.tensor([positions[int(value)] for value in targets], dtype=torch.long)


def train_pixel_model(
    images: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    classes: np.ndarray[Any, Any],
    *,
    epochs: int,
    learning_rate: float,
    weight_decay: float,
    seed: int,
    embedding_dimension: int,
) -> TrainableFaceFit:
    torch.manual_seed(seed)
    model = TrainableFaceCNN(len(classes), embedding_dimension)
    tensor_images = torch.from_numpy(images).float().unsqueeze(1)
    tensor_targets = mapped_targets(targets, classes)
    optimizer = torch.optim.Adam(
        model.parameters(), learning_rate, weight_decay=weight_decay
    )
    gradient_names: set[str] = set()
    started = time.perf_counter()
    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        loss = nn.functional.cross_entropy(model(tensor_images), tensor_targets)
        loss.backward()
        gradient_names.update(
            name
            for name, parameter in model.named_parameters()
            if parameter.grad is not None and bool(torch.any(parameter.grad != 0))
        )
        optimizer.step()
    runtime = time.perf_counter() - started
    trainable = sum(1 for parameter in model.parameters() if parameter.requires_grad)
    return TrainableFaceFit(model.eval(), runtime, len(gradient_names), trainable)


def pixel_embeddings(
    model: TrainableFaceCNN, images: np.ndarray[Any, Any]
) -> np.ndarray[Any, Any]:
    with torch.inference_mode():
        values = model.encoder(torch.from_numpy(images).float().unsqueeze(1)).numpy()
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return (values / np.maximum(norms, 1e-12)).astype(np.float32)


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def verification_auc(
    embeddings: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    indices: np.ndarray[Any, Any],
    seed: int,
) -> float:
    positives: list[tuple[int, int]] = []
    for label in np.unique(targets[indices]):
        members = [int(value) for value in indices[targets[indices] == label]]
        positives.extend(combinations(members, 2))
    rng = np.random.default_rng(seed)
    negatives: list[tuple[int, int]] = []
    while len(negatives) < len(positives):
        left, right = (int(value) for value in rng.choice(indices, 2, replace=True))
        if targets[left] != targets[right]:
            negatives.append((left, right))
    positive_scores = np.asarray([embeddings[a] @ embeddings[b] for a, b in positives])
    negative_scores = np.asarray([embeddings[a] @ embeddings[b] for a, b in negatives])
    return verification_metrics(positive_scores, negative_scores, far_target=0.01).auc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", default="benchmark/trainable-pixel-backbone-v1.json")
    parser.add_argument("--data-home", default="data/real")
    parser.add_argument("--output", default="outputs/trainable-pixel-backbone-v1")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text())
    dataset = fetch_olivetti_faces(
        data_home=args.data_home, download_if_missing=args.download, shuffle=False
    )
    images = np.asarray(dataset.images, dtype=np.float32)
    targets = np.asarray(dataset.target, dtype=np.int64)
    split = deterministic_subject_split(
        targets,
        train_per_subject=int(protocol["train_images_per_subject"]),
        seed=int(protocol["split_seed"]),
    )
    train = np.asarray(split.train_indices)
    test = np.asarray(split.test_indices)
    classes = np.unique(targets)
    trials: list[dict[str, Any]] = []
    full_gradient_coverage = True
    for seed_value in protocol["random_seeds"]:
        seed = int(seed_value)
        stale = train_pixel_model(
            images[train],
            targets[train],
            classes,
            epochs=int(protocol["exact_epochs"]),
            learning_rate=float(protocol["learning_rate"]),
            weight_decay=float(protocol["weight_decay"]),
            seed=seed,
            embedding_dimension=int(protocol["embedding_dimension"]),
        )
        stale_embeddings = pixel_embeddings(stale.model, images)
        selected = np.random.default_rng(seed).choice(
            classes,
            size=int(protocol["forget_identities_per_seed"]),
            replace=False,
        )
        for forget_value in selected:
            forget = int(forget_value)
            retained_train = train[targets[train] != forget]
            retained_classes = classes[classes != forget]
            exact = train_pixel_model(
                images[retained_train],
                targets[retained_train],
                retained_classes,
                epochs=int(protocol["exact_epochs"]),
                learning_rate=float(protocol["learning_rate"]),
                weight_decay=float(protocol["weight_decay"]),
                seed=seed,
                embedding_dimension=int(protocol["embedding_dimension"]),
            )
            candidate = train_pixel_model(
                images[retained_train],
                targets[retained_train],
                retained_classes,
                epochs=int(protocol["candidate_epochs"]),
                learning_rate=float(protocol["candidate_learning_rate"]),
                weight_decay=float(protocol["weight_decay"]),
                seed=seed,
                embedding_dimension=int(protocol["embedding_dimension"]),
            )
            exact_embeddings = pixel_embeddings(exact.model, images)
            candidate_embeddings = pixel_embeddings(candidate.model, images)
            forgotten = np.flatnonzero(targets == forget)
            retained_test = test[targets[test] != forget]
            stale_forgotten = float(
                np.mean((stale_embeddings[forgotten] - exact_embeddings[forgotten]) ** 2)
            )
            stale_retained = float(
                np.mean((stale_embeddings[retained_test] - exact_embeddings[retained_test]) ** 2)
            )
            candidate_forgotten = float(
                np.mean((candidate_embeddings[forgotten] - exact_embeddings[forgotten]) ** 2)
            )
            candidate_retained = float(
                np.mean(
                    (candidate_embeddings[retained_test] - exact_embeddings[retained_test]) ** 2
                )
            )
            full_gradient_coverage &= (
                candidate.parameters_with_gradient == candidate.trainable_parameters
                and exact.parameters_with_gradient == exact.trainable_parameters
            )
            trials.append(
                {
                    "anonymous_forget_subject": forget,
                    "candidate_forgotten_mse": candidate_forgotten,
                    "candidate_retained_auc": verification_auc(
                        candidate_embeddings, targets, retained_test, seed + forget
                    ),
                    "candidate_retained_mse": candidate_retained,
                    "exact_retained_auc": verification_auc(
                        exact_embeddings, targets, retained_test, seed + forget
                    ),
                    "forgotten_mse_ratio_to_stale": candidate_forgotten
                    / max(stale_forgotten, 1e-12),
                    "retained_mse_ratio_to_stale": candidate_retained
                    / max(stale_retained, 1e-12),
                    "seed": seed,
                    "speedup_vs_exact": exact.runtime_seconds
                    / max(candidate.runtime_seconds, 1e-12),
                }
            )
    summary: dict[str, Any] = {}
    for metric in (
        "forgotten_mse_ratio_to_stale",
        "retained_mse_ratio_to_stale",
        "candidate_retained_auc",
        "exact_retained_auc",
        "speedup_vs_exact",
    ):
        values = np.asarray([float(row[metric]) for row in trials])
        summary[metric] = {
            "ci95": list(
                bootstrap_mean_interval(
                    values,
                    seed=int(protocol["random_seeds"][0]),
                    samples=int(protocol["bootstrap_samples"]),
                )
            ),
            "mean": float(np.mean(values)),
        }
    criteria = protocol["success_criteria"]
    retained_auc_delta = (
        summary["candidate_retained_auc"]["mean"]
        - summary["exact_retained_auc"]["mean"]
    )
    success = (
        full_gradient_coverage
        and summary["forgotten_mse_ratio_to_stale"]["mean"]
        <= float(criteria["forgotten_embedding_mse_ratio_to_stale_max"])
        and summary["retained_mse_ratio_to_stale"]["mean"]
        <= float(criteria["retained_embedding_mse_ratio_to_stale_max"])
        and retained_auc_delta >= float(criteria["retained_verification_auc_delta_min"])
        and summary["speedup_vs_exact"]["mean"] >= float(criteria["speedup_min"])
    )
    result = {
        "claim_boundary": (
            "The entire CNN, including both convolutional layers, is trained from pixels on "
            "Olivetti. This proves the deletion protocol on a small local backbone, not on a "
            "production FaceID foundation model."
        ),
        "dataset": {"images": len(images), "name": "Olivetti Faces", "subjects": len(classes)},
        "full_gradient_coverage": full_gradient_coverage,
        "manifests": {"protocol": sha256_file(protocol_path)},
        "retained_auc_delta": retained_auc_delta,
        "success": success,
        "summary": summary,
        "trial_count": len(trials),
        "trials": trials,
    }
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "result.json").write_text(canonical_json(result) + "\n")
    print(canonical_json({"success": success, "summary": summary, "trial_count": len(trials)}))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
