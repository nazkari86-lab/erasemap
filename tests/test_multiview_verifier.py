import pytest

from erasemap.multiview_verifier import compose_channels, upper_bound_channel
from erasemap.pcug_domain import ChannelDecision, ChannelResult, PCUGVerdict


def channel(
    name: str,
    decision: ChannelDecision,
    *,
    mandatory: bool = True,
) -> ChannelResult:
    return ChannelResult(name, 0.05, 0.08, 0.10, decision, mandatory)


def test_mandatory_unknown_prevents_complete() -> None:
    result = compose_channels(
        (
            channel("storage", ChannelDecision.PASS),
            channel("mia", ChannelDecision.UNKNOWN),
        )
    )
    assert result.verdict is PCUGVerdict.UNVERIFIED
    assert result.unknown_channels == ("mia",)


def test_any_mandatory_failure_is_incomplete() -> None:
    result = compose_channels(
        (
            channel("storage", ChannelDecision.PASS),
            channel("mia", ChannelDecision.FAIL),
        )
    )
    assert result.verdict is PCUGVerdict.INCOMPLETE
    assert result.failed_channels == ("mia",)


def test_optional_failure_does_not_override_mandatory_pass() -> None:
    result = compose_channels(
        (
            channel("storage", ChannelDecision.PASS),
            channel("exploratory", ChannelDecision.FAIL, mandatory=False),
        )
    )
    assert result.verdict is PCUGVerdict.COMPLETE


def test_missing_required_channel_is_unverified() -> None:
    result = compose_channels(
        (channel("storage", ChannelDecision.PASS),),
        required_names=frozenset({"storage", "mia"}),
    )
    assert result.verdict is PCUGVerdict.UNVERIFIED
    assert result.missing_channels == ("mia",)


def test_upper_bound_constructor_recomputes_decision() -> None:
    passed = upper_bound_channel("mia", value=0.05, upper_bound=0.09, threshold=0.1)
    failed = upper_bound_channel("mia", value=0.05, upper_bound=0.11, threshold=0.1)
    assert passed.decision is ChannelDecision.PASS
    assert failed.decision is ChannelDecision.FAIL


def test_duplicate_name_and_stratum_is_rejected() -> None:
    duplicate = channel("mia", ChannelDecision.PASS)
    with pytest.raises(ValueError, match="duplicate"):
        compose_channels((duplicate, duplicate))

