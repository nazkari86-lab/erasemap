from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import torch
import torch.nn.functional as functional
from torch import Tensor


def _masked_mean(values: Tensor, mask: Tensor) -> Tensor:
    if mask.dtype is not torch.bool or mask.shape != values.shape:
        raise ValueError("answer mask must be boolean and match token dimensions")
    if not bool(mask.any()):
        raise ValueError("answer mask must select at least one token")
    result = values.masked_select(mask).mean()
    if not bool(torch.isfinite(result)):
        raise ValueError("masked loss is nonfinite")
    return result


def _reference_kl(candidate: Tensor, reference: Tensor, temperature: float) -> Tensor:
    if candidate.shape != reference.shape or candidate.ndim < 2:
        raise ValueError("candidate and reference logits must have identical token shapes")
    reference_probabilities = functional.softmax(reference.detach() / temperature, dim=-1)
    candidate_log_probabilities = functional.log_softmax(candidate / temperature, dim=-1)
    return (
        functional.kl_div(
            candidate_log_probabilities,
            reference_probabilities,
            reduction="none",
        ).sum(dim=-1)
        * temperature**2
    )


def bounded_rbep_loss(
    *,
    candidate_forget: Tensor,
    base_forget: Tensor,
    candidate_keep: Tensor,
    target_keep: Tensor,
    keep_labels: Tensor,
    answer_mask: Tensor,
    temperature: float,
    keep_weight: float,
    cross_entropy_weight: float,
) -> Tensor:
    if not math.isfinite(temperature) or temperature <= 0.0:
        raise ValueError("temperature must be finite and positive")
    if not math.isfinite(keep_weight) or keep_weight < 0.0:
        raise ValueError("keep_weight must be finite and nonnegative")
    if not math.isfinite(cross_entropy_weight) or cross_entropy_weight < 0.0:
        raise ValueError("cross_entropy_weight must be finite and nonnegative")
    forget_kl = _reference_kl(candidate_forget, base_forget, temperature)
    keep_kl = _reference_kl(candidate_keep, target_keep, temperature)
    if answer_mask.shape != forget_kl.shape or answer_mask.shape != keep_kl.shape:
        raise ValueError("answer mask must match forget and keep token dimensions")
    forget_loss = _masked_mean(forget_kl, answer_mask)
    keep_loss = _masked_mean(keep_kl, answer_mask)
    if keep_labels.shape != answer_mask.shape:
        raise ValueError("keep labels must match answer mask")
    if cross_entropy_weight:
        token_ce = functional.cross_entropy(
            candidate_keep.reshape(-1, candidate_keep.shape[-1]),
            keep_labels.reshape(-1),
            reduction="none",
        ).reshape(keep_labels.shape)
        keep_loss = keep_loss + cross_entropy_weight * _masked_mean(token_ce, answer_mask)
    result = forget_loss + keep_weight * keep_loss
    if not bool(torch.isfinite(result)):
        raise ValueError("RBEP loss is nonfinite")
    return result


def _validate_adapter_pair(
    target: Mapping[str, Tensor], candidate: Mapping[str, Tensor]
) -> tuple[str, ...]:
    if set(target) != set(candidate):
        raise ValueError("adapter keys must match")
    if not target:
        raise ValueError("adapter state must not be empty")
    keys = tuple(sorted(target))
    for key in keys:
        if target[key].shape != candidate[key].shape:
            raise ValueError(f"adapter tensor shape mismatch for {key}")
        if target[key].device != candidate[key].device:
            raise ValueError(f"adapter tensor device mismatch for {key}")
        if target[key].dtype != candidate[key].dtype:
            raise ValueError(f"adapter tensor dtype mismatch for {key}")
        if not bool(torch.isfinite(target[key]).all()) or not bool(
            torch.isfinite(candidate[key]).all()
        ):
            raise ValueError(f"adapter tensor {key} is nonfinite")
    return keys


def _whole_norm(values: Mapping[str, Tensor], keys: tuple[str, ...]) -> Tensor:
    device = values[keys[0]].device
    squares = torch.zeros((), dtype=torch.float64, device=device)
    for key in keys:
        squares = squares + torch.sum(values[key].detach().to(torch.float64) ** 2)
    return torch.sqrt(squares)


def project_delta_norm(
    target: Mapping[str, Tensor],
    candidate: Mapping[str, Tensor],
    *,
    maximum_ratio: float,
) -> dict[str, Tensor]:
    if not math.isfinite(maximum_ratio) or maximum_ratio < 0.0:
        raise ValueError("maximum_ratio must be finite and nonnegative")
    keys = _validate_adapter_pair(target, candidate)
    target_norm = _whole_norm(target, keys)
    deltas = {key: candidate[key] - target[key] for key in keys}
    delta_norm = _whole_norm(deltas, keys)
    ceiling = target_norm * maximum_ratio
    if bool(delta_norm <= ceiling) or float(delta_norm) == 0.0:
        return {key: candidate[key].detach().clone() for key in keys}
    scale = float(ceiling / delta_norm)
    return {
        key: target[key] + deltas[key] * scale
        for key in keys
    }


def interpolate_adapter(
    target: Mapping[str, Tensor], candidate: Mapping[str, Tensor], *, alpha: float
) -> dict[str, Tensor]:
    if not math.isfinite(alpha) or not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be finite and in [0, 1]")
    keys = _validate_adapter_pair(target, candidate)
    return {
        key: target[key] + alpha * (candidate[key] - target[key])
        for key in keys
    }


def adapter_sha256(state: Mapping[str, Tensor]) -> str:
    if not state:
        raise ValueError("adapter state must not be empty")
    digest = hashlib.sha256()
    for key in sorted(state):
        tensor = state[key].detach().cpu().contiguous()
        if not bool(torch.isfinite(tensor).all()):
            raise ValueError(f"adapter tensor {key} is nonfinite")
        metadata = {
            "dtype": str(tensor.dtype),
            "key": key,
            "shape": list(tensor.shape),
        }
        encoded = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        raw = bytes(tensor.view(torch.uint8).reshape(-1).tolist())
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return "sha256:" + digest.hexdigest()


@dataclass(frozen=True, slots=True)
class RBEPCheckpoint:
    step: int
    adapter_sha256: str
    state: Mapping[str, Tensor]


@dataclass(frozen=True, slots=True)
class RBEPPathResult:
    checkpoints: tuple[RBEPCheckpoint, ...]
    runtime_seconds: float


def train_rbep_path(
    *,
    candidate_parameters: Mapping[str, torch.nn.Parameter],
    target_state: Mapping[str, Tensor],
    optimizer: torch.optim.Optimizer,
    loss_step: Callable[[int], Tensor],
    steps: int,
    checkpoint_steps: tuple[int, ...],
    gradient_clip_norm: float,
    delta_norm_ratio_max: float,
) -> RBEPPathResult:
    if steps < 1:
        raise ValueError("steps must be positive")
    if (
        not checkpoint_steps
        or tuple(sorted(set(checkpoint_steps))) != checkpoint_steps
        or checkpoint_steps[-1] > steps
    ):
        raise ValueError("checkpoint steps must be unique, ordered, and within training")
    if not math.isfinite(gradient_clip_norm) or gradient_clip_norm <= 0.0:
        raise ValueError("gradient_clip_norm must be finite and positive")
    _validate_adapter_pair(target_state, candidate_parameters)
    started = time.perf_counter()
    checkpoints: list[RBEPCheckpoint] = []
    for step in range(1, steps + 1):
        optimizer.zero_grad(set_to_none=True)
        loss = loss_step(step)
        if loss.ndim != 0 or not bool(torch.isfinite(loss)):
            raise ValueError(f"training loss is invalid at step {step}")
        loss.backward()  # type: ignore[no-untyped-call]
        torch.nn.utils.clip_grad_norm_(
            tuple(candidate_parameters.values()),
            max_norm=gradient_clip_norm,
            error_if_nonfinite=True,
        )
        optimizer.step()
        projected = project_delta_norm(
            target_state,
            candidate_parameters,
            maximum_ratio=delta_norm_ratio_max,
        )
        with torch.no_grad():
            for key, value in projected.items():
                candidate_parameters[key].copy_(value)
        if step in checkpoint_steps:
            state = {
                key: value.detach().cpu().clone()
                for key, value in sorted(candidate_parameters.items())
            }
            checkpoints.append(
                RBEPCheckpoint(
                    step=step,
                    adapter_sha256=adapter_sha256(state),
                    state=state,
                )
            )
    return RBEPPathResult(
        checkpoints=tuple(checkpoints),
        runtime_seconds=time.perf_counter() - started,
    )
