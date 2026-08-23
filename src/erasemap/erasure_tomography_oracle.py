from __future__ import annotations

from dataclasses import dataclass

from erasemap.erasure_tomography import (
    ProbeDesign,
    Support,
    TomographyEvidence,
    TomographyVerdict,
)


@dataclass(frozen=True, slots=True)
class OracleReport:
    verdict: TomographyVerdict
    support: Support
    admissible_supports: tuple[Support, ...]
    distance: int | None


def oracle_decode(
    design: ProbeDesign,
    observations: tuple[bool, ...],
    evidence: TomographyEvidence,
) -> OracleReport:
    if len(observations) != len(design.rows):
        raise ValueError("observation count must match probe rows")
    evidence_bits = (
        evidence.catalogue_complete,
        evidence.workflows_executed,
        evidence.subjects_isolated,
        evidence.recurrence_observable,
        evidence.observations_complete,
    )
    if not all(evidence_bits):
        return OracleReport(TomographyVerdict.UNVERIFIED, (), (), None)

    matches: list[tuple[Support, int]] = []
    mechanism_count = len(design.mechanism_ids)
    for support_mask in range(1 << mechanism_count):
        if support_mask.bit_count() > design.max_failures:
            continue
        predicted_mask = 0
        for row_index, row in enumerate(design.rows):
            row_mask = sum(
                (1 << column_index) if active else 0
                for column_index, active in enumerate(row)
            )
            if row_mask & support_mask:
                predicted_mask |= 1 << row_index
        observed_mask = sum(
            (1 << row_index) if active else 0
            for row_index, active in enumerate(observations)
        )
        distance = (predicted_mask ^ observed_mask).bit_count()
        if distance <= design.error_budget:
            support = tuple(
                mechanism_id
                for index, mechanism_id in enumerate(design.mechanism_ids)
                if support_mask & (1 << index)
            )
            matches.append((support, distance))

    matches.sort(key=lambda item: (len(item[0]), item[0]))
    if not matches:
        return OracleReport(TomographyVerdict.OUT_OF_MODEL, (), (), None)
    supports = tuple(item[0] for item in matches)
    if len(matches) > 1:
        return OracleReport(TomographyVerdict.AMBIGUOUS, (), supports, None)
    support, distance = matches[0]
    verdict = (
        TomographyVerdict.NO_OBSERVED_RECURRENCE
        if not support
        else TomographyVerdict.LOCALIZED
    )
    return OracleReport(verdict, support, supports, distance)
