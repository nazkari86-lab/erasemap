import json
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from erasemap.cli import main
from erasemap.codec import graph_to_json
from erasemap.domain import (
    Artifact,
    ArtifactState,
    ArtifactType,
    ErasureGraph,
    Evidence,
    EvidenceKind,
)
from erasemap.evidence_envelopes import issue_evidence_envelope
from erasemap.receipts import generate_keypair

CLI = (sys.executable, "-m", "erasemap.cli")


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([*CLI, *arguments], capture_output=True, text=True, check=False)


def test_audit_command_emits_machine_readable_status() -> None:
    result = run_cli("audit", "examples/five_branch_system.json", "--subject", "subject-1")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "INCOMPLETE"
    assert payload["shortest_path"] == ["source", "template"]


def test_generate_command_writes_reproducible_graph(tmp_path: Path) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"

    first = run_cli(
        "generate", "--seed", "7", "--nodes", "10", "--fault", "STALE_CACHE", "--output", str(left)
    )
    second = run_cli(
        "generate", "--seed", "7", "--nodes", "10", "--fault", "STALE_CACHE", "--output", str(right)
    )

    assert first.returncode == second.returncode == 0
    assert left.read_bytes() == right.read_bytes()
    assert json.loads(first.stdout)["faults"][0]["kind"] == "STALE_CACHE"


def test_invalid_input_returns_code_two() -> None:
    result = run_cli("generate", "--seed", "-1", "--nodes", "2", "--output", "x")

    assert result.returncode == 2
    assert result.stderr


def test_invalid_receipt_returns_code_three(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text("{}")

    result = run_cli("receipt", "verify", "--public-key", "00" * 32, "--receipt", str(receipt))

    assert result.returncode == 3


def test_signed_audit_persists_nonce_and_rejects_cross_process_replay(
    tmp_path: Path,
) -> None:
    private_key, public_key = generate_keypair()
    artifact = Artifact(
        "blocked-cache", "subject-1", ArtifactType.CACHE_ENTRY, ArtifactState.BLOCKED
    )
    graph = tmp_path / "graph.json"
    graph.write_text(graph_to_json(ErasureGraph({artifact.id: artifact}, ())))
    evidence = Evidence(
        "control-1",
        artifact.id,
        EvidenceKind.SIGNED_STATEMENT,
        issued_epoch=100,
        metadata=(("control_id", "deny-1"), ("enforced", "true")),
    )
    envelope = issue_evidence_envelope(private_key, "issuer-1", evidence, nonce="fixed")
    envelopes = tmp_path / "envelopes.json"
    envelopes.write_text(json.dumps([envelope.serialized()]))
    trust_store = tmp_path / "keys.json"
    trust_store.write_text(
        json.dumps(
            {
                "issuer-1": public_key.public_bytes(
                    serialization.Encoding.Raw, serialization.PublicFormat.Raw
                ).hex()
            }
        )
    )
    ledger = tmp_path / "ledger.json"
    arguments = (
        "audit",
        str(graph),
        "--subject",
        artifact.subject_id,
        "--signed-evidence",
        str(envelopes),
        "--trust-store",
        str(trust_store),
        "--nonce-ledger",
        str(ledger),
        "--max-evidence-age",
        "300",
        "--now",
        "100",
    )

    assert json.loads(run_cli(*arguments).stdout)["status"] == "COMPLETE"
    assert json.loads(run_cli(*arguments).stdout)["status"] == "UNVERIFIED"


def test_direct_generate_audit_and_plan_workflow(tmp_path: Path, capsys: object) -> None:
    graph = tmp_path / "case.json"
    assert (
        main(
            [
                "generate",
                "--seed",
                "8",
                "--nodes",
                "10",
                "--fault",
                "ORPHANED_TEMPLATE",
                "--output",
                str(graph),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["audit", str(graph), "--subject", "subject-1"]) == 0
    audit_payload = json.loads(capsys.readouterr().out)
    assert audit_payload["status"] == "INCOMPLETE"

    node_ids = [item["id"] for item in json.loads(graph.read_text())["nodes"]]
    actions = tmp_path / "actions.json"
    actions.write_text(
        json.dumps(
            [
                {
                    "cost": 3,
                    "covers_artifact_ids": node_ids,
                    "id": "erase-all",
                    "result_state": "ERASED",
                }
            ]
        )
    )
    assert (
        main(
            [
                "plan",
                str(graph),
                "--subject",
                "subject-1",
                "--actions",
                str(actions),
                "--solver",
                "exact",
            ]
        )
        == 0
    )
    plan_payload = json.loads(capsys.readouterr().out)
    assert plan_payload["complete"]
    assert plan_payload["total_cost"] == 3


def test_direct_receipt_issue_and_verify(tmp_path: Path, capsys: object) -> None:
    private_key, public_key = generate_keypair()
    private_hex = private_key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    ).hex()
    public_hex = public_key.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()
    receipt = tmp_path / "receipt.json"

    assert (
        main(
            [
                "receipt",
                "issue",
                "--private-key",
                private_hex,
                "--request",
                "request-1",
                "--graph-root",
                "sha256:root",
                "--status",
                "COMPLETE",
                "--issued",
                "100",
                "--nonce",
                "fixed-nonce",
                "--output",
                str(receipt),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "receipt",
                "verify",
                "--public-key",
                public_hex,
                "--receipt",
                str(receipt),
                "--now",
                "100",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["valid"]


def test_direct_development_benchmark(tmp_path: Path, capsys: object) -> None:
    protocol = tmp_path / "protocol.json"
    output = tmp_path / "output"
    protocol.write_text(
        json.dumps(
            {
                "bootstrap_samples": 10,
                "bootstrap_seed": 1,
                "development_seeds": [1],
                "fault_matrix": [[], ["STALE_CACHE"]],
                "graph_sizes": [10],
                "holdout_seeds": [2],
                "methods": ["erasemap"],
                "primary_endpoint": "false_complete_rate",
                "schema_version": "erasemap-benchmark-v1",
                "topology_families": ["government-identity"],
            }
        )
    )

    assert (
        main(
            [
                "benchmark",
                "dev",
                "--protocol",
                str(protocol),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["trial_count"] == 2


def test_direct_invalid_input_is_reported(capsys: object) -> None:
    assert main(["generate", "--seed", "-1", "--nodes", "10", "--output", "unused"]) == 2
    assert "seed cannot be negative" in capsys.readouterr().err
