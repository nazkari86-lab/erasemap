from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from external_challenge.attest import verify_submission_attestation
from external_challenge.runner import predict_public_package
from external_challenge.seal import canonical, score_predictions

SCHEMA = "erasemap-independent-submission-v1"
INDEPENDENCE_STATEMENT = (
    "The evaluator controlled case authorship, hidden labels, freeze timing, reveal timing, "
    "and scoring without access by the EraSeMap author before prediction freeze."
)
FILES = {
    "frozen_predictions": "frozen-predictions.json",
    "public_package": "public-package.json",
    "reveal_key": "reveal-key.txt",
    "score": "score.json",
}
MANIFEST_FIELDS = {
    "affiliation",
    "authorship_started_at",
    "challenge_commit",
    "challenge_repository_url",
    "conflict_of_interest",
    "erasemap_commit",
    "evaluation_id",
    "evaluator",
    "family_provenance",
    "file_sha256",
    "identity_url",
    "independence_statement",
    "labels_revealed_at",
    "predictions_frozen_at",
    "schema_version",
}


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return cast(dict[str, Any], value)


def _https_url(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{field} must be an absolute HTTPS URL")
    return value


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be an ISO-8601 UTC timestamp ending in Z")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from error


def _raw_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_manifest(manifest: dict[str, Any], package: dict[str, Any]) -> None:
    if set(manifest) != MANIFEST_FIELDS or manifest.get("schema_version") != SCHEMA:
        raise ValueError("submission manifest schema mismatch")
    for field in ("evaluation_id", "evaluator", "affiliation"):
        if not isinstance(manifest[field], str) or not manifest[field].strip():
            raise ValueError(f"{field} is required")
    _https_url(manifest["identity_url"], "identity_url")
    repository = _https_url(manifest["challenge_repository_url"], "challenge_repository_url")
    normalized_repository = repository.lower().rstrip("/").removesuffix(".git")
    if normalized_repository == "https://github.com/nazkari86-lab/erasemap":
        raise ValueError("challenge repository must be external to the EraSeMap repository")
    for field in ("challenge_commit", "erasemap_commit"):
        if not isinstance(manifest[field], str) or not re.fullmatch(
            r"[0-9a-f]{40,64}", manifest[field]
        ):
            raise ValueError(f"{field} must be a full hexadecimal commit id")
    if manifest["conflict_of_interest"] != "none_declared":
        raise ValueError("conflict_of_interest must be none_declared")
    if manifest["independence_statement"] != INDEPENDENCE_STATEMENT:
        raise ValueError("independence statement mismatch")
    authored = _timestamp(manifest["authorship_started_at"], "authorship_started_at")
    frozen = _timestamp(manifest["predictions_frozen_at"], "predictions_frozen_at")
    revealed = _timestamp(manifest["labels_revealed_at"], "labels_revealed_at")
    if not authored < frozen < revealed:
        raise ValueError("timestamps must satisfy authorship < prediction freeze < label reveal")
    provenance = manifest["family_provenance"]
    if not isinstance(provenance, list):
        raise ValueError("family_provenance must be an array")
    entries: dict[str, str] = {}
    for item in provenance:
        if not isinstance(item, dict) or set(item) != {"family", "source_url"}:
            raise ValueError("family provenance schema mismatch")
        family = item["family"]
        if not isinstance(family, str) or not family or family in entries:
            raise ValueError("family provenance names must be unique and non-empty")
        entries[family] = _https_url(item["source_url"], "family source_url")
    public_cases = package.get("public_cases")
    if not isinstance(public_cases, list):
        raise ValueError("public package cases are required")
    package_families = {str(case["family"]) for case in public_cases}
    if set(entries) != package_families:
        raise ValueError("family provenance must cover every and only public package family")
    if len(set(entries.values())) < 4:
        raise ValueError("at least four distinct family provenance URLs are required")


def verify_submission(
    directory: Path, protocol_path: Path, expected_erasemap_commit: str | None = None
) -> dict[str, object]:
    manifest = _load_object(directory / "manifest.json")
    package = _load_object(directory / FILES["public_package"])
    _validate_manifest(manifest, package)
    if (
        expected_erasemap_commit is not None
        and manifest["erasemap_commit"] != expected_erasemap_commit
    ):
        raise ValueError("submission was produced by a different EraSeMap commit")
    declared_hashes = manifest["file_sha256"]
    if not isinstance(declared_hashes, dict) or set(declared_hashes) != set(FILES):
        raise ValueError("file_sha256 must bind every required submission file")
    for file_key, filename in FILES.items():
        if declared_hashes[file_key] != _raw_sha256(directory / filename):
            raise ValueError(f"submission file hash mismatch: {filename}")
    frozen = _load_object(directory / FILES["frozen_predictions"])
    expected_predictions = predict_public_package(package)
    if canonical(frozen.get("predictions")) != canonical(expected_predictions):
        raise ValueError("frozen predictions do not match the declared EraSeMap implementation")
    score = _load_object(directory / FILES["score"])
    protocol = _load_object(protocol_path)
    encoded_key = (directory / FILES["reveal_key"]).read_text().strip()
    try:
        decoded_key = base64.b64decode(encoded_key, altchars=b"-_", validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError("invalid reveal key encoding") from error
    recomputed = score_predictions(package, decoded_key, frozen, protocol)
    if canonical(recomputed) != canonical(score):
        raise ValueError("published score does not match independent recomputation")
    if score.get("decision") != "PASS":
        raise ValueError("external submission did not pass the frozen protocol")
    attestation = _load_object(directory / "attestation.json")
    if not verify_submission_attestation(score, manifest, attestation):
        raise ValueError("submission attestation does not bind score and manifest")
    return {
        "evaluation_id": manifest["evaluation_id"],
        "evaluator": manifest["evaluator"],
        "independence_decision": "PENDING_IDENTITY_AND_CONFLICT_REVIEW",
        "score_decision": score["decision"],
        "technical_decision": "PASS",
        "total_cases": score["total_cases"],
        "truth_noncomplete": score["truth_noncomplete"],
        "verdict_accuracy": score["verdict_accuracy"],
        "false_complete": score["false_complete"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an external EraSeMap evidence submission")
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument(
        "--protocol", default=Path("external_challenge/protocol-v1.json"), type=Path
    )
    parser.add_argument("--expected-erasemap-commit")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_submission(
        args.submission, args.protocol, args.expected_erasemap_commit
    )
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        if args.output.exists():
            raise FileExistsError(f"refusing to overwrite {args.output}")
        args.output.write_text(encoded)
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
