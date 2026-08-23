from __future__ import annotations

import itertools
from dataclasses import dataclass
from enum import StrEnum


class TomographyVerdict(StrEnum):
    NO_OBSERVED_RECURRENCE = "NO_OBSERVED_RECURRENCE"
    LOCALIZED = "LOCALIZED"
    AMBIGUOUS = "AMBIGUOUS"
    OUT_OF_MODEL = "OUT_OF_MODEL"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True, slots=True)
class ProbeDesign:
    mechanism_ids: tuple[str, ...]
    rows: tuple[tuple[bool, ...], ...]
    max_failures: int
    error_budget: int

    def __post_init__(self) -> None:
        if not self.mechanism_ids:
            raise ValueError("mechanism ids must be non-empty")
        if any(not item for item in self.mechanism_ids):
            raise ValueError("mechanism ids must not contain empty values")
        if len(set(self.mechanism_ids)) != len(self.mechanism_ids):
            raise ValueError("mechanism ids must be unique")
        if not self.rows:
            raise ValueError("at least one probe row is required")
        if any(len(row) != len(self.mechanism_ids) for row in self.rows):
            raise ValueError("every probe row must match the mechanism catalogue")
        if self.max_failures < 0 or self.max_failures > len(self.mechanism_ids):
            raise ValueError("invalid maximum failure count")
        if self.error_budget < 0:
            raise ValueError("error budget cannot be negative")


@dataclass(frozen=True, slots=True)
class TomographyEvidence:
    catalogue_complete: bool
    workflows_executed: bool
    subjects_isolated: bool
    recurrence_observable: bool
    observations_complete: bool
    sparsity_bound_verified: bool
    noise_bound_verified: bool
    stable_behavior: bool
    synthetic_subjects_only: bool

    @classmethod
    def complete(cls) -> TomographyEvidence:
        return cls(True, True, True, True, True, True, True, True, True)

    @property
    def valid(self) -> bool:
        return all(
            (
                self.catalogue_complete,
                self.workflows_executed,
                self.subjects_isolated,
                self.recurrence_observable,
                self.observations_complete,
                self.sparsity_bound_verified,
                self.noise_bound_verified,
                self.stable_behavior,
                self.synthetic_subjects_only,
            )
        )


Support = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TomographyCertificate:
    support_count: int
    minimum_outcome_distance: int | None
    uniquely_decodable: bool
    indistinguishable_support_pairs: tuple[tuple[Support, Support], ...]


@dataclass(frozen=True, slots=True)
class TomographyReport:
    verdict: TomographyVerdict
    support: Support
    admissible_supports: tuple[Support, ...]
    distance: int | None
    certificate: TomographyCertificate


def enumerate_supports(design: ProbeDesign) -> tuple[Support, ...]:
    return tuple(
        support
        for size in range(design.max_failures + 1)
        for support in itertools.combinations(design.mechanism_ids, size)
    )


def predict(design: ProbeDesign, support: Support) -> tuple[bool, ...]:
    unknown = set(support) - set(design.mechanism_ids)
    if unknown:
        raise ValueError(f"support contains unknown mechanism: {min(unknown)}")
    if len(support) != len(set(support)):
        raise ValueError("support contains duplicate mechanisms")
    active_indexes = {
        index for index, mechanism_id in enumerate(design.mechanism_ids)
        if mechanism_id in support
    }
    return tuple(any(row[index] for index in active_indexes) for row in design.rows)


def hamming_distance(left: tuple[bool, ...], right: tuple[bool, ...]) -> int:
    if len(left) != len(right):
        raise ValueError("Hamming inputs must have equal length")
    return sum(a is not b for a, b in zip(left, right, strict=True))


def certify_design(design: ProbeDesign) -> TomographyCertificate:
    supports = enumerate_supports(design)
    outcomes = tuple(predict(design, support) for support in supports)
    pairs: list[tuple[Support, Support]] = []
    distances: list[int] = []
    for left_index, left_support in enumerate(supports):
        for right_index in range(left_index + 1, len(supports)):
            distance = hamming_distance(outcomes[left_index], outcomes[right_index])
            distances.append(distance)
            if distance <= 2 * design.error_budget:
                pairs.append((left_support, supports[right_index]))
    minimum = min(distances) if distances else None
    return TomographyCertificate(
        support_count=len(supports),
        minimum_outcome_distance=minimum,
        uniquely_decodable=not pairs,
        indistinguishable_support_pairs=tuple(pairs),
    )


def decode(
    design: ProbeDesign,
    observations: tuple[bool, ...],
    evidence: TomographyEvidence,
) -> TomographyReport:
    if len(observations) != len(design.rows):
        raise ValueError("observation count must match probe rows")
    certificate = certify_design(design)
    if not evidence.valid:
        return TomographyReport(
            TomographyVerdict.UNVERIFIED,
            (),
            (),
            None,
            certificate,
        )

    matches = tuple(
        (support, hamming_distance(predict(design, support), observations))
        for support in enumerate_supports(design)
    )
    admissible = tuple(
        support for support, distance in matches if distance <= design.error_budget
    )
    if not admissible:
        return TomographyReport(
            TomographyVerdict.OUT_OF_MODEL,
            (),
            (),
            None,
            certificate,
        )
    if len(admissible) > 1:
        return TomographyReport(
            TomographyVerdict.AMBIGUOUS,
            (),
            admissible,
            None,
            certificate,
        )

    support = admissible[0]
    selected_distance = next(
        distance for candidate, distance in matches if candidate == support
    )
    verdict = (
        TomographyVerdict.NO_OBSERVED_RECURRENCE
        if not support
        else TomographyVerdict.LOCALIZED
    )
    return TomographyReport(
        verdict,
        support,
        admissible,
        selected_distance,
        certificate,
    )
