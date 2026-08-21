from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import joblib
import numpy as np
from advanced_face_unlearning import extract_insightface_embeddings
from huggingface_hub import HfApi, hf_hub_download

SELECTION_DOMAIN = "erasemap-mufac-content-unseen-v1:"


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identity_key(filename: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.match(filename)
    return f"{match.group(1)}:{match.group(2)}" if match else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", default="benchmark/mufac-external-v1.json")
    parser.add_argument("--output", default="data/real/mufac-external-v1")
    parser.add_argument("--model", default="data/real/insightface/buffalo_sc/w600k_mbf.onnx")
    args = parser.parse_args()
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text())
    output = Path(args.output)
    bundle_path = output / "bundle.joblib"
    if bundle_path.exists():
        raise RuntimeError(f"refusing to overwrite external bundle: {bundle_path}")
    repository = str(protocol["dataset_repository"])
    revision = str(protocol["dataset_revision"])
    pattern = re.compile(str(protocol["identity_key_regex"]))
    files_by_identity: dict[str, list[str]] = defaultdict(list)
    api = HfApi()
    for filename in api.list_repo_files(repository, repo_type="dataset", revision=revision):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        key = identity_key(filename, pattern)
        if key is not None:
            files_by_identity[key].append(filename)
    minimum = int(protocol["minimum_images_per_identity"])
    eligible = [key for key, files in files_by_identity.items() if len(files) >= minimum]
    selected = sorted(
        eligible,
        key=lambda key: hashlib.sha256((SELECTION_DOMAIN + key).encode()).hexdigest(),
    )[: int(protocol["selection_count"])]
    if len(selected) != int(protocol["selection_count"]):
        raise RuntimeError("not enough eligible identities for frozen selection")
    output.mkdir(parents=True, exist_ok=True)
    images: list[np.ndarray[Any, Any]] = []
    targets: list[int] = []
    commitments: list[dict[str, Any]] = []
    for target, key in enumerate(selected):
        for filename in sorted(files_by_identity[key]):
            downloaded = Path(
                hf_hub_download(
                    repository,
                    filename,
                    repo_type="dataset",
                    revision=revision,
                    local_dir=output / "images",
                )
            )
            image = cv2.imread(str(downloaded), cv2.IMREAD_COLOR)
            if image is None:
                raise RuntimeError(f"failed to decode {filename}")
            normalized = cv2.resize(image, (128, 128), interpolation=cv2.INTER_AREA)
            images.append(cv2.cvtColor(normalized, cv2.COLOR_BGR2RGB))
            targets.append(target)
            commitments.append(
                {
                    "file_sha256": sha256_file(downloaded),
                    "identity_commitment": hashlib.sha256(
                        (SELECTION_DOMAIN + key).encode()
                    ).hexdigest(),
                    "repository_path": filename,
                }
            )
    embeddings = extract_insightface_embeddings(
        np.stack(images).astype(np.float32), Path(args.model)
    )
    joblib.dump(
        {
            "embeddings": embeddings,
            "targets": np.asarray(targets, dtype=np.int64),
        },
        bundle_path,
        compress=6,
    )
    manifest = {
        "bundle_sha256": sha256_file(bundle_path),
        "dataset_repository": repository,
        "dataset_revision": revision,
        "files": commitments,
        "images": len(images),
        "protocol_sha256": sha256_file(protocol_path),
        "selected_identities": len(selected),
    }
    (output / "manifest.json").write_text(canonical_json(manifest) + "\n")
    print(
        canonical_json(
            {
                "bundle": str(bundle_path),
                "identities": len(selected),
                "images": len(images),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
