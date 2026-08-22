from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from erasemap.multiview_verifier import (
    VerificationSummary,
    compose_channels,
    unknown_channel,
    upper_bound_channel,
)
from erasemap.pcug_domain import ChannelResult, PCUGVerdict


@dataclass(frozen=True, slots=True)
class ModelStratumEvidence:
    stratum: str
    dataset: str
    source_hash: str
    protocol_hash: str
    trial_count: int
    reported_success: bool
    channels: tuple[ChannelResult, ...]

    def __post_init__(self) -> None:
        if not self.stratum or not self.dataset or not self.source_hash or not self.protocol_hash:
            raise ValueError("model evidence identifiers are required")
        if self.trial_count <= 0:
            raise ValueError("model evidence trial count must be positive")


_STRATA = {
    "development": "development",
    "evaluation": "locked_internal",
    "external": "content_unseen",
}


def _object(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")
    return cast(Mapping[str, Any], value)


def _number(value: object, location: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{location} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{location} must be finite")
    return result


def _integer(value: object, location: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{location} must be an integer")
    return value


def _boolean(value: object, location: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{location} must be a boolean")
    return value


def _string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{location} must be a non-empty string")
    return value


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _unknown_channels(stratum: str, evidence_id: str) -> tuple[ChannelResult, ...]:
    return (
        unknown_channel(
            "forgotten_mse_ratio",
            threshold=1.0,
            evidence_id=evidence_id,
            stratum=stratum,
        ),
        unknown_channel(
            "privacy_advantage_gap",
            threshold=0.10,
            evidence_id=evidence_id,
            stratum=stratum,
        ),
        unknown_channel(
            "retained_auc_loss",
            threshold=0.01,
            evidence_id=evidence_id,
            stratum=stratum,
        ),
    )


def _channels(
    payload: Mapping[str, Any],
    *,
    stratum: str,
    evidence_id: str,
) -> tuple[ChannelResult, ...]:
    endpoints = _object(payload.get("endpoints"), "summary.endpoints")
    summary = _object(payload.get("summary"), "summary.summary")
    candidate = _object(summary.get("deletion_matched_restart"), "summary.candidate")
    exact = _object(summary.get("exact_retrain"), "summary.exact")
    candidate_auc = _object(
        candidate.get("retained_verification_auc"), "summary.candidate.retained_auc"
    )
    exact_auc = _object(exact.get("retained_verification_auc"), "summary.exact.retained_auc")
    candidate_ci_value = candidate_auc.get("ci95")
    exact_ci_value = exact_auc.get("ci95")
    if not isinstance(candidate_ci_value, list) or len(candidate_ci_value) != 2:
        raise ValueError("candidate retained AUC ci95 must have two values")
    if not isinstance(exact_ci_value, list) or len(exact_ci_value) != 2:
        raise ValueError("exact retained AUC ci95 must have two values")

    retained_loss = _number(exact_auc.get("mean"), "exact retained AUC mean") - _number(
        candidate_auc.get("mean"), "candidate retained AUC mean"
    )
    retained_upper = _number(exact_ci_value[1], "exact retained AUC upper") - _number(
        candidate_ci_value[0], "candidate retained AUC lower"
    )
    return (
        upper_bound_channel(
            "forgotten_mse_ratio",
            value=_number(
                endpoints.get("forgotten_embedding_mse_ratio_to_stale"),
                "forgotten MSE ratio",
            ),
            upper_bound=_number(
                endpoints.get("forgotten_embedding_mse_ratio_to_stale"),
                "forgotten MSE ratio",
            ),
            threshold=1.0,
            evidence_id=evidence_id,
            stratum=stratum,
        ),
        upper_bound_channel(
            "privacy_advantage_gap",
            value=_number(
                endpoints.get("max_attack_paired_advantage_upper_ci"),
                "privacy upper confidence bound",
            ),
            upper_bound=_number(
                endpoints.get("max_attack_paired_advantage_upper_ci"),
                "privacy upper confidence bound",
            ),
            threshold=0.10,
            evidence_id=evidence_id,
            stratum=stratum,
        ),
        upper_bound_channel(
            "retained_auc_loss",
            value=max(0.0, retained_loss),
            upper_bound=max(0.0, retained_upper),
            threshold=0.01,
            evidence_id=evidence_id,
            stratum=stratum,
        ),
    )


def import_v3_evidence(
    summary_paths: Sequence[str | Path],
    *,
    protocol_path: str | Path,
) -> tuple[ModelStratumEvidence, ...]:
    protocol_raw = Path(protocol_path).read_bytes()
    protocol_hash = _sha256(protocol_raw)
    imported: list[ModelStratumEvidence] = []
    seen: set[str] = set()
    for path_value in summary_paths:
        path = Path(path_value)
        raw = path.read_bytes()
        try:
            decoded: object = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid model summary JSON: {error.msg}") from error
        payload = _object(decoded, "summary")
        split = _string(payload.get("split"), "summary.split")
        if split not in _STRATA:
            raise ValueError(f"unsupported model evidence split: {split}")
        stratum = _STRATA[split]
        if stratum in seen:
            raise ValueError(f"duplicate model evidence stratum: {stratum}")
        seen.add(stratum)
        dataset = _object(payload.get("dataset"), "summary.dataset")
        manifests = _object(payload.get("manifests"), "summary.manifests")
        claimed_protocol = _string(manifests.get("protocol"), "summary protocol hash")
        source_hash = _sha256(raw)
        channels = (
            _channels(payload, stratum=stratum, evidence_id=source_hash)
            if claimed_protocol == protocol_hash
            else _unknown_channels(stratum, source_hash)
        )
        reported_success = _boolean(payload.get("success"), "summary.success")
        computed = compose_channels(channels)
        if claimed_protocol == protocol_hash and (
            (computed.verdict is PCUGVerdict.COMPLETE) != reported_success
        ):
            raise ValueError("reported success disagrees with recomputed registered channels")
        imported.append(
            ModelStratumEvidence(
                stratum=stratum,
                dataset=_string(dataset.get("name"), "summary.dataset.name"),
                source_hash=source_hash,
                protocol_hash=claimed_protocol,
                trial_count=_integer(payload.get("trial_count"), "summary.trial_count"),
                reported_success=reported_success,
                channels=channels,
            )
        )
    return tuple(imported)


def compose_model_strata(
    evidence: Sequence[ModelStratumEvidence],
) -> VerificationSummary:
    if not evidence:
        return compose_channels(())
    strata = [item.stratum for item in evidence]
    if len(strata) != len(set(strata)):
        raise ValueError("duplicate model evidence stratum")
    channels = tuple(channel for item in evidence for channel in item.channels)
    return compose_channels(channels)

