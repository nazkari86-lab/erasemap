from __future__ import annotations

import argparse
import hashlib
import shutil
import urllib.request
import zipfile
from pathlib import Path

from sklearn.datasets import fetch_lfw_people, fetch_olivetti_faces

MODEL_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_sc.zip"
MODEL_ARCHIVE_SHA256 = "57d31b56b6ffa911c8a73cfc1707c73cab76efe7f13b675a05223bf42de47c72"
MODEL_SHA256 = "9cc6e4a75f0e2bf0b1aed94578f144d15175f357bdc05e815e5c4a02b319eb4f"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(f"checksum mismatch for {path}: {actual}")


def prepare_model(data_home: Path) -> Path:
    insightface = data_home / "insightface"
    archive = insightface / "buffalo_sc.zip"
    model_directory = insightface / "buffalo_sc"
    model = model_directory / "w600k_mbf.onnx"
    insightface.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        with urllib.request.urlopen(MODEL_URL) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
    verify(archive, MODEL_ARCHIVE_SHA256)
    if not model.exists():
        model_directory.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            for member in ("det_500m.onnx", "w600k_mbf.onnx"):
                with bundle.open(member) as source, (model_directory / member).open("wb") as output:
                    shutil.copyfileobj(source, output)
    verify(model, MODEL_SHA256)
    return model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-home", default="data/real")
    args = parser.parse_args()
    data_home = Path(args.data_home)
    model = prepare_model(data_home)
    olivetti = fetch_olivetti_faces(data_home=str(data_home), download_if_missing=True)
    lfw = fetch_lfw_people(
        data_home=str(data_home),
        funneled=True,
        color=True,
        resize=0.5,
        min_faces_per_person=20,
        download_if_missing=True,
    )
    print(f"model={model} sha256={sha256_file(model)}")
    print(f"olivetti_images={len(olivetti.images)}")
    print(f"lfw_images={len(lfw.images)} subjects={len(lfw.target_names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
