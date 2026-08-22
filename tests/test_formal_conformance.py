from erasemap.formal_conformance import run_formal_conformance


def test_formal_conformance_small_domain() -> None:
    report = run_formal_conformance(cost_levels=2)
    assert report["catalogs"] == 64
    assert report["ordering_runs"] == 384
    assert report["mismatches"] == 0


def test_formal_conformance_rejects_empty_cost_domain() -> None:
    try:
        run_formal_conformance(cost_levels=0)
    except ValueError as error:
        assert str(error) == "cost_levels must be positive"
    else:
        raise AssertionError("expected ValueError")
