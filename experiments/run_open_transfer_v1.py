from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from erasemap.open_transfer import TransferCaseRecord, summarize_transfer
from erasemap.open_transfer_evidence import canonical_json, sha256_file
from experiments.open_transfer_live import run_live_families
from experiments.prepare_open_transfer_assets import prepare_assets


def _load_protocol(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("open-transfer protocol must be a JSON object")
    if payload.get("schema_version") != "erasemap-open-transfer-v1":
        raise ValueError("unexpected open-transfer protocol schema")
    return cast(dict[str, Any], payload)


def core_sha256(protocol: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for raw_path in protocol["core_files"]:
        path = Path(str(raw_path))
        if not path.is_file():
            raise FileNotFoundError(f"frozen core file is missing: {path}")
        digest.update(str(path).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _git_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, check=True, text=True
    )
    return result.stdout.strip()


def _write_atomic(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def write_result_bundle(
    records: Sequence[TransferCaseRecord],
    protocol: dict[str, Any],
    protocol_path: Path,
    output: Path,
    *,
    support_artifacts: Sequence[Path],
    run_kind: str = "LIVE_STOCK_SERVICES",
) -> dict[str, Any]:
    result_path = output / "result.json"
    trials_path = output / "trials.jsonl"
    provenance_path = output / "PROVENANCE.json"
    if any(path.exists() for path in (result_path, trials_path, provenance_path)):
        raise FileExistsError(f"result output already exists: {output}")
    output.mkdir(parents=True, exist_ok=True)
    ordered = tuple(sorted(records, key=lambda item: item.case_id))
    trials_payload = b"".join(canonical_json(item.payload()) + b"\n" for item in ordered)
    _write_atomic(trials_path, trials_payload)
    selected_core_hash = core_sha256(protocol)
    summary = summarize_transfer(ordered, protocol, selected_core_hash)
    result: dict[str, Any] = {
        "schema_version": "erasemap-open-transfer-result-v1",
        "protocol_schema_version": protocol["schema_version"],
        "protocol_sha256": sha256_file(protocol_path),
        "core_sha256": selected_core_hash,
        "run_kind": run_kind,
        "summary": summary.payload(),
        "claim_boundary": protocol["claim_boundary"],
    }
    _write_atomic(result_path, canonical_json(result) + b"\n")
    artifact_paths = [trials_path, result_path, *support_artifacts]
    artifact_hashes: dict[str, str] = {}
    for path in artifact_paths:
        resolved = path.resolve()
        if not resolved.is_relative_to(output.resolve()):
            raise ValueError(f"support artifact is outside the result root: {path}")
        relative = str(resolved.relative_to(output.resolve()))
        if relative in artifact_hashes:
            raise ValueError(f"duplicate support artifact: {relative}")
        artifact_hashes[relative] = sha256_file(resolved)
    provenance: dict[str, Any] = {
        "schema_version": "erasemap-open-transfer-provenance-v1",
        "git_revision": _git_revision(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "protocol_sha256": result["protocol_sha256"],
        "core_sha256": selected_core_hash,
        "artifacts": dict(sorted(artifact_hashes.items())),
    }
    _write_atomic(provenance_path, canonical_json(provenance) + b"\n")
    return result


def _write_smoke_bundle(
    records: Sequence[TransferCaseRecord],
    protocol: dict[str, Any],
    protocol_path: Path,
    output: Path,
    *,
    support_artifacts: Sequence[Path],
) -> dict[str, Any]:
    if len(records) != len(protocol["families"]):
        raise ValueError("smoke run must contain one case per family")
    smoke_path = output / "smoke.json"
    if smoke_path.exists():
        raise FileExistsError(f"smoke output already exists: {smoke_path}")
    artifact_hashes = {
        str(path.resolve().relative_to(output.resolve())): sha256_file(path)
        for path in support_artifacts
    }
    payload: dict[str, Any] = {
        "schema_version": "erasemap-open-transfer-smoke-v1",
        "not_confirmatory": True,
        "protocol_sha256": sha256_file(protocol_path),
        "core_sha256": core_sha256(protocol),
        "git_revision": _git_revision(),
        "records": [record.payload() for record in sorted(records, key=lambda item: item.case_id)],
        "artifacts": dict(sorted(artifact_hashes.items())),
    }
    _write_atomic(smoke_path, canonical_json(payload) + b"\n")
    return payload


def run_live_experiment(
    protocol_path: Path,
    output: Path,
    *,
    smoke: bool,
) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"runner output is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    protocol = _load_protocol(protocol_path)
    assets_root = output / "assets"
    prepare_assets(protocol_path, assets_root)
    asset_path = assets_root / "olivetti-transfer-v1.npz"
    evidence_root = output / "evidence"
    with tempfile.TemporaryDirectory(prefix="erasemap-open-transfer-services-") as directory:
        records = run_live_families(
            protocol,
            core_hash=core_sha256(protocol),
            asset_path=asset_path,
            evidence_root=evidence_root,
            service_root=Path(directory),
            smoke=smoke,
        )
    support_artifacts = (
        asset_path,
        assets_root / "PROVENANCE.json",
        evidence_root / "keycloak-identity.jsonl",
        evidence_root / "mlflow-lineage.jsonl",
        evidence_root / "qdrant-biometric.jsonl",
    )
    if smoke:
        return _write_smoke_bundle(
            records,
            protocol,
            protocol_path,
            output,
            support_artifacts=support_artifacts,
        )
    return write_result_bundle(
        records,
        protocol,
        protocol_path,
        output,
        support_artifacts=support_artifacts,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=Path("benchmark/open-transfer-v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    result = run_live_experiment(args.protocol, args.output, smoke=args.smoke)
    print(canonical_json(result).decode())
    if args.smoke:
        return 0
    summary = result.get("summary")
    return 0 if isinstance(summary, dict) and summary.get("decision") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
