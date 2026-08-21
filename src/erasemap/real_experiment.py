from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]
import numpy as np
import sklearn  # type: ignore[import-untyped]
from sklearn.datasets import fetch_olivetti_faces  # type: ignore[import-untyped]

from erasemap.domain import AuditResult
from erasemap.real_model import (
    build_erasure_audits,
    deterministic_subject_split,
    evaluate_models,
    load_real_face_protocol,
    train_face_model,
    training_manifest,
)


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _git(command: str) -> str:
    result = subprocess.run(
        ["git", *command.split()], capture_output=True, check=False, text=True
    )
    return result.stdout.strip()


def _audit_payload(result: AuditResult) -> dict[str, Any]:
    return {
        "residual_paths": [list(path.node_ids) for path in result.residual_paths],
        "shortest_path": (
            list(result.shortest_path.node_ids) if result.shortest_path else None
        ),
        "status": result.status.value,
    }


def run_real_face_experiment(
    *, protocol_path: str | Path, data_home: str | Path, output_dir: str | Path
) -> dict[str, Any]:
    protocol_file = Path(protocol_path)
    data_directory = Path(data_home)
    output = Path(output_dir)
    data_directory.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)

    downloaded_before = set(data_directory.rglob("*"))
    dataset = fetch_olivetti_faces(
        data_home=str(data_directory), download_if_missing=True, shuffle=False
    )
    data_files = sorted(path for path in data_directory.rglob("*") if path.is_file())
    downloaded_now = [path for path in data_files if path not in downloaded_before]
    features = np.asarray(dataset.data, dtype=np.float64)
    targets = np.asarray(dataset.target, dtype=np.int64)
    if features.shape != (400, 4096):
        raise RuntimeError(f"unexpected Olivetti feature shape: {features.shape}")
    counts = np.bincount(targets)
    if counts.shape != (40,) or not np.all(counts == 10):
        raise RuntimeError("unexpected Olivetti identity distribution")

    protocol = load_real_face_protocol(protocol_file)
    if protocol.forget_subject not in set(int(value) for value in np.unique(targets)):
        raise RuntimeError("forgotten subject is absent from dataset")
    split = deterministic_subject_split(
        targets,
        train_per_subject=protocol.train_images_per_subject,
        seed=protocol.random_seed,
    )
    retained_train = tuple(
        index
        for index in split.train_indices
        if int(targets[index]) != protocol.forget_subject
    )
    forgotten_train = tuple(
        index
        for index in split.train_indices
        if int(targets[index]) == protocol.forget_subject
    )
    original_manifest = training_manifest(
        features, targets, list(split.train_indices)
    )
    retained_manifest = training_manifest(features, targets, list(retained_train))

    stale_started = time.perf_counter()
    stale_model = train_face_model(
        features[list(split.train_indices)],
        targets[list(split.train_indices)],
        pca_components=protocol.pca_components,
        max_iter=protocol.max_iter,
        seed=protocol.random_seed,
    )
    stale_seconds = time.perf_counter() - stale_started
    exact_started = time.perf_counter()
    exact_model = train_face_model(
        features[list(retained_train)],
        targets[list(retained_train)],
        pca_components=protocol.pca_components,
        max_iter=protocol.max_iter,
        seed=protocol.random_seed,
    )
    exact_seconds = time.perf_counter() - exact_started

    stale_path = output / "stale-model.joblib"
    exact_path = output / "exact-retrained-model.joblib"
    joblib.dump(stale_model, stale_path)
    joblib.dump(exact_model, exact_path)
    stale_hash = _sha256_file(stale_path)
    exact_hash = _sha256_file(exact_path)
    comparison = evaluate_models(
        stale_model,
        exact_model,
        features,
        targets,
        split,
        forget_subject=protocol.forget_subject,
    )
    stale_audit, exact_audit = build_erasure_audits(
        subject_id=f"subject-{protocol.forget_subject}",
        original_manifest=original_manifest,
        retained_manifest=retained_manifest,
        protocol_id=protocol.schema_version,
        reference_id=exact_hash,
        now_epoch=100,
    )
    retained_delta = (
        comparison.exact.retained_test_accuracy
        - comparison.stale.retained_test_accuracy
    )
    success = (
        not comparison.exact.deleted_class_present
        and comparison.exact.forgotten_class_probability == 0.0
        and retained_delta >= protocol.minimum_retained_accuracy_delta
        and exact_audit.status.value == "COMPLETE"
        and stale_audit.status.value == "INCOMPLETE"
    )

    protocol_hash = _sha256_file(protocol_file)
    file_manifest = [
        {
            "path": str(path.relative_to(data_directory)),
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in data_files
    ]
    result: dict[str, Any] = {
        "claim_boundary": (
            "Real public face images and a locally trained classifier; not production Face ID, "
            "not eGov validation, and not proof about unregistered copies."
        ),
        "dataset": {
            "cache_files": file_manifest,
            "downloaded_file_count_this_run": len(downloaded_now),
            "features": int(features.shape[1]),
            "images": int(features.shape[0]),
            "name": "Olivetti Faces",
            "subjects": len(np.unique(targets)),
        },
        "deletion_request": {
            "forgotten_subject": protocol.forget_subject,
            "removed_training_images": len(forgotten_train),
            "retained_training_images": len(retained_train),
        },
        "erasemap": {
            "exact_retrain": _audit_payload(exact_audit),
            "stale_model": _audit_payload(stale_audit),
        },
        "exact_retrain": asdict(comparison.exact),
        "manifests": {
            "exact_model": exact_hash,
            "original_training": original_manifest,
            "protocol": protocol_hash,
            "retained_training": retained_manifest,
            "stale_model": stale_hash,
        },
        "retained_accuracy_delta": retained_delta,
        "retained_prediction_disagreement": comparison.retained_prediction_disagreement,
        "runtime_seconds": {
            "exact_retrain": exact_seconds,
            "initial_training": stale_seconds,
        },
        "stale_model": asdict(comparison.stale),
        "success": success,
    }
    manifest = {
        "dirty_worktree": bool(_git("status --porcelain")),
        "git_revision": _git("rev-parse HEAD") or "unknown",
        "numpy_version": np.__version__,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "scikit_learn_version": sklearn.__version__,
    }
    (output / "result.json").write_text(_canonical_json(result) + "\n")
    (output / "run-manifest.json").write_text(_canonical_json(manifest) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="erasemap-real-face")
    parser.add_argument(
        "--protocol", default="benchmark/real-face-protocol-v1.json"
    )
    parser.add_argument("--data-home", default="data/real")
    parser.add_argument("--output", default="outputs/real-face-v1")
    args = parser.parse_args(argv)
    result = run_real_face_experiment(
        protocol_path=args.protocol, data_home=args.data_home, output_dir=args.output
    )
    print(_canonical_json(result))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
