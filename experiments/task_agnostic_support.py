from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from itertools import combinations
from typing import Any

import numpy as np
import torch
from advanced_face_unlearning import FaceAdapter, _mapped_targets, train_adapter
from torch import nn

from erasemap.paired_evaluation import identity_cohesion_scores
from erasemap.privacy_attacks import (
    balanced_shadow_membership,
    score_statistics,
    split_shadow_scores,
)
from erasemap.verification_metrics import normalize_rows

LOGIT_ATTACKS = frozenset({"confidence", "energy", "margin", "negative_entropy"})


@dataclass(frozen=True, slots=True)
class ShadowCalibration:
    in_scores: np.ndarray[Any, Any]
    out_scores: np.ndarray[Any, Any]
    models: int
    statistic: str


@dataclass(frozen=True, slots=True)
class IdentityShadowCalibration:
    in_scores: np.ndarray[Any, Any]
    out_scores: np.ndarray[Any, Any]
    models: int



def encoder_embeddings(model: FaceAdapter, features: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    with torch.inference_mode():
        values = model.encoder(torch.from_numpy(features).float()).numpy()
    return normalize_rows(values).astype(np.float32)


def probabilities(model: FaceAdapter, features: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    with torch.inference_mode():
        return torch.softmax(model(torch.from_numpy(features).float()), dim=1).numpy()


def train_shadow_calibration(
    features: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    classes: np.ndarray[Any, Any],
    local_settings: dict[str, Any],
    shadow_settings: dict[str, Any],
    *,
    seed: int,
) -> ShadowCalibration:
    shadow_count = int(shadow_settings["models"])
    inclusions = int(shadow_settings["inclusions_per_sample"])
    statistic = str(shadow_settings["statistic"])
    if statistic not in LOGIT_ATTACKS:
        raise ValueError("shadow statistic must be one of the registered logit statistics")
    membership: np.ndarray[Any, Any] | None = None
    for attempt in range(100):
        candidate = balanced_shadow_membership(
            len(features),
            shadow_count,
            inclusions_per_sample=inclusions,
            seed=seed + attempt,
        )
        if all(
            len(np.unique(targets[candidate[index]])) == len(classes)
            for index in range(shadow_count)
        ):
            membership = candidate
            break
    if membership is None:
        raise RuntimeError("could not construct class-complete balanced shadow datasets")
    shadow_scores: list[np.ndarray[Any, Any]] = []
    for shadow_index, selection in enumerate(membership):
        model, _ = train_adapter(
            features[selection],
            targets[selection],
            classes=classes,
            hidden_dimension=int(local_settings["hidden_dimension"]),
            epochs=int(shadow_settings["epochs"]),
            learning_rate=float(local_settings["learning_rate"]),
            weight_decay=float(local_settings["weight_decay"]),
            seed=seed + 10_000 + shadow_index,
        )
        with torch.inference_mode():
            logits = model(torch.from_numpy(features).float()).numpy()
        shadow_scores.append(score_statistics(logits)[statistic])
    in_scores, out_scores = split_shadow_scores(np.stack(shadow_scores), membership)
    return ShadowCalibration(in_scores, out_scores, shadow_count, statistic)


def train_identity_shadow_calibration(
    features: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    train: np.ndarray[Any, Any],
    forget_subject: int,
    local_settings: dict[str, Any],
    shadow_settings: dict[str, Any],
    *,
    seed: int,
) -> IdentityShadowCalibration:
    shadow_count = int(shadow_settings["models"])
    if shadow_count < 4 or shadow_count % 2:
        raise ValueError("identity shadow model count must be even and at least four")
    forget_all = np.flatnonzero(targets == forget_subject)
    forgotten_train = train[targets[train] == forget_subject]
    retained_train = train[targets[train] != forget_subject]
    all_classes = np.unique(targets[train])
    retained_classes = all_classes[all_classes != forget_subject]
    in_scores: list[np.ndarray[Any, Any]] = []
    out_scores: list[np.ndarray[Any, Any]] = []
    for shadow_index in range(shadow_count):
        include_identity = shadow_index < shadow_count // 2
        selection = (
            np.concatenate((retained_train, forgotten_train))
            if include_identity
            else retained_train
        )
        classes = all_classes if include_identity else retained_classes
        model, _ = train_adapter(
            features[selection],
            targets[selection],
            classes=classes,
            hidden_dimension=int(local_settings["hidden_dimension"]),
            epochs=int(shadow_settings["epochs"]),
            learning_rate=float(local_settings["learning_rate"]),
            weight_decay=float(local_settings["weight_decay"]),
            seed=seed + 20_000 + shadow_index,
        )
        scores = identity_cohesion_scores(
            encoder_embeddings(model, features), forget_all
        )
        (in_scores if include_identity else out_scores).append(scores)
    return IdentityShadowCalibration(
        np.stack(in_scores), np.stack(out_scores), shadow_count
    )


def pair_scores(
    embeddings: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    indices: np.ndarray[Any, Any],
    *,
    seed: int,
    max_pairs: int = 3000,
    negative_pool: np.ndarray[Any, Any] | None = None,
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    positive_pairs: list[tuple[int, int]] = []
    for label in np.unique(targets[indices]):
        members = [int(value) for value in indices[targets[indices] == label]]
        positive_pairs.extend(combinations(members, 2))
    rng = np.random.default_rng(seed)
    if len(positive_pairs) > max_pairs:
        selected = rng.choice(len(positive_pairs), size=max_pairs, replace=False)
        positive_pairs = [positive_pairs[int(index)] for index in selected]
    if not positive_pairs:
        raise ValueError("at least one positive pair is required")
    pool = indices if negative_pool is None else negative_pool
    if len(np.unique(targets[pool])) < 2:
        raise ValueError("negative pool must contain at least two identities")
    negative_pairs: list[tuple[int, int]] = []
    while len(negative_pairs) < len(positive_pairs):
        remaining = len(positive_pairs) - len(negative_pairs)
        candidates = rng.choice(pool, size=(max(32, remaining * 2), 2), replace=True)
        different = candidates[targets[candidates[:, 0]] != targets[candidates[:, 1]]]
        negative_pairs.extend((int(left), int(right)) for left, right in different[:remaining])
    positive = np.asarray([np.dot(embeddings[a], embeddings[b]) for a, b in positive_pairs])
    negative = np.asarray([np.dot(embeddings[a], embeddings[b]) for a, b in negative_pairs])
    return positive, negative


def influence_selective_unlearn(
    original: FaceAdapter,
    retain_features: np.ndarray[Any, Any],
    retain_targets: np.ndarray[Any, Any],
    forget_features: np.ndarray[Any, Any],
    forget_targets: np.ndarray[Any, Any],
    classes: np.ndarray[Any, Any],
    settings: dict[str, Any],
    seed: int,
) -> tuple[FaceAdapter, float, float]:
    torch.manual_seed(seed)
    model = copy.deepcopy(original).train()
    retain_x = torch.from_numpy(retain_features).float()
    retain_y = _mapped_targets(retain_targets, classes)
    forget_x = torch.from_numpy(forget_features).float()
    forget_y = _mapped_targets(forget_targets, classes)
    with torch.inference_mode():
        reference_embeddings = original.encoder(retain_x).detach()
    model.zero_grad()
    nn.functional.cross_entropy(model(forget_x), forget_y).backward()
    sensitivities = [
        parameter.grad.detach().abs().flatten()
        for parameter in model.parameters()
        if parameter.grad is not None
    ]
    threshold = torch.quantile(
        torch.cat(sensitivities), 1 - float(settings["top_parameter_fraction"])
    )
    masks = {
        name: (parameter.grad.detach().abs() >= threshold)
        for name, parameter in model.named_parameters()
        if parameter.grad is not None
    }
    selected = sum(int(mask.sum()) for mask in masks.values())
    total = sum(mask.numel() for mask in masks.values())
    reference = {name: parameter.detach().clone() for name, parameter in model.named_parameters()}
    optimizer = torch.optim.Adam(model.parameters(), lr=float(settings["learning_rate"]))
    generator = torch.Generator().manual_seed(seed)
    batch_size = min(256, len(retain_x))
    started = time.perf_counter()
    for _ in range(int(settings["steps"])):
        selection = torch.randperm(len(retain_x), generator=generator)[:batch_size]
        optimizer.zero_grad()
        current_embeddings = model.encoder(retain_x[selection])
        retain_loss = nn.functional.cross_entropy(
            model.classifier(current_embeddings), retain_y[selection]
        )
        forget_loss = nn.functional.cross_entropy(model(forget_x), forget_y)
        distillation = nn.functional.mse_loss(current_embeddings, reference_embeddings[selection])
        drift = sum(
            torch.mean((parameter - reference[name]) ** 2)
            for name, parameter in model.named_parameters()
        )
        loss = (
            retain_loss
            - float(settings["forget_weight"]) * forget_loss
            + float(settings["retain_distillation_weight"]) * distillation
            + float(settings["parameter_drift_weight"]) * drift
        )
        loss.backward()
        for name, parameter in model.named_parameters():
            if parameter.grad is not None:
                parameter.grad.mul_(masks[name])
        torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
        optimizer.step()
    return model.eval(), time.perf_counter() - started, selected / total


def deletion_matched_restart(
    retain_features: np.ndarray[Any, Any],
    retain_targets: np.ndarray[Any, Any],
    retained_classes: np.ndarray[Any, Any],
    local_settings: dict[str, Any],
    settings: dict[str, Any],
    seed: int,
) -> tuple[FaceAdapter, float]:
    """Train a fresh, bounded-cost model on retained data only.

    Sharing initialization and optimizer settings with exact retraining makes the
    approximation auditable: its only approximation is the frozen epoch budget.
    """
    return train_adapter(
        retain_features,
        retain_targets,
        classes=retained_classes,
        hidden_dimension=int(local_settings["hidden_dimension"]),
        epochs=int(settings["epochs"]),
        learning_rate=float(local_settings["learning_rate"]),
        weight_decay=float(local_settings["weight_decay"]),
        seed=seed,
    )


