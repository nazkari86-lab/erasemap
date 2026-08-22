from __future__ import annotations

from dataclasses import dataclass

from erasemap.pcug_domain import ChannelDecision, ChannelResult, PCUGVerdict


@dataclass(frozen=True, slots=True)
class VerificationSummary:
    channels: tuple[ChannelResult, ...]
    verdict: PCUGVerdict
    failed_channels: tuple[str, ...]
    unknown_channels: tuple[str, ...]
    missing_channels: tuple[str, ...]


def _label(channel: ChannelResult) -> str:
    return f"{channel.name}@{channel.stratum}" if channel.stratum else channel.name


def upper_bound_channel(
    name: str,
    *,
    value: float,
    upper_bound: float,
    threshold: float,
    mandatory: bool = True,
    evidence_id: str = "",
    stratum: str = "",
) -> ChannelResult:
    decision = (
        ChannelDecision.PASS if upper_bound <= threshold else ChannelDecision.FAIL
    )
    return ChannelResult(
        name=name,
        value=value,
        upper_bound=upper_bound,
        threshold=threshold,
        decision=decision,
        mandatory=mandatory,
        evidence_id=evidence_id,
        stratum=stratum,
    )


def unknown_channel(
    name: str,
    *,
    threshold: float,
    mandatory: bool = True,
    evidence_id: str = "",
    stratum: str = "",
) -> ChannelResult:
    return ChannelResult(
        name=name,
        value=threshold,
        upper_bound=threshold,
        threshold=threshold,
        decision=ChannelDecision.UNKNOWN,
        mandatory=mandatory,
        evidence_id=evidence_id,
        stratum=stratum,
    )


def compose_channels(
    channels: tuple[ChannelResult, ...],
    *,
    required_names: frozenset[str] = frozenset(),
) -> VerificationSummary:
    ordered = tuple(sorted(channels, key=lambda item: (item.name, item.stratum)))
    keys = [(channel.name, channel.stratum) for channel in ordered]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate verification channel")

    mandatory = tuple(channel for channel in ordered if channel.mandatory)
    present_names = {channel.name for channel in mandatory}
    missing = tuple(sorted(required_names - present_names))
    failed = tuple(
        _label(channel)
        for channel in mandatory
        if channel.decision is ChannelDecision.FAIL
    )
    unknown = tuple(
        _label(channel)
        for channel in mandatory
        if channel.decision is ChannelDecision.UNKNOWN
    )

    if failed:
        verdict = PCUGVerdict.INCOMPLETE
    elif missing or unknown or not mandatory:
        verdict = PCUGVerdict.UNVERIFIED
    else:
        verdict = PCUGVerdict.COMPLETE
    return VerificationSummary(ordered, verdict, failed, unknown, missing)

