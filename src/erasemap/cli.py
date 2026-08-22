from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from erasemap.audit import audit_subject
from erasemap.benchmark import load_protocol, run_protocol
from erasemap.codec import graph_from_json, graph_to_json
from erasemap.domain import (
    ArtifactState,
    AuditStatus,
    Evidence,
    EvidenceKind,
    RemediationAction,
)
from erasemap.evidence_envelopes import (
    EvidenceEnvelope,
    SqliteEvidenceEnvelopeLedger,
    audit_signed_subject,
    evidence_envelope_from_payload,
)
from erasemap.generator import FaultKind, generate_case
from erasemap.planning import exact_plan, greedy_plan
from erasemap.receipts import (
    ErasureReceipt,
    ReceiptLedger,
    issue_receipt,
    verify_receipt,
)


def _json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _print(payload: Any) -> None:
    sys.stdout.write(_json(payload) + "\n")


def _load_evidence(path: str | None) -> dict[str, Evidence]:
    if path is None:
        return {}
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, list):
        raise ValueError("evidence file must contain an array")
    result: dict[str, Evidence] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each evidence item must be an object")
        evidence = Evidence(
            id=str(item["id"]),
            artifact_id=str(item["artifact_id"]),
            kind=EvidenceKind(str(item["kind"])),
            valid_signature=bool(item.get("valid_signature", False)),
            commitment=str(item.get("commitment", "")),
            observed_absent=bool(item.get("observed_absent", False)),
            issued_epoch=int(item.get("issued_epoch", 0)),
            expires_epoch=(
                int(item["expires_epoch"]) if item.get("expires_epoch") is not None else None
            ),
            metadata=tuple((str(key), str(value)) for key, value in item.get("metadata", [])),
        )
        result[evidence.artifact_id] = evidence
    return result


def _audit_payload(result: Any) -> dict[str, Any]:
    return {
        "evidence_checks": [
            {
                "artifact_id": node_id,
                "effective_state": check.effective_state.value,
                "reason": check.reason,
                "valid": check.valid,
            }
            for node_id, check in result.evidence_checks
        ],
        "reachable_artifact_ids": sorted(result.reachable_artifact_ids),
        "residual_paths": [list(path.node_ids) for path in result.residual_paths],
        "shortest_path": (
            list(result.shortest_path.node_ids) if result.shortest_path is not None else None
        ),
        "status": result.status.value,
    }


def _generate(args: argparse.Namespace) -> int:
    faults = tuple(FaultKind(value) for value in args.fault)
    case = generate_case(seed=args.seed, node_count=args.nodes, faults=faults)
    Path(args.output).write_text(graph_to_json(case.graph) + "\n")
    _print(
        {
            "faults": [
                {"artifact_id": fault.artifact_id, "kind": fault.kind.value}
                for fault in case.truth.faults
            ],
            "node_count": len(case.graph.nodes),
            "output": args.output,
            "seed": case.seed,
        }
    )
    return 0


def _audit(args: argparse.Namespace) -> int:
    graph = graph_from_json(Path(args.graph).read_text())
    if args.signed_evidence is not None:
        if (
            args.evidence is not None
            or args.trust_store is None
            or args.nonce_ledger is None
            or args.max_evidence_age is None
        ):
            raise ValueError(
                "signed evidence requires --trust-store, --nonce-ledger, and "
                "--max-evidence-age, and excludes --evidence"
            )
        raw_envelopes = json.loads(Path(args.signed_evidence).read_text())
        raw_keys = json.loads(Path(args.trust_store).read_text())
        if not isinstance(raw_envelopes, list) or not isinstance(raw_keys, dict):
            raise ValueError("signed evidence must be an array and trust store an object")
        envelopes: dict[str, EvidenceEnvelope] = {}
        for raw in raw_envelopes:
            envelope = evidence_envelope_from_payload(raw)
            if envelope.evidence.artifact_id in envelopes:
                raise ValueError("duplicate signed evidence for one artifact")
            envelopes[envelope.evidence.artifact_id] = envelope
        trust_store = {
            str(key_id): Ed25519PublicKey.from_public_bytes(bytes.fromhex(str(value)))
            for key_id, value in raw_keys.items()
        }
        with SqliteEvidenceEnvelopeLedger(args.nonce_ledger) as ledger:
            result = audit_signed_subject(
                graph,
                envelopes,
                trust_store,
                args.subject,
                now_epoch=args.now,
                ledger=ledger,
                max_age_seconds=args.max_evidence_age,
            )
    else:
        result = audit_subject(
            graph, _load_evidence(args.evidence), args.subject, now_epoch=args.now
        )
    _print(_audit_payload(result))
    return 0


def _load_actions(path: str) -> tuple[RemediationAction, ...]:
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, list):
        raise ValueError("actions file must contain an array")
    return tuple(
        RemediationAction(
            id=str(item["id"]),
            covers_artifact_ids=frozenset(str(value) for value in item["covers_artifact_ids"]),
            cost=int(item["cost"]),
            result_state=ArtifactState(str(item["result_state"])),
            permitted=bool(item.get("permitted", True)),
        )
        for item in raw
    )


def _plan(args: argparse.Namespace) -> int:
    graph = graph_from_json(Path(args.graph).read_text())
    audit = audit_subject(graph, {}, args.subject, now_epoch=args.now)
    required = frozenset(node_id for node_id, check in audit.evidence_checks if not check.valid)
    solver = exact_plan if args.solver == "exact" else greedy_plan
    result = solver(required, _load_actions(args.actions))
    _print(
        {
            "action_ids": list(result.action_ids),
            "complete": result.complete,
            "covered_artifact_ids": sorted(result.covered_artifact_ids),
            "total_cost": result.total_cost,
            "uncovered_artifact_ids": sorted(result.uncovered_artifact_ids),
        }
    )
    return 0


def _receipt_payload(receipt: ErasureReceipt) -> dict[str, Any]:
    return {**receipt.payload(), "signature": receipt.signature.hex()}


def _receipt_from_payload(raw: Any) -> ErasureReceipt:
    if not isinstance(raw, dict):
        raise ValueError("receipt must be an object")
    return ErasureReceipt(
        schema_version=str(raw["schema_version"]),
        request_id=str(raw["request_id"]),
        graph_root=str(raw["graph_root"]),
        audit_status=AuditStatus(str(raw["audit_status"])),
        issued_epoch=int(raw["issued_epoch"]),
        nonce=str(raw["nonce"]),
        previous_receipt_hash=(
            str(raw["previous_receipt_hash"])
            if raw.get("previous_receipt_hash") is not None
            else None
        ),
        signature=bytes.fromhex(str(raw["signature"])),
    )


def _receipt_issue(args: argparse.Namespace) -> int:
    private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(args.private_key))
    receipt = issue_receipt(
        private_key,
        args.request,
        args.graph_root,
        args.status,
        args.issued,
        nonce=args.nonce,
    )
    Path(args.output).write_text(_json(_receipt_payload(receipt)) + "\n")
    _print({"output": args.output, "nonce": receipt.nonce})
    return 0


def _receipt_verify(args: argparse.Namespace) -> int:
    try:
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(args.public_key))
        receipt = _receipt_from_payload(json.loads(Path(args.receipt).read_text()))
        result = verify_receipt(
            public_key,
            receipt,
            ReceiptLedger(),
            now_epoch=args.now,
            max_age_seconds=args.max_age,
            expected_previous_hash=args.previous_hash,
        )
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
        sys.stderr.write(f"invalid receipt: {error}\n")
        return 3
    _print({"reason": result.reason, "valid": result.valid})
    return 0 if result.valid else 3


def _benchmark(args: argparse.Namespace) -> int:
    report = run_protocol(load_protocol(args.protocol), output_dir=args.output, split=args.split)
    _print(
        {
            "failure_count": report.failure_count,
            "protocol_hash": report.protocol_hash,
            "trial_count": report.trial_count,
        }
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="erasemap")
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate")
    generate.add_argument("--seed", type=int, required=True)
    generate.add_argument("--nodes", type=int, required=True)
    generate.add_argument("--fault", action="append", default=[])
    generate.add_argument("--output", required=True)
    generate.set_defaults(handler=_generate)

    audit = commands.add_parser("audit")
    audit.add_argument("graph")
    audit.add_argument("--subject", required=True)
    audit.add_argument("--evidence")
    audit.add_argument("--signed-evidence")
    audit.add_argument("--trust-store")
    audit.add_argument("--nonce-ledger")
    audit.add_argument("--max-evidence-age", type=int)
    audit.add_argument("--now", type=int, default=100)
    audit.set_defaults(handler=_audit)

    plan = commands.add_parser("plan")
    plan.add_argument("graph")
    plan.add_argument("--subject", required=True)
    plan.add_argument("--actions", required=True)
    plan.add_argument("--solver", choices=("exact", "greedy"), default="greedy")
    plan.add_argument("--now", type=int, default=100)
    plan.set_defaults(handler=_plan)

    receipt = commands.add_parser("receipt")
    receipt_commands = receipt.add_subparsers(dest="receipt_command", required=True)
    issue = receipt_commands.add_parser("issue")
    issue.add_argument("--private-key", required=True)
    issue.add_argument("--request", required=True)
    issue.add_argument("--graph-root", required=True)
    issue.add_argument(
        "--status", choices=tuple(status.value for status in AuditStatus), required=True
    )
    issue.add_argument("--issued", type=int, required=True)
    issue.add_argument("--nonce")
    issue.add_argument("--output", required=True)
    issue.set_defaults(handler=_receipt_issue)
    verify = receipt_commands.add_parser("verify")
    verify.add_argument("--public-key", required=True)
    verify.add_argument("--receipt", required=True)
    verify.add_argument("--now", type=int)
    verify.add_argument("--max-age", type=int)
    verify.add_argument("--previous-hash")
    verify.set_defaults(handler=_receipt_verify)

    benchmark = commands.add_parser("benchmark")
    benchmark.add_argument("split", choices=("dev", "holdout"))
    benchmark.add_argument("--protocol", required=True)
    benchmark.add_argument("--output", required=True)
    benchmark.set_defaults(handler=_benchmark)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if getattr(args, "split", None) == "dev":
        args.split = "development"
    try:
        return int(args.handler(args))
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
