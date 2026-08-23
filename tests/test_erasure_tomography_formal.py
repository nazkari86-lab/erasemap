from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_formal_tomography_boundary_is_imported_and_contains_no_placeholders() -> None:
    source = (ROOT / "EraseMapFormal/ErasureTomography.lean").read_text()
    root = (ROOT / "EraseMapFormal.lean").read_text()

    assert "theorem unique_decode_of_separated" in source
    assert "theorem ambiguous_without_separation" in source
    assert "theorem localized_controls_safe_for_listed_mechanisms" in source
    assert "catalogueClosed" in source
    assert "observationSound" in source
    assert "import EraseMapFormal.ErasureTomography" in root
    assert "sorry" not in source.lower()
    assert "admit" not in source.lower()
    assert "axiom " not in source.lower()
