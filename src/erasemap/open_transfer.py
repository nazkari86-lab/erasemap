from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Any

FAMILIES = ("keycloak-identity", "mlflow-lineage", "qdrant-biometric")
FAULT_STATES = (
    "safe_native",
    "surviving_derivative",
    "recovery_regeneration",
    "coverage_fault",
)
TRUTH_BY_FAULT = {
    "safe_native": "COMPLETE",
    "surviving_derivative": "INCOMPLETE",
    "recovery_regeneration": "INCOMPLETE",
    "coverage_fault": "UNVERIFIED",
}
VERDICTS = frozenset({"COMPLETE", "INCOMPLETE", "UNVERIFIED"})
RISK_FACTS = frozenset({"primary", "derivative", "recovery"})
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_IMAGE = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")


def expected_case_id(family: str, seed: int, fault_state: str) -> str:
    return f"{family}:{seed}:{fault_state}"


def _require_sha256(value: str, field: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise ValueError(f"{field} must be a canonical SHA-256 value")


@dataclass(frozen=True, slots=True)
class PhysicalOutcome:
    primary_absent: bool
    derivative_present: bool | None
    recovery_recurrence: bool | None
    coverage_complete: bool
    retained_before: int
    retained_after: int

    def __post_init__(self) -> None:
        if self.retained_before < 0 or self.retained_after < 0:
            raise ValueError("retained counts cannot be negative")


@dataclass(frozen=True, slots=True)
class ControlCandidate:
    id: str
    cost: int
    closes: frozenset[str]
    permitted: bool = True

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("control id is required")
        if self.cost < 0:
            raise ValueError("control cost cannot be negative")
        if not self.closes or not self.closes <= RISK_FACTS:
            raise ValueError("control must close known risk facts")


@dataclass(frozen=True, slots=True)
class PhysicalDecision:
    native_complete: bool
    typed_complete: bool
    erasemap_verdict: str
    shortest_witness: tuple[str, ...] | None
    selected_control_ids: tuple[str, ...]
    selected_cost: int
    oracle_control_ids: tuple[str, ...]
    oracle_cost: int
    retained_loss: bool


def _required_risks(outcome: PhysicalOutcome) -> frozenset[str]:
    required: set[str] = set()
    if not outcome.primary_absent:
        required.add("primary")
    if outcome.derivative_present:
        required.add("derivative")
    if outcome.recovery_recurrence:
        required.add("recovery")
    return frozenset(required)


def _exact_control_plan(
    required: frozenset[str], controls: tuple[ControlCandidate, ...]
) -> tuple[tuple[str, ...], int]:
    permitted = tuple(sorted((item for item in controls if item.permitted), key=lambda x: x.id))
    best: tuple[int, int, tuple[str, ...]] | None = None

    def search(index: int, selected: tuple[ControlCandidate, ...], closed: frozenset[str]) -> None:
        nonlocal best
        cost = sum(item.cost for item in selected)
        ids = tuple(item.id for item in selected)
        if best is not None and (cost > best[0] or (cost == best[0] and len(ids) > best[1])):
            return
        if required <= closed:
            key = (cost, len(ids), ids)
            if best is None or key < best:
                best = key
            return
        if index == len(permitted):
            return
        item = permitted[index]
        search(index + 1, (*selected, item), closed | item.closes)
        search(index + 1, selected, closed)

    search(0, (), frozenset())
    return (best[2], best[0]) if best is not None else ((), 0)


def _brute_force_control_plan(
    required: frozenset[str], controls: tuple[ControlCandidate, ...]
) -> tuple[tuple[str, ...], int]:
    permitted = tuple(item for item in controls if item.permitted)
    best: tuple[int, int, tuple[str, ...]] | None = None
    for size in range(len(permitted) + 1):
        for selected in combinations(permitted, size):
            closed = frozenset().union(*(item.closes for item in selected))
            if not required <= closed:
                continue
            ids = tuple(sorted(item.id for item in selected))
            key = (sum(item.cost for item in selected), len(ids), ids)
            if best is None or key < best:
                best = key
    return (best[2], best[0]) if best is not None else ((), 0)


def decide_physical_outcome(
    outcome: PhysicalOutcome,
    controls: tuple[ControlCandidate, ...],
) -> PhysicalDecision:
    control_ids = [item.id for item in controls]
    if len(control_ids) != len(set(control_ids)):
        raise ValueError("duplicate control id")
    if len(controls) > 24:
        raise ValueError("exact transfer control limit exceeded")
    native_complete = outcome.primary_absent
    typed_complete = outcome.primary_absent and outcome.derivative_present is False
    if (
        not outcome.coverage_complete
        or outcome.derivative_present is None
        or outcome.recovery_recurrence is None
    ):
        verdict = "UNVERIFIED"
        witness: tuple[str, ...] | None = None
        required: frozenset[str] = frozenset()
    else:
        required = _required_risks(outcome)
        verdict = "INCOMPLETE" if required else "COMPLETE"
        if "primary" in required:
            witness = ("primary-object",)
        elif "derivative" in required:
            witness = ("materialized-derivative",)
        elif "recovery" in required:
            witness = ("recovery-carrier", "replay", "primary-object")
        else:
            witness = None
    selected_ids, selected_cost = _exact_control_plan(required, controls)
    oracle_ids, oracle_cost = _brute_force_control_plan(required, controls)
    return PhysicalDecision(
        native_complete=native_complete,
        typed_complete=typed_complete,
        erasemap_verdict=verdict,
        shortest_witness=witness,
        selected_control_ids=selected_ids,
        selected_cost=selected_cost,
        oracle_control_ids=oracle_ids,
        oracle_cost=oracle_cost,
        retained_loss=outcome.retained_after < outcome.retained_before,
    )


@dataclass(frozen=True, slots=True)
class TransferCaseRecord:
    case_id: str
    family: str
    seed: int
    fault_state: str
    truth: str
    native_complete: bool
    typed_complete: bool
    erasemap_verdict: str
    shortest_witness: tuple[str, ...] | None
    selected_control_ids: tuple[str, ...]
    selected_cost: int
    oracle_control_ids: tuple[str, ...]
    oracle_cost: int
    post_control_recurrence: bool
    retained_loss: bool
    core_sha256: str
    service_image: str
    service_version: str
    evidence_sha256: str
    process_observed: bool
    remediation_milliseconds: float
    bytes_rewritten: int

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ValueError(f"unknown family: {self.family}")
        if self.fault_state not in FAULT_STATES:
            raise ValueError(f"unknown fault state: {self.fault_state}")
        if self.case_id != expected_case_id(self.family, self.seed, self.fault_state):
            raise ValueError("case id does not match family, seed, and fault state")
        if self.truth != TRUTH_BY_FAULT[self.fault_state]:
            raise ValueError("truth does not match the frozen fault state")
        if self.erasemap_verdict not in VERDICTS:
            raise ValueError(f"unknown EraSeMap verdict: {self.erasemap_verdict}")
        if self.erasemap_verdict == "INCOMPLETE" and not self.shortest_witness:
            raise ValueError("incomplete EraSeMap verdict requires a shortest witness")
        if self.erasemap_verdict != "INCOMPLETE" and self.shortest_witness is not None:
            raise ValueError("only an incomplete EraSeMap verdict may carry a shortest witness")
        if len(self.selected_control_ids) != len(set(self.selected_control_ids)):
            raise ValueError("selected control ids must be unique")
        if len(self.oracle_control_ids) != len(set(self.oracle_control_ids)):
            raise ValueError("oracle control ids must be unique")
        if self.selected_cost < 0:
            raise ValueError("selected cost cannot be negative")
        if self.oracle_cost < 0:
            raise ValueError("oracle cost cannot be negative")
        if (
            self.selected_control_ids == self.oracle_control_ids
            and self.selected_cost != self.oracle_cost
        ):
            raise ValueError("matching control sets cannot have different oracle costs")
        _require_sha256(self.core_sha256, "core_sha256")
        _require_sha256(self.evidence_sha256, "evidence_sha256")
        if _IMAGE.fullmatch(self.service_image) is None:
            raise ValueError("immutable service image digest is required")
        if not self.service_version:
            raise ValueError("service version is required")
        if not math.isfinite(self.remediation_milliseconds) or self.remediation_milliseconds < 0:
            raise ValueError("remediation time cannot be negative or non-finite")
        if self.bytes_rewritten < 0:
            raise ValueError("bytes rewritten cannot be negative")

    @property
    def oracle_match(self) -> bool:
        return (
            self.selected_control_ids == self.oracle_control_ids
            and self.selected_cost == self.oracle_cost
        )

    def payload(self) -> dict[str, Any]:
        return asdict(self)


def transfer_record_from_payload(payload: Mapping[str, Any]) -> TransferCaseRecord:
    expected_fields = frozenset(TransferCaseRecord.__dataclass_fields__)
    if set(payload) != expected_fields:
        missing = sorted(expected_fields - set(payload))
        extra = sorted(set(payload) - expected_fields)
        raise ValueError(f"transfer record fields mismatch: missing={missing}, extra={extra}")
    string_fields = (
        "case_id",
        "family",
        "fault_state",
        "truth",
        "erasemap_verdict",
        "core_sha256",
        "service_image",
        "service_version",
        "evidence_sha256",
    )
    boolean_fields = (
        "native_complete",
        "typed_complete",
        "post_control_recurrence",
        "retained_loss",
        "process_observed",
    )
    integer_fields = ("seed", "selected_cost", "oracle_cost", "bytes_rewritten")
    if any(type(payload[field]) is not str for field in string_fields):
        raise ValueError("transfer record string field has the wrong type")
    if any(type(payload[field]) is not bool for field in boolean_fields):
        raise ValueError("transfer record boolean field has the wrong type")
    if any(type(payload[field]) is not int for field in integer_fields):
        raise ValueError("transfer record integer field has the wrong type")
    remediation_raw = payload["remediation_milliseconds"]
    if type(remediation_raw) not in {int, float}:
        raise ValueError("remediation milliseconds must be numeric")
    witness_raw = payload["shortest_witness"]
    if witness_raw is not None and not isinstance(witness_raw, list):
        raise ValueError("shortest witness must be a list or null")
    if witness_raw is not None and not all(type(item) is str for item in witness_raw):
        raise ValueError("shortest witness entries must be strings")
    selected_raw = payload["selected_control_ids"]
    oracle_raw = payload["oracle_control_ids"]
    if not isinstance(selected_raw, list) or not all(type(item) is str for item in selected_raw):
        raise ValueError("selected control ids must be a list of strings")
    if not isinstance(oracle_raw, list) or not all(type(item) is str for item in oracle_raw):
        raise ValueError("oracle control ids must be a list of strings")
    return TransferCaseRecord(
        case_id=payload["case_id"],
        family=payload["family"],
        seed=payload["seed"],
        fault_state=payload["fault_state"],
        truth=payload["truth"],
        native_complete=payload["native_complete"],
        typed_complete=payload["typed_complete"],
        erasemap_verdict=payload["erasemap_verdict"],
        shortest_witness=(tuple(witness_raw) if witness_raw is not None else None),
        selected_control_ids=tuple(selected_raw),
        selected_cost=payload["selected_cost"],
        oracle_control_ids=tuple(oracle_raw),
        oracle_cost=payload["oracle_cost"],
        post_control_recurrence=payload["post_control_recurrence"],
        retained_loss=payload["retained_loss"],
        core_sha256=payload["core_sha256"],
        service_image=payload["service_image"],
        service_version=payload["service_version"],
        evidence_sha256=payload["evidence_sha256"],
        process_observed=payload["process_observed"],
        remediation_milliseconds=float(remediation_raw),
        bytes_rewritten=payload["bytes_rewritten"],
    )


@dataclass(frozen=True, slots=True)
class GateResult:
    id: str
    observed: int | float | bool
    requirement: str
    passed: bool


@dataclass(frozen=True, slots=True)
class FamilyFalseComplete:
    family: str
    count: int


@dataclass(frozen=True, slots=True)
class TransferSummary:
    decision: str
    case_count: int
    family_count: int
    rotation_count: int
    erasemap_false_complete_count: int
    typed_false_complete_count: int
    native_false_complete_count: int
    native_false_complete_by_family: tuple[FamilyFalseComplete, ...]
    coverage_fail_closed_count: int
    post_control_recurrence_count: int
    retained_loss_count: int
    oracle_mismatch_count: int
    core_diff_count: int
    unobserved_process_count: int
    erasemap_safe_specificity: float
    typed_safe_specificity: float
    specificity_drop: float
    gates: tuple[GateResult, ...]

    def payload(self) -> dict[str, Any]:
        return asdict(self)


def _expected_matrix(protocol: Mapping[str, Any]) -> set[tuple[str, int, str]]:
    return {
        (str(family["id"]), int(seed), str(fault))
        for family in protocol["families"]
        for seed in protocol["seeds"]
        for fault in protocol["fault_states"]
    }


def _gate(id: str, observed: int | float | bool, requirement: str, passed: bool) -> GateResult:
    return GateResult(id, observed, requirement, passed)


def summarize_transfer(
    records: Sequence[TransferCaseRecord],
    protocol: Mapping[str, Any],
    protocol_core_sha256: str,
) -> TransferSummary:
    _require_sha256(protocol_core_sha256, "protocol_core_sha256")
    ids = [item.case_id for item in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case id")
    observed_matrix = {(item.family, item.seed, item.fault_state) for item in records}
    if observed_matrix != _expected_matrix(protocol):
        raise ValueError("observed case matrix does not equal the frozen protocol")

    configured_images = {str(item["id"]): str(item["image"]) for item in protocol["families"]}
    configured_versions = {str(item["id"]): str(item["version"]) for item in protocol["families"]}
    if any(item.service_image != configured_images[item.family] for item in records):
        raise ValueError("recorded service image differs from the frozen protocol")
    if any(item.service_version != configured_versions[item.family] for item in records):
        raise ValueError("recorded service version differs from the frozen protocol")

    unsafe = tuple(item for item in records if item.truth != "COMPLETE")
    safe = tuple(item for item in records if item.truth == "COMPLETE")
    erasemap_false_complete = sum(item.erasemap_verdict == "COMPLETE" for item in unsafe)
    typed_false_complete = sum(item.typed_complete for item in unsafe)
    native_false_complete = sum(item.native_complete for item in unsafe)
    by_family = tuple(
        FamilyFalseComplete(
            family,
            sum(
                item.native_complete and item.truth != "COMPLETE"
                for item in records
                if item.family == family
            ),
        )
        for family in FAMILIES
    )
    coverage_fail_closed = sum(
        item.fault_state == "coverage_fault" and item.erasemap_verdict == "UNVERIFIED"
        for item in records
    )
    post_control_recurrence = sum(item.post_control_recurrence for item in records)
    retained_loss = sum(item.retained_loss for item in records)
    oracle_mismatches = sum(not item.oracle_match for item in records)
    core_diffs = sum(item.core_sha256 != protocol_core_sha256 for item in records)
    unobserved = sum(not item.process_observed for item in records)
    era_specificity = (
        sum(item.erasemap_verdict == "COMPLETE" for item in safe) / len(safe) if safe else 0.0
    )
    typed_specificity = sum(item.typed_complete for item in safe) / len(safe) if safe else 0.0
    specificity_drop = max(0.0, typed_specificity - era_specificity)
    rotations = protocol["rotations"]
    rotation_count = sum(
        any(item.family == rotation["held_out_family"] for item in records)
        for rotation in rotations
    )
    configured_gates = protocol["gates"]
    minimum_native = int(configured_gates["native_false_complete_min_per_family"])
    gates = (
        _gate(
            "case_count",
            len(records),
            f"equals {configured_gates['case_count']}",
            len(records) == int(configured_gates["case_count"]),
        ),
        _gate(
            "family_count",
            len({item.family for item in records}),
            f"equals {configured_gates['family_count']}",
            len({item.family for item in records}) == int(configured_gates["family_count"]),
        ),
        _gate(
            "erasemap_false_complete",
            erasemap_false_complete,
            f"at most {configured_gates['erasemap_false_complete_max']}",
            erasemap_false_complete <= int(configured_gates["erasemap_false_complete_max"]),
        ),
        _gate(
            "coverage_fail_closed",
            coverage_fail_closed,
            f"equals {configured_gates['coverage_fault_unverified_count']}",
            coverage_fail_closed == int(configured_gates["coverage_fault_unverified_count"]),
        ),
        _gate(
            "post_control_recurrence",
            post_control_recurrence,
            f"at most {configured_gates['post_control_recurrence_max']}",
            post_control_recurrence <= int(configured_gates["post_control_recurrence_max"]),
        ),
        _gate(
            "retained_loss",
            retained_loss,
            f"at most {configured_gates['retained_loss_max']}",
            retained_loss <= int(configured_gates["retained_loss_max"]),
        ),
        _gate(
            "native_false_complete_each_family",
            min(item.count for item in by_family),
            f"at least {minimum_native} in every family",
            all(item.count >= minimum_native for item in by_family),
        ),
        _gate(
            "specificity_drop",
            specificity_drop,
            f"at most {configured_gates['specificity_drop_max']}",
            specificity_drop <= float(configured_gates["specificity_drop_max"]),
        ),
        _gate(
            "oracle_mismatch",
            oracle_mismatches,
            f"at most {configured_gates['oracle_mismatch_max']}",
            oracle_mismatches <= int(configured_gates["oracle_mismatch_max"]),
        ),
        _gate(
            "core_diff",
            core_diffs,
            f"at most {configured_gates['core_diff_max']}",
            core_diffs <= int(configured_gates["core_diff_max"]),
        ),
        _gate(
            "rotation_count",
            rotation_count,
            f"equals {configured_gates['rotation_count']}",
            rotation_count == int(configured_gates["rotation_count"]),
        ),
        _gate("process_observed", unobserved, "equals 0", unobserved == 0),
    )
    return TransferSummary(
        decision="PASS" if all(item.passed for item in gates) else "FAIL",
        case_count=len(records),
        family_count=len({item.family for item in records}),
        rotation_count=rotation_count,
        erasemap_false_complete_count=erasemap_false_complete,
        typed_false_complete_count=typed_false_complete,
        native_false_complete_count=native_false_complete,
        native_false_complete_by_family=by_family,
        coverage_fail_closed_count=coverage_fail_closed,
        post_control_recurrence_count=post_control_recurrence,
        retained_loss_count=retained_loss,
        oracle_mismatch_count=oracle_mismatches,
        core_diff_count=core_diffs,
        unobserved_process_count=unobserved,
        erasemap_safe_specificity=era_specificity,
        typed_safe_specificity=typed_specificity,
        specificity_drop=specificity_drop,
        gates=gates,
    )
