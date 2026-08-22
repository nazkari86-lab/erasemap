from __future__ import annotations

from dataclasses import dataclass

from erasemap.pcug_domain import (
    CDCAction,
    CDCProtocol,
    ChannelDecision,
    ChannelResult,
    EdgeKind,
    EdgeState,
    PCUGEdge,
    PCUGGraph,
    PCUGNode,
    PCUGVerdict,
    Transition,
    TransitionTarget,
)
from erasemap.source_lock import SourceExcerpt, SourceManifest


@dataclass(frozen=True, slots=True)
class ExternalCase:
    id: str
    family: str
    mapping_ids: tuple[str, ...]
    graph: PCUGGraph
    protocol: CDCProtocol
    actions: tuple[CDCAction, ...]
    truth_verdict: PCUGVerdict
    expected_path: tuple[str, ...] | None


_KINDS = {
    "identity": ("subscriber_account", "biometric_reference"),
    "provenance": ("primary_entity", "derived_entity"),
    "search": ("search_index", "snapshot"),
    "ml": ("run_metadata", "artifact_store_object"),
    "recovery": ("database_record", "wal_archive"),
}


def _build_case(source: SourceExcerpt, variant: int) -> ExternalCase:
    source_kind, sink_kind = _KINDS[source.family]
    subject = f"holdout-subject-{variant:02d}"
    source_id = f"{source.family}-source-{variant:02d}"
    middle_id = f"{source.family}-materialized-{variant:02d}"
    sink_id = f"{source.family}-sink-{variant:02d}"
    mode = variant % 5
    sink_state = (
        EdgeState.CLOSED
        if mode == 0
        else EdgeState.UNKNOWN
        if mode == 4
        else EdgeState.ACTIVE
    )
    final_edge_state = (
        EdgeState.CLOSED
        if mode == 0
        else EdgeState.UNKNOWN
        if mode == 4
        else EdgeState.ACTIVE
    )
    nodes = (
        PCUGNode(source_id, source_kind, subject, EdgeState.CLOSED, evidence_id="source-erased"),
        PCUGNode(
            middle_id,
            f"{source_kind}_projection",
            subject,
            EdgeState.CLOSED if mode == 0 else EdgeState.ACTIVE,
            evidence_id="projection-erased" if mode == 0 else "",
        ),
        PCUGNode(
            sink_id,
            sink_kind,
            subject,
            sink_state,
            active_sink=sink_state is not EdgeState.CLOSED,
            evidence_id="sink-erased" if mode == 0 else "",
        ),
    )
    edges = (
        PCUGEdge(
            source_id,
            middle_id,
            EdgeKind.MATERIAL,
            EdgeState.CLOSED if mode == 0 else EdgeState.ACTIVE,
            request_scoped=True,
            subject_id=subject,
            evidence_id="edge-erased" if mode == 0 else "",
        ),
        PCUGEdge(
            middle_id,
            sink_id,
            EdgeKind.MATERIAL,
            final_edge_state,
            request_scoped=True,
            subject_id=subject,
            evidence_id="sink-edge-erased" if mode == 0 else "",
        ),
    )
    graph = PCUGGraph(
        nodes,
        edges,
        (
            ChannelResult(
                name="deletion_evidence",
                value=0.0,
                upper_bound=0.0,
                threshold=0.1,
                decision=ChannelDecision.PASS,
                mandatory=True,
                evidence_id="source-derived-verifier",
                stratum=source.family,
            ),
        ),
    )
    protocol = CDCProtocol(
        request_id=f"external-{source.family}-{variant:02d}",
        subject_id=subject,
        source_ids=frozenset({source_id}),
        sink_ids=frozenset({sink_id}),
        mandatory_channels=frozenset({"deletion_evidence"}),
    )
    actions = (
        CDCAction(
            id=f"erase-{source.family}-projection-{variant:02d}",
            cost=2 + variant % 3,
            transitions=(
                Transition(
                    middle_id,
                    EdgeState.CLOSED,
                    "projection-delete-replay",
                    TransitionTarget.NODE,
                ),
                Transition(edges[0].id, EdgeState.CLOSED, "derivation-delete-replay"),
            ),
        ),
        CDCAction(
            id=f"erase-{source.family}-sink-{variant:02d}",
            cost=3 + variant % 4,
            transitions=(
                Transition(
                    sink_id,
                    EdgeState.CLOSED,
                    "sink-delete-replay",
                    TransitionTarget.NODE,
                ),
                Transition(edges[1].id, EdgeState.CLOSED, "sink-edge-delete-replay"),
            ),
        ),
    )
    if mode == 0:
        truth = PCUGVerdict.COMPLETE
        path = None
    elif mode == 4:
        truth = PCUGVerdict.UNVERIFIED
        path = (sink_id,)
    else:
        truth = PCUGVerdict.INCOMPLETE
        path = (sink_id,)
    return ExternalCase(
        id=f"{source.family}-{variant:02d}",
        family=source.family,
        mapping_ids=tuple(mapping.id for mapping in source.mappings),
        graph=graph,
        protocol=protocol,
        actions=actions,
        truth_verdict=truth,
        expected_path=path,
    )


def build_source_cases(manifest: SourceManifest) -> tuple[ExternalCase, ...]:
    families = {source.family for source in manifest.sources}
    if families != set(_KINDS):
        raise ValueError("all five external source families are required")
    cases = tuple(
        _build_case(source, variant)
        for source in sorted(manifest.sources, key=lambda item: item.family)
        for variant in range(25)
    )
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("external case ids must be unique")
    return cases
