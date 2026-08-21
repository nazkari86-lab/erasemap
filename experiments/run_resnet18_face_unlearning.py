from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import torch
from sklearn.datasets import fetch_olivetti_faces
from torch import nn
from torchvision.models import ResNet18_Weights, resnet18

from erasemap.real_model import (
    build_erasure_audits,
    deterministic_subject_split,
    evaluate_models,
    train_face_model,
    training_manifest,
)


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def extract_embeddings(images: np.ndarray[Any, Any], batch_size: int = 32) -> np.ndarray[Any, Any]:
    torch.manual_seed(20260821)
    weights = ResNet18_Weights.IMAGENET1K_V1
    backbone = resnet18(weights=weights)
    backbone.fc = nn.Identity()
    backbone.eval()
    preprocess = weights.transforms()
    embeddings: list[np.ndarray[Any, Any]] = []
    with torch.inference_mode():
        for start in range(0, len(images), batch_size):
            batch = torch.from_numpy(images[start : start + batch_size]).float()
            batch = batch.unsqueeze(1).repeat(1, 3, 1, 1)
            transformed = preprocess(batch)
            embeddings.append(backbone(transformed).cpu().numpy())
    return np.concatenate(embeddings, axis=0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol", default="benchmark/real-face-resnet18-protocol-v1.json"
    )
    parser.add_argument("--data-home", default="data/real")
    parser.add_argument("--output", default="outputs/real-face-resnet18-v1")
    args = parser.parse_args()
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text())
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    dataset = fetch_olivetti_faces(
        data_home=args.data_home, download_if_missing=False, shuffle=False
    )
    images = np.asarray(dataset.images, dtype=np.float32)
    targets = np.asarray(dataset.target, dtype=np.int64)

    embedding_started = time.perf_counter()
    embeddings = extract_embeddings(images)
    embedding_seconds = time.perf_counter() - embedding_started
    if embeddings.shape != (400, 512):
        raise RuntimeError(f"unexpected embedding shape: {embeddings.shape}")

    seed = int(protocol["random_seed"])
    forget_subject = int(protocol["forget_subject"])
    split = deterministic_subject_split(
        targets,
        train_per_subject=int(protocol["train_images_per_subject"]),
        seed=seed,
    )
    retained = tuple(
        index for index in split.train_indices if int(targets[index]) != forget_subject
    )
    forgotten = tuple(
        index for index in split.train_indices if int(targets[index]) == forget_subject
    )
    pca_components = int(protocol["head"]["pca_components"])
    max_iter = int(protocol["head"]["max_iter"])
    stale_started = time.perf_counter()
    stale = train_face_model(
        embeddings[list(split.train_indices)],
        targets[list(split.train_indices)],
        pca_components=pca_components,
        max_iter=max_iter,
        seed=seed,
    )
    stale_seconds = time.perf_counter() - stale_started
    exact_started = time.perf_counter()
    exact = train_face_model(
        embeddings[list(retained)],
        targets[list(retained)],
        pca_components=pca_components,
        max_iter=max_iter,
        seed=seed,
    )
    exact_seconds = time.perf_counter() - exact_started
    comparison = evaluate_models(
        stale, exact, embeddings, targets, split, forget_subject=forget_subject
    )

    stale_path = output / "stale-head.joblib"
    exact_path = output / "exact-retrained-head.joblib"
    joblib.dump(stale, stale_path)
    joblib.dump(exact, exact_path)
    exact_hash = sha256_file(exact_path)
    original_manifest = training_manifest(
        images.reshape(400, -1), targets, list(split.train_indices)
    )
    retained_manifest = training_manifest(
        images.reshape(400, -1), targets, list(retained)
    )
    stale_audit, exact_audit = build_erasure_audits(
        subject_id=f"subject-{forget_subject}",
        original_manifest=original_manifest,
        retained_manifest=retained_manifest,
        protocol_id=str(protocol["schema_version"]),
        reference_id=exact_hash,
        now_epoch=100,
    )
    delta = comparison.exact.retained_test_accuracy - comparison.stale.retained_test_accuracy
    threshold = float(protocol["success_criteria"]["minimum_retained_accuracy_delta"])
    success = (
        not comparison.exact.deleted_class_present
        and comparison.exact.forgotten_class_probability == 0.0
        and delta >= threshold
        and stale_audit.status.value == "INCOMPLETE"
        and exact_audit.status.value == "COMPLETE"
    )
    torch_home = Path(os.environ.get("TORCH_HOME", Path.home() / ".cache" / "torch"))
    weights_path = torch_home / "hub/checkpoints/resnet18-f37072fd.pth"
    result = {
        "backbone": {
            "architecture": "ResNet-18",
            "trained_on_local_faces": False,
            "weights": "IMAGENET1K_V1",
            "weights_sha256": sha256_file(weights_path),
        },
        "claim_boundary": (
            "The frozen ImageNet backbone never trained on Olivetti identities; the deletion "
            "test covers the locally trained PCA and classification head only."
        ),
        "dataset": {"images": 400, "name": "Olivetti Faces", "subjects": 40},
        "deletion_request": {
            "forgotten_subject": forget_subject,
            "removed_training_images": len(forgotten),
            "retained_training_images": len(retained),
        },
        "erasemap": {
            "exact_retrain": {"status": exact_audit.status.value},
            "stale_model": {
                "shortest_path": list(stale_audit.shortest_path.node_ids)
                if stale_audit.shortest_path
                else None,
                "status": stale_audit.status.value,
            },
        },
        "exact_retrain": asdict(comparison.exact),
        "manifests": {
            "exact_head": exact_hash,
            "original_training": original_manifest,
            "protocol": sha256_file(protocol_path),
            "retained_training": retained_manifest,
            "stale_head": sha256_file(stale_path),
        },
        "retained_accuracy_delta": delta,
        "retained_prediction_disagreement": comparison.retained_prediction_disagreement,
        "runtime_seconds": {
            "embedding": embedding_seconds,
            "exact_retrain_head": exact_seconds,
            "initial_train_head": stale_seconds,
        },
        "stale_model": asdict(comparison.stale),
        "success": success,
    }
    (output / "result.json").write_text(canonical_json(result) + "\n")
    print(canonical_json(result))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
