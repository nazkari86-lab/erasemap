from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import time
from itertools import combinations
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import torch
from advanced_face_unlearning import (
    FaceAdapter,
    _load_dataset,
    _mapped_targets,
    gradient_ascent_unlearn,
    train_adapter,
)
from sklearn.metrics import roc_auc_score
from torch import nn

from erasemap.verification_metrics import (
    bootstrap_mean_interval,
    linear_cka,
    normalize_rows,
    verification_metrics,
)

METHODS = ("stale", "head_only", "gradient_ascent", "lineage_guided", "exact_retrain")
METRICS = (
    "retained_verification_auc",
    "retained_tar_at_far",
    "forgotten_verification_auc",
    "membership_attack_auc",
    "functional_embedding_mse_to_exact",
    "retained_cka_to_exact",
    "runtime_seconds",
    "speedup_vs_exact",
)


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


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


def encoder_embeddings(model: FaceAdapter, features: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    with torch.inference_mode():
        values = model.encoder(torch.from_numpy(features).float()).numpy()
    return normalize_rows(values).astype(np.float32)


def probabilities(model: FaceAdapter, features: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    with torch.inference_mode():
        return torch.softmax(model(torch.from_numpy(features).float()), dim=1).numpy()


def pair_scores(
    embeddings: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    indices: np.ndarray[Any, Any],
    *,
    seed: int,
    max_pairs: int = 3000,
    negative_pool: np.ndarray[Any, Any] | None = None,
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    positive_pairs: list[tuple[int, int]] = []
    for label in np.unique(targets[indices]):
        members = [int(value) for value in indices[targets[indices] == label]]
        positive_pairs.extend(combinations(members, 2))
    rng = np.random.default_rng(seed)
    if len(positive_pairs) > max_pairs:
        selected = rng.choice(len(positive_pairs), size=max_pairs, replace=False)
        positive_pairs = [positive_pairs[int(index)] for index in selected]
    if not positive_pairs:
        raise ValueError("at least one positive pair is required")
    pool = indices if negative_pool is None else negative_pool
    if len(np.unique(targets[pool])) < 2:
        raise ValueError("negative pool must contain at least two identities")
    negative_pairs: list[tuple[int, int]] = []
    while len(negative_pairs) < len(positive_pairs):
        remaining = len(positive_pairs) - len(negative_pairs)
        candidates = rng.choice(pool, size=(max(32, remaining * 2), 2), replace=True)
        different = candidates[targets[candidates[:, 0]] != targets[candidates[:, 1]]]
        negative_pairs.extend((int(left), int(right)) for left, right in different[:remaining])
    positive = np.asarray([np.dot(embeddings[a], embeddings[b]) for a, b in positive_pairs])
    negative = np.asarray([np.dot(embeddings[a], embeddings[b]) for a, b in negative_pairs])
    return positive, negative


def lineage_guided_unlearn(
    original: FaceAdapter,
    retain_features: np.ndarray[Any, Any],
    retain_targets: np.ndarray[Any, Any],
    forget_features: np.ndarray[Any, Any],
    forget_targets: np.ndarray[Any, Any],
    classes: np.ndarray[Any, Any],
    settings: dict[str, Any],
    seed: int,
) -> tuple[FaceAdapter, float, float]:
    torch.manual_seed(seed)
    model = copy.deepcopy(original).train()
    retain_x = torch.from_numpy(retain_features).float()
    retain_y = _mapped_targets(retain_targets, classes)
    forget_x = torch.from_numpy(forget_features).float()
    forget_y = _mapped_targets(forget_targets, classes)
    with torch.inference_mode():
        reference_embeddings = original.encoder(retain_x).detach()
    model.zero_grad()
    nn.functional.cross_entropy(model(forget_x), forget_y).backward()
    sensitivities = [
        parameter.grad.detach().abs().flatten()
        for parameter in model.parameters()
        if parameter.grad is not None
    ]
    threshold = torch.quantile(
        torch.cat(sensitivities), 1 - float(settings["top_parameter_fraction"])
    )
    masks = {
        name: (parameter.grad.detach().abs() >= threshold)
        for name, parameter in model.named_parameters()
        if parameter.grad is not None
    }
    selected = sum(int(mask.sum()) for mask in masks.values())
    total = sum(mask.numel() for mask in masks.values())
    reference = {name: parameter.detach().clone() for name, parameter in model.named_parameters()}
    optimizer = torch.optim.Adam(model.parameters(), lr=float(settings["learning_rate"]))
    generator = torch.Generator().manual_seed(seed)
    batch_size = min(256, len(retain_x))
    started = time.perf_counter()
    for _ in range(int(settings["steps"])):
        selection = torch.randperm(len(retain_x), generator=generator)[:batch_size]
        optimizer.zero_grad()
        current_embeddings = model.encoder(retain_x[selection])
        retain_loss = nn.functional.cross_entropy(
            model.classifier(current_embeddings), retain_y[selection]
        )
        forget_loss = nn.functional.cross_entropy(model(forget_x), forget_y)
        distillation = nn.functional.mse_loss(current_embeddings, reference_embeddings[selection])
        drift = sum(
            torch.mean((parameter - reference[name]) ** 2)
            for name, parameter in model.named_parameters()
        )
        loss = (
            retain_loss
            - float(settings["forget_weight"]) * forget_loss
            + float(settings["retain_distillation_weight"]) * distillation
            + float(settings["parameter_drift_weight"]) * drift
        )
        loss.backward()
        for name, parameter in model.named_parameters():
            if parameter.grad is not None:
                parameter.grad.mul_(masks[name])
        torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
        optimizer.step()
    return model.eval(), time.perf_counter() - started, selected / total


def evaluate_method(
    model: FaceAdapter,
    exact: FaceAdapter,
    features: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    train: np.ndarray[Any, Any],
    test: np.ndarray[Any, Any],
    forget_subject: int,
    *,
    runtime: float,
    exact_runtime: float,
    far_target: float,
    seed: int,
) -> dict[str, float]:
    model_embeddings = encoder_embeddings(model, features)
    exact_embeddings = encoder_embeddings(exact, features)
    forget_all = np.flatnonzero(targets == forget_subject)
    retain_test = test[targets[test] != forget_subject]
    forgotten_train = train[targets[train] == forget_subject]
    forgotten_test = test[targets[test] == forget_subject]
    retained_positive, retained_negative = pair_scores(
        model_embeddings, targets, retain_test, seed=seed
    )
    forgotten_positive, forgotten_negative = pair_scores(
        model_embeddings,
        targets,
        forget_all,
        seed=seed + 1,
        max_pairs=1000,
        negative_pool=np.arange(len(targets)),
    )
    retained = verification_metrics(retained_positive, retained_negative, far_target=far_target)
    forgotten = verification_metrics(forgotten_positive, forgotten_negative, far_target=far_target)
    member_confidence = np.max(probabilities(model, features[forgotten_train]), axis=1)
    nonmember_confidence = np.max(probabilities(model, features[forgotten_test]), axis=1)
    membership_auc = float(
        roc_auc_score(
            np.concatenate((np.ones(len(member_confidence)), np.zeros(len(nonmember_confidence)))),
            np.concatenate((member_confidence, nonmember_confidence)),
        )
    )
    mse = float(np.mean((model_embeddings - exact_embeddings) ** 2))
    return {
        "forgotten_verification_auc": forgotten.auc,
        "functional_embedding_mse_to_exact": mse,
        "membership_attack_auc": membership_auc,
        "retained_cka_to_exact": linear_cka(
            model_embeddings[retain_test], exact_embeddings[retain_test]
        ),
        "retained_tar_at_far": retained.tar_at_far,
        "retained_verification_auc": retained.auc,
        "runtime_seconds": runtime,
        "speedup_vs_exact": exact_runtime / max(runtime, 1e-9),
    }


def run_split(protocol_path: Path, split: str, output: Path) -> dict[str, Any]:
    if split == "evaluation" and is_dirty():
        raise RuntimeError("evaluation requires a clean working tree")
    protocol = json.loads(protocol_path.read_text())
    dataset_settings = protocol["datasets"][split]
    source_protocol = json.loads(Path(dataset_settings["protocol"]).read_text())
    dataset = _load_dataset(dataset_settings["name"], source_protocol, Path("data/real"))
    features = np.asarray(joblib.load(dataset_settings["embeddings"]), dtype=np.float32)
    train = np.asarray(dataset.train_indices)
    test = np.asarray(dataset.test_indices)
    targets = dataset.targets
    classes = np.unique(targets)
    local = protocol["local_model"]
    output.mkdir(parents=True, exist_ok=True)
    if split == "evaluation":
        lock = output / "evaluation.lock.json"
        if lock.exists():
            raise RuntimeError("evaluation lock already exists")
        lock.write_text(
            canonical_json(
                {
                    "code_revision": revision(),
                    "protocol_sha256": sha256_file(protocol_path),
                    "schema_version": "erasemap-task-agnostic-evaluation-lock-v1",
                }
            )
            + "\n"
        )
    trials: list[dict[str, Any]] = []
    for seed in protocol["random_seeds"]:
        original, _ = train_adapter(
            features[train],
            targets[train],
            classes=classes,
            hidden_dimension=int(local["hidden_dimension"]),
            epochs=int(local["epochs"]),
            learning_rate=float(local["learning_rate"]),
            weight_decay=float(local["weight_decay"]),
            seed=int(seed),
        )
        rng = np.random.default_rng(int(seed))
        selected_subjects = rng.choice(
            classes,
            size=min(int(protocol["forget_identities_per_seed"]), len(classes)),
            replace=False,
        )
        for forget_subject_value in selected_subjects:
            forget_subject = int(forget_subject_value)
            forget_train = train[targets[train] == forget_subject]
            retain_train = train[targets[train] != forget_subject]
            retained_classes = classes[classes != forget_subject]
            exact, exact_runtime = train_adapter(
                features[retain_train],
                targets[retain_train],
                classes=retained_classes,
                hidden_dimension=int(local["hidden_dimension"]),
                epochs=int(local["epochs"]),
                learning_rate=float(local["learning_rate"]),
                weight_decay=float(local["weight_decay"]),
                seed=int(seed),
            )
            encoder_state = {
                name: value.detach().clone()
                for name, value in original.encoder.state_dict().items()
            }
            head_only, head_runtime = train_adapter(
                features[retain_train],
                targets[retain_train],
                classes=retained_classes,
                hidden_dimension=int(local["hidden_dimension"]),
                epochs=int(local["epochs"]),
                learning_rate=float(local["learning_rate"]),
                weight_decay=float(local["weight_decay"]),
                seed=int(seed),
                encoder_state=encoder_state,
                freeze_encoder=True,
            )
            gradient, gradient_runtime = gradient_ascent_unlearn(
                original,
                features[retain_train],
                targets[retain_train],
                features[forget_train],
                targets[forget_train],
                classes,
                protocol["gradient_ascent"],
                int(seed),
            )
            lineage, lineage_runtime, selected_fraction = lineage_guided_unlearn(
                original,
                features[retain_train],
                targets[retain_train],
                features[forget_train],
                targets[forget_train],
                classes,
                protocol["lineage_guided"],
                int(seed),
            )
            models = {
                "stale": (original, 0.0),
                "head_only": (head_only, head_runtime),
                "gradient_ascent": (gradient, gradient_runtime),
                "lineage_guided": (lineage, lineage_runtime),
                "exact_retrain": (exact, exact_runtime),
            }
            for method, (model, runtime) in models.items():
                metrics = evaluate_method(
                    model,
                    exact,
                    features,
                    targets,
                    train,
                    test,
                    forget_subject,
                    runtime=runtime,
                    exact_runtime=exact_runtime,
                    far_target=float(protocol["far_target"]),
                    seed=int(seed) + forget_subject,
                )
                trials.append(
                    {
                        "anonymous_forget_subject": forget_subject,
                        "method": method,
                        "seed": int(seed),
                        "selected_parameter_fraction": (
                            selected_fraction if method == "lineage_guided" else None
                        ),
                        **metrics,
                    }
                )
    summary: dict[str, Any] = {}
    for method in METHODS:
        rows = [row for row in trials if row["method"] == method]
        summary[method] = {}
        for metric in METRICS:
            values = np.asarray([row[metric] for row in rows], dtype=np.float64)
            interval = bootstrap_mean_interval(
                values,
                seed=int(protocol["random_seeds"][0]),
                samples=int(protocol["bootstrap_samples"]),
            )
            summary[method][metric] = {
                "ci95": list(interval),
                "mean": float(np.mean(values)),
                "std": float(np.std(values, ddof=1)),
            }
    lineage = summary["lineage_guided"]
    exact = summary["exact_retrain"]
    criteria = protocol["success_criteria"]
    success = (
        lineage["retained_verification_auc"]["mean"] - exact["retained_verification_auc"]["mean"]
        >= float(criteria["lineage_guided_retained_auc_delta_min"])
        and abs(lineage["membership_attack_auc"]["mean"] - exact["membership_attack_auc"]["mean"])
        <= float(criteria["lineage_guided_mia_auc_gap_to_exact_max"])
        and lineage["speedup_vs_exact"]["mean"] >= float(criteria["lineage_guided_speedup_min"])
    )
    payload = {
        "claim_boundary": (
            "Task-agnostic verification over a trainable local embedding encoder; "
            "the pretrained MobileFaceNet input backbone remains frozen."
        ),
        "dataset": {"images": len(features), "name": dataset.name, "subjects": len(classes)},
        "manifests": {
            "embeddings": sha256_file(Path(dataset_settings["embeddings"])),
            "protocol": sha256_file(protocol_path),
        },
        "split": split,
        "success": success,
        "summary": summary,
        "trial_count": len(trials),
        "trials": trials,
    }
    (output / "result.json").write_text(canonical_json(payload) + "\n")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", default="benchmark/task-agnostic-v2.json")
    parser.add_argument("--split", choices=("development", "evaluation"), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = run_split(Path(args.protocol), args.split, Path(args.output))
    print(
        canonical_json(
            {
                "split": args.split,
                "success": payload["success"],
                "trial_count": payload["trial_count"],
            }
        )
    )
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
