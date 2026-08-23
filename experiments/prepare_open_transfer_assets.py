from __future__ import annotations

import argparse
import io
import json
import ssl
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import loadmat  # type: ignore[import-untyped]

from erasemap.open_transfer_evidence import canonical_json, sha256_bytes, sha256_file


def _verified_https_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    for candidate in (
        Path("/etc/ssl/cert.pem"),
        Path("/opt/homebrew/etc/ca-certificates/cert.pem"),
    ):
        if candidate.is_file():
            context.load_verify_locations(cafile=str(candidate))
    return context


@dataclass(frozen=True, slots=True)
class VectorAsset:
    development_vectors: np.ndarray[Any, Any]
    development_subject_ids: np.ndarray[Any, Any]
    confirmatory_vectors: np.ndarray[Any, Any]
    confirmatory_subject_ids: np.ndarray[Any, Any]

    def arrays(self) -> dict[str, np.ndarray[Any, Any]]:
        return {
            "confirmatory_subject_ids": self.confirmatory_subject_ids,
            "confirmatory_vectors": self.confirmatory_vectors,
            "development_subject_ids": self.development_subject_ids,
            "development_vectors": self.development_vectors,
        }


def build_vector_asset(
    faces: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    *,
    development_subject_ids: tuple[int, ...],
    confirmatory_subject_ids: tuple[int, ...],
    sample_offset: int,
) -> VectorAsset:
    matrix = np.asarray(faces, dtype=np.float32)
    labels = np.asarray(targets, dtype=np.int64).reshape(-1)
    if matrix.ndim != 2 or matrix.shape[0] != labels.shape[0] or matrix.shape[1] != 4096:
        raise ValueError("face data must have shape (samples, 4096) with aligned labels")
    if set(development_subject_ids) & set(confirmatory_subject_ids):
        raise ValueError("development and confirmatory subjects must be disjoint")
    if sample_offset < 0:
        raise ValueError("sample offset cannot be negative")

    def select(subject_ids: tuple[int, ...]) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        rows: list[np.ndarray[Any, Any]] = []
        for subject_id in subject_ids:
            indices = np.flatnonzero(labels == subject_id)
            if sample_offset >= len(indices):
                raise ValueError(f"subject {subject_id} does not have the frozen sample offset")
            rows.append(matrix[int(indices[sample_offset])])
        return np.stack(rows).astype(np.float32), np.asarray(subject_ids, dtype=np.int64)

    development_vectors, development_ids = select(development_subject_ids)
    confirmatory_vectors, confirmatory_ids = select(confirmatory_subject_ids)
    return VectorAsset(
        development_vectors,
        development_ids,
        confirmatory_vectors,
        confirmatory_ids,
    )


def _npy_bytes(array: np.ndarray[Any, Any]) -> bytes:
    stream = io.BytesIO()
    np.lib.format.write_array(stream, np.asarray(array), allow_pickle=False)
    return stream.getvalue()


def write_deterministic_npz(
    path: Path, arrays: dict[str, np.ndarray[Any, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name in sorted(arrays):
            if not name or "/" in name or "\\" in name:
                raise ValueError("invalid deterministic NPZ member name")
            info = zipfile.ZipInfo(f"{name}.npy", (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, _npy_bytes(arrays[name]))


def _load_olivetti(raw_path: Path) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    payload = loadmat(file_name=raw_path)
    if "faces" not in payload:
        raise ValueError("Olivetti source does not contain the faces matrix")
    faces = np.float32(payload["faces"].T.copy())
    faces -= faces.min()
    maximum = float(faces.max())
    if maximum <= 0:
        raise ValueError("Olivetti source has no positive pixel range")
    faces /= maximum
    vectors = faces.reshape((400, 64, 64)).transpose(0, 2, 1).reshape(400, -1)
    targets = np.asarray([index // 10 for index in range(400)], dtype=np.int64)
    return vectors, targets


def prepare_assets(
    protocol_path: Path, output: Path, *, allow_overwrite: bool = False
) -> dict[str, object]:
    if output.exists() and any(output.iterdir()) and not allow_overwrite:
        raise FileExistsError(f"asset output is not empty: {output}")
    protocol = json.loads(protocol_path.read_text())
    source = protocol["public_inputs"][0]
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="erasemap-open-transfer-source-") as directory:
        raw_path = Path(directory) / str(source["source_filename"])
        with urllib.request.urlopen(
            str(source["source_url"]), timeout=60, context=_verified_https_context()
        ) as response:
            raw_path.write_bytes(response.read())
        observed_source_hash = sha256_file(raw_path)
        if observed_source_hash != source["source_sha256"]:
            raise ValueError("public input checksum drift")
        vectors, targets = _load_olivetti(raw_path)
    asset = build_vector_asset(
        vectors,
        targets,
        development_subject_ids=tuple(int(item) for item in source["development_subject_ids"]),
        confirmatory_subject_ids=tuple(int(item) for item in source["confirmatory_subject_ids"]),
        sample_offset=int(source["sample_offset_within_subject"]),
    )
    asset_path = output / "olivetti-transfer-v1.npz"
    write_deterministic_npz(asset_path, asset.arrays())
    provenance: dict[str, object] = {
        "schema_version": "erasemap-open-transfer-asset-v1",
        "source_url": source["source_url"],
        "source_filename": source["source_filename"],
        "source_sha256": observed_source_hash,
        "terms_pointer": source["terms_pointer"],
        "preprocessing": source["preprocessing"],
        "development_subject_ids": source["development_subject_ids"],
        "confirmatory_subject_ids": source["confirmatory_subject_ids"],
        "sample_offset_within_subject": source["sample_offset_within_subject"],
        "vector_dimension": int(asset.confirmatory_vectors.shape[1]),
        "asset_sha256": sha256_file(asset_path),
        "array_payload_sha256": sha256_bytes(
            b"".join(_npy_bytes(asset.arrays()[key]) for key in sorted(asset.arrays()))
        ),
    }
    (output / "PROVENANCE.json").write_bytes(canonical_json(provenance) + b"\n")
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=Path("benchmark/open-transfer-v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-overwrite", action="store_true")
    args = parser.parse_args()
    result = prepare_assets(args.protocol, args.output, allow_overwrite=args.allow_overwrite)
    print(canonical_json(result).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
