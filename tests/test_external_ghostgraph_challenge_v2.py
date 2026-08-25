from __future__ import annotations

import base64
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from erasemap.ghostgraph import predict_trace
from experiments.run_ghostgraph_v1 import _objects, _truth_graph
from external_ghostgraph_challenge.active import run_active
from external_ghostgraph_challenge.attest import generate_keypair, sign_manifest
from external_ghostgraph_challenge.schema import canonical, public_suite_v2, validate_suite_v2
from external_ghostgraph_challenge.seal import seal_suite, unseal_suite
from external_ghostgraph_challenge.verify_v2 import status, verify_submission

ROOT = Path(__file__).resolve().parents[1]


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _suite() -> dict[str, object]:
    return {
        "schema_version": "erasemap-external-ghostgraph-suite-v2",
        "author": {
            "name": "External Evaluator",
            "contact": "evaluator@example.org",
            "affiliation": "Example Independent Lab",
            "project_member": False,
            "authored_hidden_cases": True,
        },
        "cases": [
            {
                "case_id": "external-direct",
                "kind": "in-catalogue-recurrence",
                "truth_graph_id": "g-live-direct",
            },
            {
                "case_id": "external-missing-evidence",
                "kind": "missing-evidence",
                "truth_graph_id": "g-live-direct",
                "evidence_overrides": {"subjects_isolated": False},
            },
            {
                "case_id": "external-outside",
                "kind": "outside-catalogue",
                "truth_graph": {
                    "graph_id": "external-unknown",
                    "edges": [
                        {
                            "edge_id": "unknown-restore",
                            "operation_id": "restore",
                            "source_id": "source",
                            "target_id": "lineage",
                        },
                        {
                            "edge_id": "unknown-index",
                            "operation_id": "index",
                            "source_id": "lineage",
                            "target_id": "vector",
                        },
                    ],
                    "initial_node_ids": ["source"],
                    "residual_node_ids": ["vector"],
                },
            },
            {
                "case_id": "external-path-equivalent",
                "kind": "path-equivalent",
                "truth_graph_id": "g-live-multi-audit",
            },
            {
                "case_id": "external-safe",
                "kind": "safe",
                "truth_graph_id": "g-live-safe",
            },
        ],
    }


def _submission(tmp_path: Path) -> Path:
    root = tmp_path / "submission"
    root.mkdir(parents=True)
    suite = _suite()
    core = json.loads((ROOT / "benchmark/ghostgraph-live-v2.json").read_text())
    hypotheses, experiments = _objects(core)
    experiment_by_id = {item.experiment_id: item for item in experiments}
    case_by_id = {item["case_id"]: item for item in suite["cases"]}  # type: ignore[index]

    public = public_suite_v2(suite)
    key = Fernet.generate_key()
    sealed, commitment = seal_suite(suite, key)
    assert unseal_suite(sealed, key, str(commitment["truth_sha256"])) == suite

    def execute(case_id: str, experiment_id: str) -> tuple[bool, ...]:
        truth = _truth_graph(case_by_id[case_id], hypotheses, core)
        return predict_trace(truth, experiment_by_id[experiment_id]).bits

    result = run_active(public, core, execute)
    (root / "truth-reveal.json").write_bytes(canonical(suite))
    (root / "public.json").write_bytes(canonical(public))
    (root / "commitment.json").write_bytes(canonical(commitment))
    (root / "sealed.bin").write_bytes(sealed)
    (root / "result.json").write_bytes(canonical(result))

    protocol = json.loads((ROOT / "external_ghostgraph_challenge/protocol-v2.json").read_text())
    source_hashes = {}
    for relative in protocol["required_source_files"]:
        source = ROOT / relative
        target = root / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        source_hashes[relative] = _sha(target.read_bytes())
    manifest = {
        "schema_version": "erasemap-external-ghostgraph-manifest-v2",
        "evaluator_name": suite["author"]["name"],  # type: ignore[index]
        "evaluator_contact": suite["author"]["contact"],  # type: ignore[index]
        "clean_commit": "a" * 40,
        "result_sha256": _sha((root / "result.json").read_bytes()),
        "source_sha256": source_hashes,
    }
    (root / "manifest.json").write_bytes(canonical(manifest))
    private_pem, _ = generate_keypair()
    (root / "attestation.json").write_bytes(canonical(sign_manifest(manifest, private_pem)))
    return root


def test_v2_public_bundle_is_answer_blind_and_seal_round_trips() -> None:
    suite = _suite()
    validate_suite_v2(suite)
    key = Fernet.generate_key()
    sealed, commitment = seal_suite(suite, key)
    public = public_suite_v2(suite)

    assert "truth_graph" not in json.dumps(public)
    assert "name" not in public["author_commitment"]  # type: ignore[operator]
    assert unseal_suite(sealed, key, str(commitment["truth_sha256"])) == suite


def test_v2_valid_signed_blind_active_submission_passes(tmp_path: Path) -> None:
    report = verify_submission(_submission(tmp_path))

    assert report["status"] == "TECHNICALLY_VALID_PENDING_IDENTITY_REVIEW"
    assert report["case_count"] == 5
    assert report["false_confident_count"] == 0
    assert all(report["computed_evidence_gates"].values())  # type: ignore[union-attr]


def test_v2_rejects_trace_tamper_signature_tamper_and_duplicates(tmp_path: Path) -> None:
    root = _submission(tmp_path)
    result = json.loads((root / "result.json").read_text())
    first_trace = next(
        step["trace_bits"]
        for trial in result["trials"]
        for step in trial["steps"]
        if step["trace_bits"] is not None
    )
    first_trace[0] = not first_trace[0]
    (root / "result.json").write_bytes(canonical(result))
    with pytest.raises(ValueError, match=r"adapter response|manifest result"):
        verify_submission(root)

    root = _submission(tmp_path / "signature")
    attestation = json.loads((root / "attestation.json").read_text())
    attestation["signature"] = base64.b64encode(b"invalid").decode()
    (root / "attestation.json").write_bytes(canonical(attestation))
    with pytest.raises(ValueError, match="signature is invalid"):
        verify_submission(root)

    suite = _suite()
    suite["cases"][1]["case_id"] = "external-direct"  # type: ignore[index]
    with pytest.raises(ValueError, match="duplicate"):
        validate_suite_v2(suite)


def test_v2_rejects_project_key_and_absence_is_not_collected(tmp_path: Path) -> None:
    root = _submission(tmp_path)
    attestation = json.loads((root / "attestation.json").read_text())
    attestation["public_key"] = "/nWaA+Gu+lC7Liefp8lt1CxX1mUbBgD2RL0DdNxD0g0="
    (root / "attestation.json").write_bytes(canonical(attestation))
    with pytest.raises(ValueError, match="self-signature"):
        verify_submission(root)

    report = status(tmp_path / "absent")
    assert report["status"] == "NOT_COLLECTED"
    assert report["independent_evidence"] is False
