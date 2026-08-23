from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from external_ghostgraph_challenge.run import run_public
from external_ghostgraph_challenge.schema import (
    canonical,
    load_object,
    public_suite,
    validate_suite,
)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def status(submission: Path | None) -> dict[str, object]:
    if submission is None or not submission.is_dir():
        return {
            "status": "NOT_COLLECTED",
            "independent_evidence": False,
            "reason": "no independently signed GhostGraph submission is present",
        }
    return verify_submission(submission)


def verify_submission(root: Path) -> dict[str, object]:
    protocol = load_object(Path(__file__).with_name("protocol-v1.json"))
    suite = load_object(root / "truth-reveal.json")
    public = load_object(root / "public.json")
    commitment = load_object(root / "commitment.json")
    result = load_object(root / "result.json")
    manifest = load_object(root / "manifest.json")
    attestation = load_object(root / "attestation.json")
    validate_suite(suite, minimum_cases=int(protocol["required_case_count_min"]))
    if public != public_suite(suite):
        raise ValueError("public challenge differs from revealed suite")
    truth_bytes = canonical(suite)
    if commitment.get("truth_sha256") != _sha(truth_bytes):
        raise ValueError("truth commitment mismatch")
    if commitment.get("public_sha256") != _sha(canonical(public)):
        raise ValueError("public commitment mismatch")
    sealed = (root / "sealed.bin").read_bytes()
    if commitment.get("sealed_sha256") != _sha(sealed):
        raise ValueError("sealed challenge commitment mismatch")

    core_path = root / "ghostgraph-v1.json"
    core = load_object(core_path)
    recomputed = run_public(public, core)
    if result != json.loads(canonical(recomputed)):
        raise ValueError("external result does not match frozen public execution")
    trial_by_id = {item["case_id"]: item for item in result["trials"]}
    false_confident = 0
    for case in suite["cases"]:
        expected = case["truth"]["expected_verdict"]
        trial = trial_by_id[case["case_id"]]
        if trial["verdict"] != expected:
            false_confident += int(
                trial["verdict"]
                in {"GRAPH_DISCOVERED", "PATH_CLASS_DISCOVERED", "EQUIVALENCE_CLASS"}
            )
        if not trial["oracle_match"]:
            raise ValueError("external production/oracle mismatch")

    required = set(protocol["required_evidence_gates"])
    gates = manifest.get("evidence_gates")
    if not isinstance(gates, dict) or set(gates) != required or not all(gates.values()):
        raise ValueError("nine external evidence gates are incomplete")
    if manifest.get("result_sha256") != _sha((root / "result.json").read_bytes()):
        raise ValueError("manifest result hash mismatch")
    if manifest.get("core_sha256") != _sha(core_path.read_bytes()):
        raise ValueError("manifest core protocol hash mismatch")
    if manifest.get("evaluator_name") != suite["author"]["name"]:
        raise ValueError("evaluator identity differs from suite author")

    public_key_text = str(attestation.get("public_key", ""))
    if public_key_text in protocol["project_public_key_blocklist"]:
        raise ValueError("project self-signature is not independent evidence")
    if attestation.get("manifest_sha256") != _sha(canonical(manifest)):
        raise ValueError("attestation does not bind manifest")
    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_text))
        public_key.verify(
            base64.b64decode(str(attestation["signature"])), canonical(manifest)
        )
    except (InvalidSignature, KeyError, TypeError, ValueError) as exc:
        raise ValueError("external GhostGraph signature is invalid") from exc
    if false_confident:
        raise ValueError("external challenge contains a false confident output")
    return {
        "status": "TECHNICALLY_VALID_PENDING_IDENTITY_REVIEW",
        "independent_evidence": True,
        "evaluator_name": manifest["evaluator_name"],
        "case_count": len(suite["cases"]),
        "false_confident_count": false_confident,
        "claim_boundary": protocol["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path)
    args = parser.parse_args()
    report = status(args.submission)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
