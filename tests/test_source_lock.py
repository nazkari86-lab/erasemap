from __future__ import annotations

import json
from pathlib import Path

import pytest

from erasemap.source_lock import load_source_manifest

MANIFEST = Path("benchmark/external-sources-v1.json")


def test_public_source_manifest_is_valid_and_heterogeneous() -> None:
    manifest = load_source_manifest(MANIFEST)
    assert len(manifest.sources) == 5
    assert len({source.family for source in manifest.sources}) == 5
    assert manifest.digest.startswith("sha256:")


@pytest.mark.parametrize("mutation", ["hash", "url", "relation", "extra", "duplicate"])
def test_source_manifest_tampering_fails_closed(tmp_path: Path, mutation: str) -> None:
    payload = json.loads(MANIFEST.read_text())
    if mutation == "hash":
        payload["sources"][0]["excerpt"] += " changed"
    elif mutation == "url":
        payload["sources"][0]["url"] = "http://example.test"
    elif mutation == "relation":
        payload["sources"][0]["mappings"][0]["relation"] = "TRUST_ME"
    elif mutation == "extra":
        payload["surprise"] = True
    else:
        payload["sources"][1]["mappings"][0]["id"] = payload["sources"][0]["mappings"][0]["id"]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        load_source_manifest(path)
