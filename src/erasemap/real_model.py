from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.decomposition import PCA  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from erasemap.audit import audit_subject
from erasemap.domain import (
    Artifact,
    ArtifactState,
    ArtifactType,
    AuditResult,
    Edge,
    EdgeType,
    ErasureGraph,
    Evidence,
    EvidenceKind,
)


@dataclass(frozen=True, slots=True)
class RealFaceProtocol:
    schema_version: str
    random_seed: int
    forget_subject: int
    train_images_per_subject: int
    test_images_per_subject: int
    pca_components: int
    max_iter: int
    minimum_retained_accuracy_delta: float

    def __post_init__(self) -> None:
        if self.schema_version != "erasemap-real-face-v1":
            raise ValueError("unsupported real-face protocol")
        if self.train_images_per_subject + self.test_images_per_subject != 10:
            raise ValueError("Olivetti protocol must allocate all ten images per subject")
        if self.train_images_per_subject < 2 or self.test_images_per_subject < 1:
            raise ValueError("both training and test splits are required")
        if self.random_seed < 0 or self.forget_subject < 0:
            raise ValueError("seed and forgotten subject cannot be negative")
        if self.pca_components < 1 or self.max_iter < 1:
            raise ValueError("model parameters must be positive")


@dataclass(frozen=True, slots=True)
class SubjectSplit:
    train_indices: tuple[int, ...]
    test_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ModelMetrics:
    deleted_class_present: bool
    forgotten_class_probability: float
    retained_test_accuracy: float


@dataclass(frozen=True, slots=True)
class ModelComparison:
    stale: ModelMetrics
    exact: ModelMetrics
    retained_prediction_disagreement: float


def load_real_face_protocol(path: str | Path) -> RealFaceProtocol:
    raw = json.loads(Path(path).read_text())
    model = raw["model"]
    success = raw["success_criteria"]
    return RealFaceProtocol(
        schema_version=str(raw["schema_version"]),
        random_seed=int(raw["random_seed"]),
        forget_subject=int(raw["forget_subject"]),
        train_images_per_subject=int(raw["train_images_per_subject"]),
        test_images_per_subject=int(raw["test_images_per_subject"]),
        pca_components=int(model["pca_components"]),
        max_iter=int(model["max_iter"]),
        minimum_retained_accuracy_delta=float(
            success["minimum_retained_accuracy_delta"]
        ),
    )


def deterministic_subject_split(
    targets: np.ndarray[Any, Any], *, train_per_subject: int, seed: int
) -> SubjectSplit:
    if train_per_subject < 1:
        raise ValueError("train_per_subject must be positive")
    rng = np.random.default_rng(seed)
    train: list[int] = []
    test: list[int] = []
    for subject in np.unique(targets):
        indices = np.flatnonzero(targets == subject)
        if train_per_subject >= len(indices):
            raise ValueError("each subject needs held-out images")
        shuffled = rng.permutation(indices)
        train.extend(int(value) for value in shuffled[:train_per_subject])
        test.extend(int(value) for value in shuffled[train_per_subject:])
    return SubjectSplit(tuple(sorted(train)), tuple(sorted(test)))


def train_face_model(
    features: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    *,
    pca_components: int,
    max_iter: int,
    seed: int,
) -> Pipeline:
    components = min(pca_components, features.shape[0] - 1, features.shape[1])
    if components < 1 or len(np.unique(targets)) < 2:
        raise ValueError("training data is too small")
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "pca",
                PCA(
                    n_components=components,
                    whiten=True,
                    svd_solver="randomized",
                    random_state=seed,
                ),
            ),
            (
                "classifier",
                LogisticRegression(max_iter=max_iter, random_state=seed, solver="lbfgs"),
            ),
        ]
    )
    return model.fit(features, targets)


def _model_classes(model: Pipeline) -> np.ndarray[Any, Any]:
    classifier = model.named_steps["classifier"]
    return np.asarray(classifier.classes_)


def _forgotten_probability(
    model: Pipeline,
    features: np.ndarray[Any, Any],
    forget_subject: int,
) -> float:
    classes = _model_classes(model)
    locations = np.flatnonzero(classes == forget_subject)
    if not len(locations):
        return 0.0
    probabilities = model.predict_proba(features)
    return float(np.mean(probabilities[:, int(locations[0])]))


def evaluate_models(
    stale_model: Pipeline,
    exact_model: Pipeline,
    features: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    split: SubjectSplit,
    *,
    forget_subject: int,
) -> ModelComparison:
    test = np.asarray(split.test_indices)
    forgotten = test[targets[test] == forget_subject]
    retained = test[targets[test] != forget_subject]
    if not len(forgotten) or not len(retained):
        raise ValueError("test split must include forgotten and retained subjects")

    stale_predictions = stale_model.predict(features[retained])
    exact_predictions = exact_model.predict(features[retained])
    stale_classes = _model_classes(stale_model)
    exact_classes = _model_classes(exact_model)
    return ModelComparison(
        stale=ModelMetrics(
            deleted_class_present=bool(np.any(stale_classes == forget_subject)),
            forgotten_class_probability=_forgotten_probability(
                stale_model, features[forgotten], forget_subject
            ),
            retained_test_accuracy=float(np.mean(stale_predictions == targets[retained])),
        ),
        exact=ModelMetrics(
            deleted_class_present=bool(np.any(exact_classes == forget_subject)),
            forgotten_class_probability=_forgotten_probability(
                exact_model, features[forgotten], forget_subject
            ),
            retained_test_accuracy=float(np.mean(exact_predictions == targets[retained])),
        ),
        retained_prediction_disagreement=float(
            np.mean(stale_predictions != exact_predictions)
        ),
    )


def training_manifest(
    features: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    indices: tuple[int, ...] | list[int],
) -> str:
    digest = hashlib.sha256()
    for index in sorted(indices):
        digest.update(int(index).to_bytes(4, "big"))
        digest.update(int(targets[index]).to_bytes(4, "big"))
        digest.update(np.asarray(features[index], dtype="<f4").tobytes())
    return "sha256:" + digest.hexdigest()


def build_erasure_audits(
    *,
    subject_id: str,
    original_manifest: str,
    retained_manifest: str,
    protocol_id: str,
    reference_id: str,
    now_epoch: int,
) -> tuple[AuditResult, AuditResult]:
    source = Artifact(
        "source",
        subject_id,
        ArtifactType.SOURCE_RECORD,
        ArtifactState.ERASED,
        commitment=original_manifest,
    )
    template = Artifact(
        "template",
        subject_id,
        ArtifactType.BIOMETRIC_TEMPLATE,
        ArtifactState.ERASED,
        commitment=retained_manifest,
    )
    stale_model = Artifact(
        "model",
        subject_id,
        ArtifactType.MODEL_INFLUENCE,
        ArtifactState.ACTIVE,
        active_sink=True,
        commitment=reference_id,
    )
    exact_model = Artifact(
        "model",
        subject_id,
        ArtifactType.MODEL_INFLUENCE,
        ArtifactState.ERASED,
        commitment=reference_id,
    )
    edges = (
        Edge("source", "template", EdgeType.DERIVED_INTO),
        Edge("template", "model", EdgeType.USED_TO_TRAIN),
    )
    common_evidence = {
        "source": Evidence(
            "evidence-source",
            "source",
            EvidenceKind.ABSENCE_CHECK,
            commitment=original_manifest,
            observed_absent=True,
            issued_epoch=now_epoch,
        ),
        "template": Evidence(
            "evidence-template",
            "template",
            EvidenceKind.ABSENCE_CHECK,
            commitment=retained_manifest,
            observed_absent=True,
            issued_epoch=now_epoch,
        ),
    }
    stale_graph = ErasureGraph(
        {"source": source, "template": template, "model": stale_model}, edges
    )
    exact_graph = ErasureGraph(
        {"source": source, "template": template, "model": exact_model}, edges
    )
    exact_evidence = {
        **common_evidence,
        "model": Evidence(
            "evidence-model",
            "model",
            EvidenceKind.MODEL_AUDIT,
            issued_epoch=now_epoch,
            metadata=(
                ("pass", "true"),
                ("protocol_id", protocol_id),
                ("reference_id", reference_id),
            ),
        ),
    }
    return (
        audit_subject(stale_graph, common_evidence, subject_id, now_epoch),
        audit_subject(exact_graph, exact_evidence, subject_id, now_epoch),
    )
