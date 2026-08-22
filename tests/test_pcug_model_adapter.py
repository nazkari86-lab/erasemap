import json
from pathlib import Path

from erasemap.pcug_domain import PCUGVerdict
from erasemap.pcug_model_adapter import compose_model_strata, import_v3_evidence

RESULTS = Path("benchmark/results/task-agnostic-v3")
PROTOCOL = Path("benchmark/task-agnostic-v3.json")


def _paths() -> tuple[Path, ...]:
    return tuple(
        RESULTS / f"{name}-summary.json"
        for name in ("development", "evaluation", "external")
    )


def test_v3_import_preserves_dataset_strata() -> None:
    evidence = import_v3_evidence(_paths(), protocol_path=PROTOCOL)
    assert tuple(item.stratum for item in evidence) == (
        "development",
        "locked_internal",
        "content_unseen",
    )


def test_failed_external_stratum_cannot_be_hidden_by_average() -> None:
    evidence = import_v3_evidence(_paths(), protocol_path=PROTOCOL)
    summary = compose_model_strata(evidence)
    assert summary.verdict is PCUGVerdict.INCOMPLETE
    assert "retained_auc_loss@content_unseen" in summary.failed_channels


def test_internal_passes_remain_visible_separately() -> None:
    evidence = import_v3_evidence(_paths()[:2], protocol_path=PROTOCOL)
    assert compose_model_strata(evidence).verdict is PCUGVerdict.COMPLETE


def test_unknown_protocol_hash_is_unverified(tmp_path: Path) -> None:
    payload = json.loads(_paths()[0].read_text())
    payload["manifests"]["protocol"] = "sha256:unregistered"
    result = tmp_path / "summary.json"
    result.write_text(json.dumps(payload))
    evidence = import_v3_evidence((result,), protocol_path=PROTOCOL)
    assert compose_model_strata(evidence).verdict is PCUGVerdict.UNVERIFIED


def test_source_hash_is_recorded() -> None:
    evidence = import_v3_evidence((_paths()[0],), protocol_path=PROTOCOL)
    assert evidence[0].source_hash.startswith("sha256:")
    assert len(evidence[0].source_hash) == 71

