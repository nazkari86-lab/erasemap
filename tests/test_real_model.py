import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from erasemap.domain import AuditStatus
from erasemap.real_experiment import run_real_face_experiment
from erasemap.real_model import (
    RealFaceProtocol,
    build_erasure_audits,
    deterministic_subject_split,
    evaluate_models,
    train_face_model,
)


def tiny_faces() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(4)
    targets = np.repeat(np.arange(4), 5)
    features = rng.normal(0, 0.02, size=(20, 8))
    features += np.eye(4, 8)[targets] * 2
    return features, targets


def test_subject_split_is_deterministic_and_stratified() -> None:
    _, targets = tiny_faces()

    left = deterministic_subject_split(targets, train_per_subject=3, seed=9)
    right = deterministic_subject_split(targets, train_per_subject=3, seed=9)

    assert left == right
    assert len(left.train_indices) == 12
    assert len(left.test_indices) == 8
    assert set(targets[list(left.train_indices)]) == {0, 1, 2, 3}


def test_exact_retraining_removes_subject_class() -> None:
    features, targets = tiny_faces()
    split = deterministic_subject_split(targets, train_per_subject=3, seed=9)
    original = train_face_model(
        features[list(split.train_indices)],
        targets[list(split.train_indices)],
        pca_components=3,
        max_iter=500,
        seed=9,
    )
    keep = [index for index in split.train_indices if targets[index] != 0]
    exact = train_face_model(
        features[keep], targets[keep], pca_components=3, max_iter=500, seed=9
    )

    metrics = evaluate_models(
        original,
        exact,
        features,
        targets,
        split,
        forget_subject=0,
    )

    assert metrics.stale.deleted_class_present
    assert not metrics.exact.deleted_class_present
    assert metrics.exact.forgotten_class_probability == 0.0


def test_erasemap_rejects_stale_model_and_accepts_exact_retrain() -> None:
    stale, exact = build_erasure_audits(
        subject_id="subject-0",
        original_manifest="sha256:original",
        retained_manifest="sha256:retained",
        protocol_id="real-face-v1",
        reference_id="sha256:model",
        now_epoch=100,
    )

    assert stale.status is AuditStatus.INCOMPLETE
    assert stale.shortest_path is not None
    assert stale.shortest_path.node_ids[-1] == "model"
    assert exact.status is AuditStatus.COMPLETE


def test_protocol_rejects_inconsistent_split() -> None:
    try:
        RealFaceProtocol(
            schema_version="erasemap-real-face-v1",
            random_seed=1,
            forget_subject=0,
            train_images_per_subject=8,
            test_images_per_subject=3,
            pca_components=3,
            max_iter=100,
            minimum_retained_accuracy_delta=-0.1,
        )
    except ValueError as error:
        assert "ten images" in str(error)
    else:
        raise AssertionError("invalid split should be rejected")


def test_real_experiment_writes_auditable_artifacts(
    tmp_path: Path, monkeypatch: object
) -> None:
    rng = np.random.default_rng(12)
    targets = np.repeat(np.arange(40), 10)
    features = rng.normal(0, 0.001, size=(400, 4096)).astype(np.float32)
    features[:, :40] += np.eye(40, dtype=np.float32)[targets] * 2
    dataset = SimpleNamespace(data=features, target=targets)
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "erasemap.real_experiment.fetch_olivetti_faces", lambda **_: dataset
    )
    data_home = tmp_path / "data"
    data_home.mkdir()
    (data_home / "fixture.bin").write_bytes(b"fixture")
    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "forget_subject": 0,
                "model": {"max_iter": 200, "pca_components": 3},
                "random_seed": 5,
                "schema_version": "erasemap-real-face-v1",
                "success_criteria": {"minimum_retained_accuracy_delta": -0.1},
                "test_images_per_subject": 3,
                "train_images_per_subject": 7,
            }
        )
    )
    output = tmp_path / "output"

    result = run_real_face_experiment(
        protocol_path=protocol, data_home=data_home, output_dir=output
    )

    assert result["success"]
    assert result["erasemap"]["stale_model"]["status"] == "INCOMPLETE"
    assert result["erasemap"]["exact_retrain"]["status"] == "COMPLETE"
    assert (output / "result.json").is_file()
    assert (output / "run-manifest.json").is_file()
