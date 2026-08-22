from __future__ import annotations

import json
import sys

import pytest

from pilot.validate import main, validate_manifest


def _manifest() -> dict[str, object]:
    digest = "sha256:" + "a" * 64
    return {
        "algorithm_commit": "0" * 40,
        "attestation": {
            "algorithm_unchanged_after_reveal": True,
            "no_project_author_label_access_before_freeze": True,
            "signed_by": "independent-evaluator",
        },
        "evidence": [
            {
                "artifact_id": f"artifact-{index}",
                "collected_by": "independent-evaluator",
                "contains_personal_data": False,
                "sha256": digest,
                "stage": stage,
                "system_id": "source" if index == 0 else "derived",
            }
            for index, stage in enumerate(
                ("before", "after_source_delete", "after_remediation")
            )
        ],
        "independent_evaluator": {
            "affiliation": "external-lab",
            "controlled_case_authorship": True,
            "controlled_labels": True,
            "name_or_pseudonym": "reviewer-1",
        },
        "organization_alias": "external-lab",
        "pilot_id": "pilot-001",
        "preregistered_at": "2026-08-22T00:00:00Z",
        "schema_version": "erasemap-production-pilot-v1",
        "systems": [
            {
                "connector": "SQL",
                "data_class": "source",
                "id": "source",
                "synthetic_or_consented": "synthetic",
            },
            {
                "connector": "filesystem",
                "data_class": "derived",
                "id": "derived",
                "synthetic_or_consented": "synthetic",
            },
        ],
    }


def test_ready_pilot_manifest() -> None:
    result = validate_manifest(_manifest())
    assert result["decision"] == "READY"
    assert result["evidence_stages"] == ["after_remediation", "after_source_delete", "before"]


def test_pilot_manifest_rejects_personal_data_artifact() -> None:
    manifest = _manifest()
    manifest["evidence"][0]["contains_personal_data"] = True
    with pytest.raises(ValueError, match="personal-data"):
        validate_manifest(manifest)


def test_pilot_manifest_cli(tmp_path, monkeypatch, capsys) -> None:
    manifest_path = tmp_path / "manifest.json"
    output_path = tmp_path / "validation.json"
    manifest_path.write_text(json.dumps(_manifest()))
    monkeypatch.setattr(
        sys,
        "argv",
        ["validate.py", str(manifest_path), "--output", str(output_path)],
    )
    assert main() == 0
    assert json.loads(output_path.read_text())["decision"] == "READY"
    monkeypatch.setattr(sys, "argv", ["validate.py", str(manifest_path)])
    assert main() == 0
    assert '"decision": "READY"' in capsys.readouterr().out


def test_pilot_manifest_rejects_invalid_contract_shapes() -> None:
    manifest = _manifest()
    manifest.pop("pilot_id")
    with pytest.raises(ValueError, match="schema mismatch"):
        validate_manifest(manifest)

    manifest = _manifest()
    manifest["schema_version"] = "unknown"
    with pytest.raises(ValueError, match="unsupported"):
        validate_manifest(manifest)

    manifest = _manifest()
    manifest["pilot_id"] = ""
    with pytest.raises(ValueError, match="pilot_id"):
        validate_manifest(manifest)

    manifest = _manifest()
    manifest["independent_evaluator"] = {}
    with pytest.raises(ValueError, match="independent_evaluator"):
        validate_manifest(manifest)

    manifest = _manifest()
    manifest["independent_evaluator"]["controlled_labels"] = False
    with pytest.raises(ValueError, match="control case authorship"):
        validate_manifest(manifest)

    manifest = _manifest()
    manifest["systems"] = manifest["systems"][:1]
    with pytest.raises(ValueError, match="at least two"):
        validate_manifest(manifest)

    manifest = _manifest()
    manifest["systems"][0].pop("connector")
    with pytest.raises(ValueError, match="system schema"):
        validate_manifest(manifest)

    manifest = _manifest()
    manifest["systems"][0]["synthetic_or_consented"] = "private"
    with pytest.raises(ValueError, match="synthetic or consented"):
        validate_manifest(manifest)

    manifest = _manifest()
    manifest["evidence"][0]["stage"] = "unknown"
    with pytest.raises(ValueError, match="stage"):
        validate_manifest(manifest)

    manifest = _manifest()
    manifest["evidence"] = []
    with pytest.raises(ValueError, match="evidence is required"):
        validate_manifest(manifest)

    manifest = _manifest()
    manifest["evidence"][0]["system_id"] = "unknown"
    with pytest.raises(ValueError, match="unknown system"):
        validate_manifest(manifest)

    manifest = _manifest()
    manifest["evidence"][0]["sha256"] = "invalid"
    with pytest.raises(ValueError, match="SHA-256"):
        validate_manifest(manifest)

    manifest = _manifest()
    manifest["evidence"][1]["artifact_id"] = manifest["evidence"][0]["artifact_id"]
    with pytest.raises(ValueError, match="duplicate evidence"):
        validate_manifest(manifest)

    manifest = _manifest()
    manifest["attestation"]["algorithm_unchanged_after_reveal"] = False
    assert validate_manifest(manifest)["decision"] == "INCOMPLETE"
