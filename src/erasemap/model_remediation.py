from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from erasemap.domain import ArtifactType, AuditResult, AuditStatus, ErasureGraph


class ModelRemediationMethod(StrEnum):
    NO_ACTION = "NO_ACTION"
    EXACT_RETRAIN = "EXACT_RETRAIN"
    INFLUENCE_SELECTIVE = "INFLUENCE_SELECTIVE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class ModelRemediationDecision:
    method: ModelRemediationMethod
    model_artifact_ids: tuple[str, ...]
    required_evidence: tuple[str, ...]
    reason: str


def select_model_remediation(
    graph: ErasureGraph,
    audit: AuditResult,
    *,
    exact_retrain_seconds: float | None,
    maximum_update_seconds: float | None,
    approximate_protocol_available: bool,
) -> ModelRemediationDecision:
    if exact_retrain_seconds is not None and exact_retrain_seconds < 0:
        raise ValueError("exact retrain time cannot be negative")
    if maximum_update_seconds is not None and maximum_update_seconds < 0:
        raise ValueError("maximum update time cannot be negative")
    residual_ids = {
        node_id for path in audit.residual_paths for node_id in path.node_ids
    }
    invalid_evidence_ids = {
        node_id for node_id, check in audit.evidence_checks if not check.valid
    }
    model_ids = tuple(
        sorted(
            node_id
            for node_id in residual_ids | invalid_evidence_ids
            if graph.nodes[node_id].type is ArtifactType.MODEL_INFLUENCE
        )
    )
    if not model_ids:
        return ModelRemediationDecision(
            ModelRemediationMethod.NO_ACTION,
            (),
            (),
            "no residual model influence is present in the audited lineage",
        )
    if audit.status is AuditStatus.UNVERIFIED:
        return ModelRemediationDecision(
            ModelRemediationMethod.BLOCKED,
            model_ids,
            ("valid model-lineage evidence",),
            "model lineage is unverified, so no unlearning claim can be selected",
        )
    if exact_retrain_seconds is None or maximum_update_seconds is None:
        return ModelRemediationDecision(
            ModelRemediationMethod.BLOCKED,
            model_ids,
            ("measured exact-retraining runtime", "declared remediation deadline"),
            "runtime evidence is required before selecting an update method",
        )
    if exact_retrain_seconds <= maximum_update_seconds:
        return ModelRemediationDecision(
            ModelRemediationMethod.EXACT_RETRAIN,
            model_ids,
            (
                "fresh checkpoint hash",
                "retained-utility evaluation",
                "privacy attack suite",
            ),
            "exact retraining fits the registered remediation deadline",
        )
    if approximate_protocol_available:
        return ModelRemediationDecision(
            ModelRemediationMethod.INFLUENCE_SELECTIVE,
            model_ids,
            (
                "primary endpoint equivalence to exact",
                "four-attack worst-case privacy result",
                "retained-utility confidence interval",
                "updated checkpoint hash",
            ),
            "exact retraining misses the deadline and a frozen approximate protocol exists",
        )
    return ModelRemediationDecision(
        ModelRemediationMethod.BLOCKED,
        model_ids,
        ("approved approximate-unlearning protocol",),
        "exact retraining misses the deadline and no approved alternative exists",
    )
