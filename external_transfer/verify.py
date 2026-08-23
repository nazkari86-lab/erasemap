from __future__ import annotations

import argparse
import base64
import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from external_transfer.attest import canonical, sha256_bytes

SCHEMA = "erasemap-external-transfer-manifest-v1"
AUTHORSHIP_DECLARATION = (
    "I authored or independently operated the hidden evaluation without giving hidden cases, "
    "labels, or expected faults to the EraSeMap author before the frozen run completed."
)
REQUIRED_FIELDS = {
    "schema_version",
    "evaluation_id",
    "evaluator_name",
    "evaluator_contact",
    "evaluator_status",
    "organization",
    "authorship_declaration",
    "started_at",
    "ended_at",
    "clean_commit",
    "core_sha256",
    "service_images",
    "artifacts",
    "result_sha256",
}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain an object")
    return cast(dict[str, Any], payload)


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be an ISO-8601 UTC timestamp")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 UTC timestamp") from exc


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if set(manifest) != REQUIRED_FIELDS or manifest.get("schema_version") != SCHEMA:
        raise ValueError("external transfer manifest schema mismatch")
    for field in ("evaluation_id", "evaluator_name", "evaluator_contact"):
        if not isinstance(manifest[field], str) or not manifest[field].strip():
            raise ValueError(f"{field} is required")
    if manifest["evaluator_status"] not in {"independent_person", "organization"}:
        raise ValueError("evaluator_status must establish external operation")
    if manifest["evaluator_status"] == "organization" and not str(manifest["organization"]).strip():
        raise ValueError("organization is required for organization status")
    if manifest["authorship_declaration"] != AUTHORSHIP_DECLARATION:
        raise ValueError("authorship declaration mismatch")
    if _timestamp(manifest["started_at"], "started_at") >= _timestamp(
        manifest["ended_at"], "ended_at"
    ):
        raise ValueError("evaluation timestamps must increase")
    if re.fullmatch(r"[0-9a-f]{40}", str(manifest["clean_commit"])) is None:
        raise ValueError("clean_commit must be a full Git commit")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", str(manifest["core_sha256"])) is None:
        raise ValueError("core_sha256 is malformed")
    images = manifest["service_images"]
    if (
        not isinstance(images, dict)
        or len(images) < 1
        or any(
            re.fullmatch(r"[^@\s]+@sha256:[0-9a-f]{64}", str(value)) is None
            for value in images.values()
        )
    ):
        raise ValueError("service images must be immutable digest references")
    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError("artifact hash manifest is required")
    for relative, digest in artifacts.items():
        path = PurePosixPath(str(relative))
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ValueError("artifact path must be safe and relative")
        if re.fullmatch(r"sha256:[0-9a-f]{64}", str(digest)) is None:
            raise ValueError("artifact digest is malformed")
    if manifest["result_sha256"] not in set(artifacts.values()):
        raise ValueError("result_sha256 must be bound by the artifact manifest")


def verify_submission(root: Path) -> dict[str, Any]:
    manifest = _load(root / "manifest.json")
    attestation = _load(root / "attestation.json")
    _validate_manifest(manifest)
    artifacts = cast(dict[str, str], manifest["artifacts"])
    for relative, expected in artifacts.items():
        path = root / relative
        if not path.is_file() or sha256_bytes(path.read_bytes()) != expected:
            raise ValueError(f"external artifact hash mismatch: {relative}")
    if attestation.get("schema_version") != "erasemap-external-transfer-attestation-v1":
        raise ValueError("external attestation schema mismatch")
    commitment = sha256_bytes(canonical(manifest))
    if attestation.get("manifest_sha256") != commitment:
        raise ValueError("attestation does not bind the manifest")
    statement = attestation.get("statement")
    if not isinstance(statement, dict) or statement.get("manifest_sha256") != commitment:
        raise ValueError("attestation statement mismatch")
    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(attestation["public_key"]))
        public.verify(base64.b64decode(attestation["signature"]), canonical(statement))
    except (InvalidSignature, KeyError, TypeError, ValueError) as exc:
        raise ValueError("external attestation signature is invalid") from exc
    return {
        "technical_decision": "PASS",
        "evaluation_id": manifest["evaluation_id"],
        "evaluator_name": manifest["evaluator_name"],
        "evaluator_status": manifest["evaluator_status"],
        "identity_and_conflict_review": "REQUIRED",
        "claim_boundary": (
            "A valid signature proves bundle integrity and key control, not evaluator identity, "
            "independence, or organizational authorization."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_submission(args.submission), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
