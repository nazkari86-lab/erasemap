from dataclasses import replace

from erasemap.baselines import FlatChecklist, ReceiptOnly, UntypedTraversal
from erasemap.domain import ArtifactState, ArtifactType, Evidence, EvidenceKind
from erasemap.generator import FaultKind, generate_case


def test_receipt_only_trusts_a_valid_signature_despite_residual() -> None:
    case = generate_case(seed=1, node_count=10, faults=(FaultKind.ORPHANED_TEMPLATE,))

    decision = ReceiptOnly().assess(case, now_epoch=100)

    assert decision.declared_complete
    assert not decision.detected_artifact_ids


def test_checklist_cannot_see_an_unlisted_store() -> None:
    case = generate_case(seed=2, node_count=10, faults=(FaultKind.STALE_CACHE,))
    method = FlatChecklist(
        checked_types=frozenset(
            {ArtifactType.SOURCE_RECORD, ArtifactType.BIOMETRIC_TEMPLATE}
        )
    )

    decision = method.assess(case, now_epoch=100)

    assert decision.declared_complete


def test_untyped_traversal_accepts_wrong_evidence_kind() -> None:
    case = generate_case(seed=3, node_count=10, faults=())
    template_id = next(
        node.id
        for node in case.graph.nodes.values()
        if node.type is ArtifactType.BIOMETRIC_TEMPLATE
    )
    wrong = Evidence(
        id="generic-statement",
        artifact_id=template_id,
        kind=EvidenceKind.SIGNED_STATEMENT,
        valid_signature=True,
        issued_epoch=10,
        expires_epoch=1_000,
    )
    evidence = dict(case.evidence)
    evidence[template_id] = wrong
    modified = replace(case, evidence=evidence)

    decision = UntypedTraversal().assess(modified, now_epoch=100)

    assert decision.declared_complete
    assert case.graph.nodes[template_id].state is ArtifactState.ERASED
