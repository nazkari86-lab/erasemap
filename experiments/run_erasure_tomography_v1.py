from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from erasemap.erasure_tomography import (
    ProbeDesign,
    TomographyEvidence,
    TomographyVerdict,
    certify_design,
    decode,
    predict,
)
from erasemap.erasure_tomography_lab import (
    CARRIER_FACTS,
    MultiCarrierStorageLab,
    run_tomography_and_stabilize,
    run_tomography_round,
)
from erasemap.erasure_tomography_oracle import oracle_decode

ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION_COMMIT = "c2f83dfdadc2a9f49082d7c27621aca985d19947"


def _canonical(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


def _protocol_design(protocol: dict[str, Any]) -> ProbeDesign:
    return ProbeDesign(
        tuple(str(item) for item in protocol["candidate_mechanism_ids"]),
        tuple(tuple(bool(value) for value in row) for row in protocol["probe_rows"]),
        int(protocol["max_failures"]),
        int(protocol["error_budget"]),
    )


def _validate_inputs(
    protocol_path: Path, reveal_path: Path
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    reveal = json.loads(reveal_path.read_text())
    if protocol.get("schema_version") != "erasemap-erasure-tomography-v1":
        raise ValueError("unsupported erasure tomography protocol")
    if reveal.get("schema_version") != "erasemap-erasure-tomography-reveal-v1":
        raise ValueError("unsupported erasure tomography reveal")
    schedule = protocol["support_schedule"]
    if _canonical_sha256(reveal) != schedule["canonical_sha256"]:
        raise ValueError("erasure tomography reveal commitment mismatch")
    cases = reveal.get("cases")
    if not isinstance(cases, list) or len(cases) != int(schedule["case_count"]):
        raise ValueError("erasure tomography reveal case count mismatch")
    case_ids = [str(item["case_id"]) for item in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("duplicate erasure tomography case id")
    for relative_path, expected in protocol["adapter_source_sha256"].items():
        actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"adapter source digest mismatch: {relative_path}")
    return protocol, reveal, protocol_bytes


def _greedy_rows(width: int) -> tuple[tuple[bool, ...], ...]:
    candidates = tuple(itertools.product((False, True), repeat=width))[1:]
    supports = ((), *(tuple([index]) for index in range(width)))
    unresolved = {
        (left, right)
        for left_index, left in enumerate(supports)
        for right in supports[left_index + 1 :]
    }
    selected: list[tuple[bool, ...]] = []
    while unresolved:
        scored = []
        for row in candidates:
            if row in selected:
                continue
            separates = sum(
                any(row[index] for index in left)
                != any(row[index] for index in right)
                for left, right in unresolved
            )
            scored.append((-separates, row))
        _, best = min(scored)
        selected.append(best)
        unresolved = {
            pair
            for pair in unresolved
            if any(best[index] for index in pair[0])
            == any(best[index] for index in pair[1])
        }
    return tuple(selected)


def _support_recovery(design: ProbeDesign) -> int:
    evidence = TomographyEvidence.complete()
    return sum(
        decode(design, predict(design, (mechanism_id,)), evidence).support
        == (mechanism_id,)
        for mechanism_id in design.mechanism_ids
    )


def _baseline_records(design: ProbeDesign) -> dict[str, object]:
    width = len(design.mechanism_ids)
    identity_rows = tuple(
        tuple(column == row for column in range(width)) for row in range(width)
    )
    individual = ProbeDesign(design.mechanism_ids, identity_rows, 1, 0)
    generator = random.Random(20_260_823)
    random_rows: list[tuple[bool, ...]] = []
    while len(random_rows) < len(design.rows):
        row = tuple(bool(generator.getrandbits(1)) for _ in range(width))
        if any(row) and row not in random_rows:
            random_rows.append(row)
    random_design = ProbeDesign(design.mechanism_ids, tuple(random_rows), 1, 0)
    greedy_design = ProbeDesign(design.mechanism_ids, _greedy_rows(width), 1, 0)
    return {
        "tomography": {
            "probe_count": len(design.rows),
            "exact_single_support_recovery": _support_recovery(design),
            "uniquely_decodable": certify_design(design).uniquely_decodable,
        },
        "individual_audit": {
            "probe_count": len(individual.rows),
            "exact_single_support_recovery": _support_recovery(individual),
        },
        "random_feasible_same_budget": {
            "rows": random_design.rows,
            "probe_count": len(random_design.rows),
            "exact_single_support_recovery": _support_recovery(random_design),
            "uniquely_decodable": certify_design(random_design).uniquely_decodable,
        },
        "greedy_separating": {
            "rows": greedy_design.rows,
            "probe_count": len(greedy_design.rows),
            "exact_single_support_recovery": _support_recovery(greedy_design),
            "uniquely_decodable": certify_design(greedy_design).uniquely_decodable,
        },
        "declared_topology_only": {
            "omitted_mechanism_localization_count": 0,
            "reason": "an omitted transition is absent from the declared audit object",
        },
    }


def _retained_subject_loss(
    root: Path,
    *,
    mechanism_ids: tuple[str, ...],
    control_ids: tuple[str, ...],
    seed: int,
) -> bool:
    carriers = frozenset(CARRIER_FACTS[item] for item in mechanism_ids)
    lab = MultiCarrierStorageLab(root, seed=seed, carriers=carriers)
    retained_id = f"retained-subject-{seed}"
    lab.lab.enroll(retained_id, -lab.vector)
    before = lab.lab.online_presence(retained_id)
    lab.install_controls(control_ids)
    lab.replay_registered_workflows()
    after = lab.lab.online_presence(retained_id)
    return any(present and not after[key] for key, present in before.items())


def _trial_record(
    case: dict[str, Any],
    root: Path,
    design: ProbeDesign,
) -> dict[str, object]:
    case_id = str(case["case_id"])
    kind = str(case["kind"])
    seed = int(case["seed"])
    active_ids = tuple(str(item) for item in case["active_ids"])
    if kind == "valid":
        stabilized = run_tomography_and_stabilize(
            root,
            active_ids=active_ids,
            seed=seed,
        )
        round_result = stabilized.round
        plan_ids = stabilized.plan.control_ids if stabilized.plan is not None else ()
        plan_cost = stabilized.plan.total_cost if stabilized.plan is not None else None
        post_control = stabilized.post_control_recurrence
        retained_loss = (
            _retained_subject_loss(
                root / "specificity",
                mechanism_ids=active_ids,
                control_ids=plan_ids,
                seed=seed + 20_000,
            )
            if stabilized.plan is not None
            else True
        )
    else:
        round_result = run_tomography_round(
            root,
            active_ids=active_ids,
            seed=seed,
            design=design,
            skipped_probe_index=(
                int(case["skipped_probe_index"])
                if "skipped_probe_index" in case
                else None
            ),
            contaminate_subjects=bool(case.get("contaminate_subjects", False)),
        )
        plan_ids = ()
        plan_cost = None
        post_control = None
        retained_loss = False
    oracle = oracle_decode(
        design,
        round_result.observations,
        round_result.evidence,
    )
    oracle_match = (
        round_result.report.verdict == oracle.verdict
        and round_result.report.support == oracle.support
        and round_result.report.admissible_supports == oracle.admissible_supports
        and round_result.report.distance == oracle.distance
    )
    return {
        "case_id": case_id,
        "kind": kind,
        "seed": seed,
        "active_ids": active_ids,
        "observations": round_result.observations,
        "workflow_evidence_complete": round_result.workflow_evidence_complete,
        "subject_commitments": round_result.subject_commitments,
        "evidence": asdict(round_result.evidence),
        "verdict": round_result.report.verdict.value,
        "support": round_result.report.support,
        "admissible_supports": round_result.report.admissible_supports,
        "distance": round_result.report.distance,
        "oracle": {
            "verdict": oracle.verdict.value,
            "support": oracle.support,
            "admissible_supports": oracle.admissible_supports,
            "distance": oracle.distance,
        },
        "oracle_match": oracle_match,
        "selected_control_ids": plan_ids,
        "selected_control_cost": plan_cost,
        "post_control_recurrence": post_control,
        "retained_subject_loss": retained_loss,
    }


def _metrics(
    trials: list[dict[str, object]], protocol: dict[str, Any]
) -> dict[str, int]:
    valid = [item for item in trials if item["kind"] == "valid"]
    safe = [item for item in trials if item["kind"] == "safe"]
    negative = [item for item in trials if item["kind"] not in {"valid", "safe"}]
    false_localization = sum(
        item["verdict"] == TomographyVerdict.LOCALIZED.value
        and tuple(item["support"]) != tuple(item["active_ids"])
        for item in trials
    )
    return {
        "valid_case_count": len(valid),
        "exact_support_recovery_count": sum(
            item["verdict"] == TomographyVerdict.LOCALIZED.value
            and tuple(item["support"]) == tuple(item["active_ids"])
            for item in valid
        ),
        "safe_no_recurrence_count": sum(
            item["verdict"] == TomographyVerdict.NO_OBSERVED_RECURRENCE.value
            for item in safe
        ),
        "negative_case_count": len(negative),
        "negative_case_pass_count": sum(
            item["verdict"] == TomographyVerdict.UNVERIFIED.value
            for item in negative
        ),
        "false_localization_count": false_localization,
        "oracle_mismatch_count": sum(not bool(item["oracle_match"]) for item in trials),
        "post_control_recurrence_count": sum(
            item["post_control_recurrence"] is True for item in valid
        ),
        "retained_subject_loss_count": sum(
            bool(item["retained_subject_loss"]) for item in valid
        ),
        "tomography_probe_count": len(protocol["probe_rows"]),
        "individual_audit_probe_count": int(protocol["individual_audit_probe_count"]),
    }


def _gates(metrics: dict[str, int], protocol: dict[str, Any]) -> dict[str, bool]:
    result = {}
    for gate_id, expected_value in protocol["primary_gates"].items():
        metric_id = gate_id.removesuffix("_max")
        observed = metrics[metric_id]
        expected = int(expected_value)
        result[gate_id] = observed <= expected if gate_id.endswith("_max") else observed == expected
    return result


def run(protocol_path: Path, reveal_path: Path, output: Path) -> dict[str, Any]:
    protocol, reveal, protocol_bytes = _validate_inputs(protocol_path, reveal_path)
    design = _protocol_design(protocol)
    trials = []
    for case in reveal["cases"]:
        with tempfile.TemporaryDirectory(prefix=f"erasemap-et-{case['case_id']}-") as root:
            trials.append(_trial_record(case, Path(root), design))
    metrics = _metrics(trials, protocol)
    gates = _gates(metrics, protocol)
    result = {
        "schema_version": "erasemap-erasure-tomography-result-v1",
        "protocol_id": protocol["protocol_id"],
        "protocol_hash": hashlib.sha256(protocol_bytes).hexdigest(),
        "reveal_hash": _canonical_sha256(reveal),
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "evidence_scope": protocol["evidence_scope"],
        "claim_boundary": protocol["claim_boundary"],
        "design_certificate": asdict(certify_design(design)),
        "baselines": _baseline_records(design),
        "metrics": metrics,
        "gates": gates,
        "passed": all(gates.values()) and len(gates) == len(protocol["primary_gates"]),
        "trials": trials,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "result.json").write_text(_canonical(result) + "\n")
    (output / "PROVENANCE.json").write_text(
        _canonical(
            {
                "protocol_path": str(protocol_path),
                "protocol_sha256": result["protocol_hash"],
                "reveal_path": str(reveal_path),
                "reveal_sha256": result["reveal_hash"],
                "preregistration_commit": PREREGISTRATION_COMMIT,
                "runner": "experiments/run_erasure_tomography_v1.py",
            }
        )
        + "\n"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "benchmark/erasure-tomography-v1.json",
    )
    parser.add_argument(
        "--reveal",
        type=Path,
        default=ROOT / "benchmark/erasure-tomography-v1-reveal.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/erasure-tomography-v1",
    )
    args = parser.parse_args()
    result = run(args.protocol, args.reveal, args.output)
    print(_canonical({"metrics": result["metrics"], "passed": result["passed"]}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
