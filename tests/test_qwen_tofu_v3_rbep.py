from __future__ import annotations

import pytest
import torch

from experiments.qwen_tofu_v3_rbep import (
    adapter_sha256,
    bounded_rbep_loss,
    interpolate_adapter,
    project_delta_norm,
    train_rbep_path,
)


def test_rbep_loss_is_zero_when_candidate_matches_both_references() -> None:
    logits = torch.tensor([[[1.0, 2.0], [2.0, 1.0]]])
    loss = bounded_rbep_loss(
        candidate_forget=logits,
        base_forget=logits,
        candidate_keep=logits,
        target_keep=logits,
        keep_labels=torch.tensor([[1, 0]]),
        forget_answer_mask=torch.tensor([[True, True]]),
        keep_answer_mask=torch.tensor([[True, True]]),
        temperature=1.0,
        keep_weight=1.0,
        cross_entropy_weight=0.0,
    )
    assert torch.allclose(loss, torch.tensor(0.0), atol=1e-7)


def test_rbep_loss_detaches_references_and_is_finite() -> None:
    candidate = torch.tensor([[[0.5, 1.5]]], requires_grad=True)
    base = torch.tensor([[[1.0, 2.0]]], requires_grad=True)
    target = torch.tensor([[[2.0, 1.0]]], requires_grad=True)
    loss = bounded_rbep_loss(
        candidate_forget=candidate,
        base_forget=base,
        candidate_keep=candidate,
        target_keep=target,
        keep_labels=torch.tensor([[1]]),
        forget_answer_mask=torch.tensor([[True]]),
        keep_answer_mask=torch.tensor([[True]]),
        temperature=2.0,
        keep_weight=0.5,
        cross_entropy_weight=0.1,
    )
    loss.backward()
    assert candidate.grad is not None
    assert base.grad is None
    assert target.grad is None
    assert torch.isfinite(loss)


def test_rbep_loss_rejects_empty_mask_and_invalid_temperature() -> None:
    logits = torch.tensor([[[1.0, 2.0]]])
    kwargs = {
        "candidate_forget": logits,
        "base_forget": logits,
        "candidate_keep": logits,
        "target_keep": logits,
        "keep_labels": torch.tensor([[1]]),
        "forget_answer_mask": torch.tensor([[False]]),
        "keep_answer_mask": torch.tensor([[False]]),
        "keep_weight": 1.0,
        "cross_entropy_weight": 0.0,
    }
    with pytest.raises(ValueError, match="answer mask"):
        bounded_rbep_loss(**kwargs, temperature=1.0)
    with pytest.raises(ValueError, match="temperature"):
        bounded_rbep_loss(**kwargs, temperature=0.0)


def test_project_delta_norm_caps_whole_adapter_ratio() -> None:
    target = {"x": torch.tensor([3.0, 4.0]), "y": torch.tensor([0.0])}
    candidate = {"x": torch.tensor([9.0, 12.0]), "y": torch.tensor([5.0])}
    projected = project_delta_norm(target, candidate, maximum_ratio=0.5)
    delta_norm = torch.sqrt(
        sum(torch.sum((projected[key] - target[key]) ** 2) for key in target)
    )
    target_norm = torch.sqrt(sum(torch.sum(value**2) for value in target.values()))
    assert delta_norm <= target_norm * 0.5 + 1e-6


def test_projection_leaves_in_bound_candidate_unchanged() -> None:
    target = {"x": torch.tensor([2.0])}
    candidate = {"x": torch.tensor([2.1])}
    projected = project_delta_norm(target, candidate, maximum_ratio=0.5)
    assert torch.equal(projected["x"], candidate["x"])


def test_interpolation_is_complete_deterministic_and_bounded() -> None:
    target = {"b": torch.tensor([2.0]), "a": torch.tensor([0.0, 2.0])}
    candidate = {"a": torch.tensor([2.0, 4.0]), "b": torch.tensor([4.0])}
    midpoint = interpolate_adapter(target, candidate, alpha=0.5)
    assert list(midpoint) == ["a", "b"]
    assert torch.equal(midpoint["a"], torch.tensor([1.0, 3.0]))
    assert torch.equal(midpoint["b"], torch.tensor([3.0]))
    assert adapter_sha256(midpoint) == adapter_sha256(dict(reversed(list(midpoint.items()))))


def test_interpolation_rejects_key_shape_and_alpha_drift() -> None:
    with pytest.raises(ValueError, match="keys"):
        interpolate_adapter({"a": torch.zeros(1)}, {"b": torch.zeros(1)}, alpha=0.5)
    with pytest.raises(ValueError, match="shape"):
        interpolate_adapter({"a": torch.zeros(1)}, {"a": torch.zeros(2)}, alpha=0.5)
    with pytest.raises(ValueError, match="alpha"):
        interpolate_adapter({"a": torch.zeros(1)}, {"a": torch.zeros(1)}, alpha=1.1)


def test_train_path_projects_every_step_and_saves_declared_checkpoints() -> None:
    parameter = torch.nn.Parameter(torch.tensor([1.0, -1.0]))
    optimizer = torch.optim.SGD([parameter], lr=1.0)
    target = {"adapter": parameter.detach().clone()}

    def loss_step(_: int) -> torch.Tensor:
        return -parameter.square().sum()

    result = train_rbep_path(
        candidate_parameters={"adapter": parameter},
        target_state=target,
        optimizer=optimizer,
        loss_step=loss_step,
        steps=4,
        checkpoint_steps=(2, 4),
        gradient_clip_norm=1.0,
        delta_norm_ratio_max=0.25,
    )
    assert [checkpoint.step for checkpoint in result.checkpoints] == [2, 4]
    assert result.runtime_seconds >= 0.0
    assert all(checkpoint.runtime_seconds > 0.0 for checkpoint in result.checkpoints)
    delta = torch.linalg.vector_norm(parameter.detach() - target["adapter"])
    assert delta <= torch.linalg.vector_norm(target["adapter"]) * 0.25 + 1e-6
    assert all(checkpoint.adapter_sha256.startswith("sha256:") for checkpoint in result.checkpoints)


def test_train_path_rejects_undeclared_checkpoint() -> None:
    parameter = torch.nn.Parameter(torch.tensor([1.0]))
    with pytest.raises(ValueError, match="checkpoint"):
        train_rbep_path(
            candidate_parameters={"adapter": parameter},
            target_state={"adapter": parameter.detach().clone()},
            optimizer=torch.optim.SGD([parameter], lr=0.1),
            loss_step=lambda _: parameter.sum(),
            steps=2,
            checkpoint_steps=(1, 3),
            gradient_clip_norm=1.0,
            delta_norm_ratio_max=0.25,
        )
