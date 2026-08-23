from erasemap.rse_conformance import COST_CATALOGS, run_rse_conformance


def test_rse_conformance_covers_frozen_finite_domain() -> None:
    result = run_rse_conformance()

    assert result["carrier_subsets"] == 16
    assert result["permission_masks"] == 64
    assert result["cost_catalogs"] == len(COST_CATALOGS) == 8
    assert result["input_orderings"] == 2
    assert result["configurations"] == 16_384
    assert result["mismatches"] == 0
