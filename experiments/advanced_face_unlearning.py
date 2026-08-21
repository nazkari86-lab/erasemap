from __future__ import annotations

import argparse
import copy
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

import cv2
import joblib
import numpy as np
import onnxruntime as ort
import torch
from sklearn.datasets import fetch_lfw_people, fetch_olivetti_faces
from sklearn.metrics import roc_auc_score
from torch import nn

from erasemap.real_model import deterministic_subject_split
from erasemap.unlearning_metrics import (
    align_probabilities,
    mean_total_variation,
    membership_attack_metrics,
)


@dataclass(frozen=True, slots=True)
class DatasetView:
    images: np.ndarray[Any, Any]
    targets: np.ndarray[Any, Any]
    train_indices: tuple[int, ...]
    test_indices: tuple[int, ...]
    forget_subject: int
    name: str


@dataclass(frozen=True, slots=True)
class MethodResult:
    deleted_class_present: bool
    forgotten_label_prediction_rate: float
    forgotten_label_probability: float
    membership_attack_auc: float
    membership_attack_tpr_at_fpr_0_10: float
    retained_accuracy: float
    prediction_total_variation_to_exact: float
    encoder_parameter_l2_to_exact: float
    update_runtime_seconds: float


class FaceAdapter(nn.Module):
    def __init__(self, input_dimension: int, hidden_dimension: int, classes: int) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dimension, hidden_dimension), nn.ReLU()
        )
        self.classifier = nn.Linear(hidden_dimension, classes)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.encoder(features))


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _split_general(
    targets: np.ndarray[Any, Any], *, test_fraction: float, seed: int
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    rng = np.random.default_rng(seed)
    train: list[int] = []
    test: list[int] = []
    for label in np.unique(targets):
        indices = rng.permutation(np.flatnonzero(targets == label))
        test_count = max(1, round(len(indices) * test_fraction))
        test.extend(int(value) for value in indices[:test_count])
        train.extend(int(value) for value in indices[test_count:])
    return tuple(sorted(train)), tuple(sorted(test))


def _load_dataset(
    dataset_name: str, protocol: dict[str, Any], data_home: Path
) -> DatasetView:
    seed = int(protocol["random_seed"])
    if dataset_name == "olivetti":
        dataset = fetch_olivetti_faces(
            data_home=str(data_home), download_if_missing=False, shuffle=False
        )
        images = np.asarray(dataset.images, dtype=np.float32)
        targets = np.asarray(dataset.target, dtype=np.int64)
        split = deterministic_subject_split(
            targets,
            train_per_subject=int(protocol["train_images_per_subject"]),
            seed=seed,
        )
        return DatasetView(
            images,
            targets,
            split.train_indices,
            split.test_indices,
            int(protocol["forget_subject"]),
            "Olivetti Faces",
        )
    settings = protocol["dataset"]
    dataset = fetch_lfw_people(
        data_home=str(data_home),
        funneled=bool(settings["funneled"]),
        resize=float(settings["resize"]),
        min_faces_per_person=int(settings["min_faces_per_person"]),
        color=bool(settings["color"]),
        download_if_missing=False,
    )
    images = np.asarray(dataset.images, dtype=np.float32)
    targets = np.asarray(dataset.target, dtype=np.int64)
    counts = np.bincount(targets)
    selection = hashlib.sha256(
        f"{seed}:{','.join(str(value) for value in sorted(counts))}".encode()
    ).digest()
    forget_subject = int.from_bytes(selection[:8], "big") % len(counts)
    train, test = _split_general(
        targets,
        test_fraction=float(protocol["test_fraction_per_identity"]),
        seed=seed,
    )
    return DatasetView(
        images,
        targets,
        train,
        test,
        forget_subject,
        "Labeled Faces in the Wild",
    )


def _image_to_bgr(image: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    scaled = image
    if float(np.max(scaled)) <= 1.0:
        scaled = scaled * 255.0
    unsigned = np.clip(scaled, 0, 255).astype(np.uint8)
    if unsigned.ndim == 2:
        return cv2.cvtColor(unsigned, cv2.COLOR_GRAY2BGR)
    return cv2.cvtColor(unsigned, cv2.COLOR_RGB2BGR)


def extract_insightface_embeddings(
    images: np.ndarray[Any, Any], model_path: Path, batch_size: int = 64
) -> np.ndarray[Any, Any]:
    options = ort.SessionOptions()
    options.log_severity_level = 3
    session = ort.InferenceSession(
        str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
    )
    input_name = session.get_inputs()[0].name
    results: list[np.ndarray[Any, Any]] = []
    for start in range(0, len(images), batch_size):
        prepared = [_image_to_bgr(image) for image in images[start : start + batch_size]]
        blob = cv2.dnn.blobFromImages(
            prepared,
            scalefactor=1 / 127.5,
            size=(112, 112),
            mean=(127.5, 127.5, 127.5),
            swapRB=True,
        )
        results.append(np.asarray(session.run(None, {input_name: blob})[0]))
    embeddings = np.concatenate(results, axis=0).astype(np.float32)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    return embeddings / np.maximum(norms, 1e-12)


def _label_map(classes: np.ndarray[Any, Any]) -> dict[int, int]:
    return {int(label): index for index, label in enumerate(classes)}


def _mapped_targets(
    targets: np.ndarray[Any, Any], classes: np.ndarray[Any, Any]
) -> torch.Tensor:
    locations = _label_map(classes)
    return torch.tensor([locations[int(label)] for label in targets], dtype=torch.long)


def train_adapter(
    features: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    *,
    classes: np.ndarray[Any, Any],
    hidden_dimension: int,
    epochs: int,
    learning_rate: float,
    weight_decay: float,
    seed: int,
    encoder_state: dict[str, torch.Tensor] | None = None,
    freeze_encoder: bool = False,
) -> tuple[FaceAdapter, float]:
    torch.manual_seed(seed)
    model = FaceAdapter(features.shape[1], hidden_dimension, len(classes))
    if encoder_state is not None:
        model.encoder.load_state_dict(encoder_state)
    for parameter in model.encoder.parameters():
        parameter.requires_grad = not freeze_encoder
    optimizer = torch.optim.Adam(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=learning_rate,
        weight_decay=weight_decay,
    )
    tensor_features = torch.from_numpy(features).float()
    tensor_targets = _mapped_targets(targets, classes)
    started = time.perf_counter()
    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        loss = nn.functional.cross_entropy(model(tensor_features), tensor_targets)
        loss.backward()
        optimizer.step()
    return model.eval(), time.perf_counter() - started


def gradient_ascent_unlearn(
    original: FaceAdapter,
    retain_features: np.ndarray[Any, Any],
    retain_targets: np.ndarray[Any, Any],
    forget_features: np.ndarray[Any, Any],
    forget_targets: np.ndarray[Any, Any],
    classes: np.ndarray[Any, Any],
    settings: dict[str, Any],
    seed: int,
) -> tuple[FaceAdapter, float]:
    torch.manual_seed(seed)
    model = copy.deepcopy(original).train()
    reference = {
        name: parameter.detach().clone() for name, parameter in model.named_parameters()
    }
    optimizer = torch.optim.Adam(model.parameters(), lr=float(settings["learning_rate"]))
    retain_x = torch.from_numpy(retain_features).float()
    retain_y = _mapped_targets(retain_targets, classes)
    forget_x = torch.from_numpy(forget_features).float()
    forget_y = _mapped_targets(forget_targets, classes)
    generator = torch.Generator().manual_seed(seed)
    batch_size = min(int(settings["retain_batch_size"]), len(retain_x))
    started = time.perf_counter()
    for _ in range(int(settings["steps"])):
        selection = torch.randperm(len(retain_x), generator=generator)[:batch_size]
        optimizer.zero_grad()
        retain_loss = nn.functional.cross_entropy(
            model(retain_x[selection]), retain_y[selection]
        )
        forget_loss = nn.functional.cross_entropy(model(forget_x), forget_y)
        drift = sum(
            torch.sum((parameter - reference[name]) ** 2)
            for name, parameter in model.named_parameters()
        )
        loss = (
            retain_loss
            - float(settings["forget_loss_weight"]) * forget_loss
            + float(settings["parameter_drift_weight"]) * drift
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        optimizer.step()
    return model.eval(), time.perf_counter() - started


def _probabilities(model: FaceAdapter, features: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    with torch.inference_mode():
        return torch.softmax(model(torch.from_numpy(features).float()), dim=1).numpy()


def _encoder_distance(left: FaceAdapter, right: FaceAdapter) -> float:
    squared = 0.0
    for left_parameter, right_parameter in zip(
        left.encoder.parameters(), right.encoder.parameters(), strict=True
    ):
        squared += float(
            torch.sum((left_parameter.detach() - right_parameter.detach()) ** 2)
        )
    return squared**0.5


def _verification_auc(
    embeddings: np.ndarray[Any, Any], targets: np.ndarray[Any, Any], seed: int
) -> float:
    rng = np.random.default_rng(seed)
    positive: list[float] = []
    negative: list[float] = []
    for label in np.unique(targets):
        indices = np.flatnonzero(targets == label)
        for left, right in pairwise(indices):
            positive.append(float(np.dot(embeddings[left], embeddings[right])))
    for _ in range(len(positive)):
        left = int(rng.integers(len(targets)))
        candidates = np.flatnonzero(targets != targets[left])
        right = int(rng.choice(candidates))
        negative.append(float(np.dot(embeddings[left], embeddings[right])))
    labels = np.concatenate((np.ones(len(positive)), np.zeros(len(negative))))
    return float(roc_auc_score(labels, np.asarray([*positive, *negative])))


def _evaluate(
    model: FaceAdapter,
    classes: np.ndarray[Any, Any],
    exact_model: FaceAdapter,
    exact_classes: np.ndarray[Any, Any],
    all_classes: np.ndarray[Any, Any],
    embeddings: np.ndarray[Any, Any],
    dataset: DatasetView,
    runtime: float,
) -> MethodResult:
    train = np.asarray(dataset.train_indices)
    test = np.asarray(dataset.test_indices)
    forget_train = train[dataset.targets[train] == dataset.forget_subject]
    forget_test = test[dataset.targets[test] == dataset.forget_subject]
    retain_test = test[dataset.targets[test] != dataset.forget_subject]
    model_forget_train = align_probabilities(
        _probabilities(model, embeddings[forget_train]),
        model_classes=classes,
        all_classes=all_classes,
    )
    model_forget_test = align_probabilities(
        _probabilities(model, embeddings[forget_test]),
        model_classes=classes,
        all_classes=all_classes,
    )
    model_retain = align_probabilities(
        _probabilities(model, embeddings[retain_test]),
        model_classes=classes,
        all_classes=all_classes,
    )
    exact_retain = align_probabilities(
        _probabilities(exact_model, embeddings[retain_test]),
        model_classes=exact_classes,
        all_classes=all_classes,
    )
    forgotten_column = int(np.flatnonzero(all_classes == dataset.forget_subject)[0])
    attack = membership_attack_metrics(
        member_scores=model_forget_train[:, forgotten_column],
        nonmember_scores=model_forget_test[:, forgotten_column],
        target_fpr=0.1,
    )
    predictions = all_classes[np.argmax(model_retain, axis=1)]
    return MethodResult(
        deleted_class_present=bool(np.any(classes == dataset.forget_subject)),
        forgotten_label_prediction_rate=float(
            np.mean(
                all_classes[np.argmax(model_forget_test, axis=1)]
                == dataset.forget_subject
            )
        ),
        forgotten_label_probability=float(
            np.mean(model_forget_test[:, forgotten_column])
        ),
        membership_attack_auc=attack.auc,
        membership_attack_tpr_at_fpr_0_10=attack.tpr_at_target_fpr,
        retained_accuracy=float(np.mean(predictions == dataset.targets[retain_test])),
        prediction_total_variation_to_exact=mean_total_variation(
            model_retain, exact_retain
        ),
        encoder_parameter_l2_to_exact=_encoder_distance(model, exact_model),
        update_runtime_seconds=runtime,
    )


def run_experiment(
    *,
    dataset_name: str,
    protocol_path: Path,
    data_home: Path,
    model_path: Path,
    output: Path,
) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text())
    dataset = _load_dataset(dataset_name, protocol, data_home)
    embedding_started = time.perf_counter()
    embeddings = extract_insightface_embeddings(dataset.images, model_path)
    embedding_runtime = time.perf_counter() - embedding_started
    train = np.asarray(dataset.train_indices)
    forget_train = train[dataset.targets[train] == dataset.forget_subject]
    retain_train = train[dataset.targets[train] != dataset.forget_subject]
    all_classes = np.unique(dataset.targets)
    retained_classes = all_classes[all_classes != dataset.forget_subject]
    if dataset_name == "olivetti":
        local = protocol["local_model"]
        approximate = protocol["approximate_unlearning"]
        hidden = 128
    else:
        contract = protocol["method_contract"]
        local = {
            "epochs": contract["local_epochs"],
            "learning_rate": contract["local_learning_rate"],
            "weight_decay": contract["local_weight_decay"],
        }
        approximate = {
            "forget_loss_weight": contract["approximate_forget_loss_weight"],
            "learning_rate": contract["approximate_learning_rate"],
            "parameter_drift_weight": contract[
                "approximate_parameter_drift_weight"
            ],
            "retain_batch_size": 128,
            "steps": contract["approximate_steps"],
        }
        hidden = int(contract["local_hidden_dimension"])
    seed = int(protocol["random_seed"])
    original, original_runtime = train_adapter(
        embeddings[train],
        dataset.targets[train],
        classes=all_classes,
        hidden_dimension=hidden,
        epochs=int(local["epochs"]),
        learning_rate=float(local["learning_rate"]),
        weight_decay=float(local["weight_decay"]),
        seed=seed,
    )
    exact, exact_runtime = train_adapter(
        embeddings[retain_train],
        dataset.targets[retain_train],
        classes=retained_classes,
        hidden_dimension=hidden,
        epochs=int(local["epochs"]),
        learning_rate=float(local["learning_rate"]),
        weight_decay=float(local["weight_decay"]),
        seed=seed,
    )
    encoder_state = {
        name: value.detach().clone() for name, value in original.encoder.state_dict().items()
    }
    head_only, head_runtime = train_adapter(
        embeddings[retain_train],
        dataset.targets[retain_train],
        classes=retained_classes,
        hidden_dimension=hidden,
        epochs=int(local["epochs"]),
        learning_rate=float(local["learning_rate"]),
        weight_decay=float(local["weight_decay"]),
        seed=seed,
        encoder_state=encoder_state,
        freeze_encoder=True,
    )
    approximate_model, approximate_runtime = gradient_ascent_unlearn(
        original,
        embeddings[retain_train],
        dataset.targets[retain_train],
        embeddings[forget_train],
        dataset.targets[forget_train],
        all_classes,
        approximate,
        seed,
    )
    models = {
        "stale": (original, all_classes, 0.0),
        "head_only": (head_only, retained_classes, head_runtime),
        "gradient_ascent": (
            approximate_model,
            all_classes,
            approximate_runtime,
        ),
        "exact_retrain": (exact, retained_classes, exact_runtime),
    }
    results = {
        name: asdict(
            _evaluate(
                model,
                classes,
                exact,
                retained_classes,
                all_classes,
                embeddings,
                dataset,
                runtime,
            )
        )
        for name, (model, classes, runtime) in models.items()
    }
    criteria = protocol["success_criteria"]
    exact_result = results["exact_retrain"]
    stale_result = results["stale"]
    success = (
        float(exact_result["forgotten_label_probability"])
        <= float(criteria["exact_forgotten_label_probability_max"])
        and float(exact_result["membership_attack_auc"])
        <= float(criteria["exact_membership_auc_max"])
        and float(exact_result["retained_accuracy"])
        - float(stale_result["retained_accuracy"])
        >= float(
            criteria.get(
                "minimum_exact_retained_accuracy_delta",
                criteria.get("minimum_retained_accuracy_delta"),
            )
        )
    )
    output.mkdir(parents=True, exist_ok=True)
    checkpoint_hashes: dict[str, str] = {}
    for name, (model, classes, _) in models.items():
        checkpoint = output / f"{name}.pt"
        torch.save(
            {"classes": classes.tolist(), "state_dict": model.state_dict()}, checkpoint
        )
        checkpoint_hashes[name] = sha256_file(checkpoint)
    cache_path = output / "embeddings.joblib"
    joblib.dump(embeddings, cache_path, compress=6)
    payload = {
        "claim_boundary": (
            "Research-only InsightFace weights; local adapter unlearning, not production "
            "Face ID/eGov validation or deletion from the pretrained backbone."
        ),
        "dataset": {
            "anonymous_forget_subject": dataset.forget_subject,
            "images": len(dataset.images),
            "name": dataset.name,
            "subjects": len(all_classes),
            "test_images": len(dataset.test_indices),
            "train_images": len(dataset.train_indices),
        },
        "embedding": {
            "model_sha256": sha256_file(model_path),
            "runtime_seconds": embedding_runtime,
            "verification_auc": _verification_auc(
                embeddings, dataset.targets, seed
            ),
        },
        "manifests": {
            "checkpoints": checkpoint_hashes,
            "embeddings": sha256_file(cache_path),
            "protocol": sha256_file(protocol_path),
        },
        "methods": results,
        "original_training_runtime_seconds": original_runtime,
        "success": success,
    }
    (output / "result.json").write_text(canonical_json(payload) + "\n")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=("olivetti", "lfw"), required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--data-home", default="data/real")
    parser.add_argument(
        "--model", default="data/real/insightface/buffalo_sc/w600k_mbf.onnx"
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = run_experiment(
        dataset_name=args.dataset,
        protocol_path=Path(args.protocol),
        data_home=Path(args.data_home),
        model_path=Path(args.model),
        output=Path(args.output),
    )
    print(canonical_json(payload))
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
