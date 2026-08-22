from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import time
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import torch
from advanced_face_unlearning import (
    DatasetView,
    FaceAdapter,
    _load_dataset,
    _mapped_targets,
    _split_general,
    gradient_ascent_unlearn,
    train_adapter,
)
from torch import nn

from erasemap.paired_evaluation import (
    identity_cohesion_scores,
    paired_attack_differences,
    split_embedding_mse,
)
from erasemap.privacy_attacks import (
    balanced_shadow_membership,
    embedding_nearest_neighbor_scores,
    evaluate_attack,
    gaussian_likelihood_ratio_scores,
    score_statistics,
    split_shadow_scores,
)
from erasemap.verification_metrics import (
    bootstrap_mean_interval,
    linear_cka,
    normalize_rows,
    verification_metrics,
)

METRICS = (
    "retained_verification_auc",
    "retained_tar_at_far",
    "forgotten_verification_auc",
    "membership_attack_auc",
    "privacy_confidence_symmetric_auc",
    "privacy_energy_symmetric_auc",
    "privacy_margin_symmetric_auc",
    "privacy_negative_entropy_symmetric_auc",
    "privacy_worst_case_advantage",
    "privacy_worst_case_tpr_at_fpr",
    "functional_embedding_mse_to_exact",
    "retained_cka_to_exact",
    "runtime_seconds",
    "speedup_vs_exact",
)
V22_METRICS = (
    "privacy_embedding_nn_symmetric_auc",
    "privacy_embedding_nn_tpr_at_fpr",
    "privacy_lira_symmetric_auc",
    "privacy_lira_tpr_at_fpr",
)
V3_METRICS = (
    "forgotten_embedding_mse_to_exact",
    "retained_embedding_mse_to_exact",
    "privacy_confidence_advantage",
    "privacy_energy_advantage",
    "privacy_margin_advantage",
    "privacy_negative_entropy_advantage",
    "privacy_embedding_nn_advantage",
    "privacy_identity_deletion_lira_in_probability",
    "privacy_identity_deletion_lira_mean_log_lr",
)
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


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, check=False, text=True
    )
    return result.stdout.strip() or "unknown"


def is_dirty() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, check=False, text=True
    )
    return bool(result.stdout.strip())


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


def evaluate_method(
    model: FaceAdapter,
    exact: FaceAdapter,
    features: np.ndarray[Any, Any],
    targets: np.ndarray[Any, Any],
    train: np.ndarray[Any, Any],
    test: np.ndarray[Any, Any],
    forget_subject: int,
    *,
    runtime: float,
    exact_runtime: float,
    far_target: float,
    privacy_attacks: tuple[str, ...],
    shadow_calibration: ShadowCalibration | None,
    identity_shadow_calibration: IdentityShadowCalibration | None,
    seed: int,
) -> dict[str, float]:
    model_embeddings = encoder_embeddings(model, features)
    exact_embeddings = encoder_embeddings(exact, features)
    forget_all = np.flatnonzero(targets == forget_subject)
    retain_test = test[targets[test] != forget_subject]
    forgotten_train = train[targets[train] == forget_subject]
    forgotten_test = test[targets[test] == forget_subject]
    retained_positive, retained_negative = pair_scores(
        model_embeddings, targets, retain_test, seed=seed
    )
    forgotten_positive, forgotten_negative = pair_scores(
        model_embeddings,
        targets,
        forget_all,
        seed=seed + 1,
        max_pairs=1000,
        negative_pool=np.arange(len(targets)),
    )
    retained = verification_metrics(retained_positive, retained_negative, far_target=far_target)
    forgotten = verification_metrics(forgotten_positive, forgotten_negative, far_target=far_target)
    with torch.inference_mode():
        member_logits = model(torch.from_numpy(features[forgotten_train]).float()).numpy()
        nonmember_logits = model(torch.from_numpy(features[forgotten_test]).float()).numpy()
    member_statistics = score_statistics(member_logits)
    nonmember_statistics = score_statistics(nonmember_logits)
    logit_attacks = tuple(name for name in privacy_attacks if name in LOGIT_ATTACKS)
    attack_results = {
        name: evaluate_attack(
            member_statistics[name], nonmember_statistics[name], target_fpr=far_target
        )
        for name in logit_attacks
    }
    if "task_agnostic_lira" in privacy_attacks:
        if shadow_calibration is None:
            raise ValueError("LiRA attack requires frozen shadow-model calibration")
        member_lira = gaussian_likelihood_ratio_scores(
            member_statistics[shadow_calibration.statistic],
            shadow_calibration.in_scores[:, forgotten_train],
            shadow_calibration.out_scores[:, forgotten_train],
        )
        nonmember_lira = gaussian_likelihood_ratio_scores(
            nonmember_statistics[shadow_calibration.statistic],
            shadow_calibration.in_scores[:, forgotten_test],
            shadow_calibration.out_scores[:, forgotten_test],
        )
        attack_results["task_agnostic_lira"] = evaluate_attack(
            member_lira, nonmember_lira, target_fpr=far_target
        )
    if "embedding_nn" in privacy_attacks:
        member_nn, nonmember_nn = embedding_nearest_neighbor_scores(
            model_embeddings, forgotten_train, forgotten_test
        )
        attack_results["embedding_nn"] = evaluate_attack(
            member_nn, nonmember_nn, target_fpr=far_target
        )
    membership_auc = attack_results["confidence"].raw_auc
    worst_advantage = max(result.advantage for result in attack_results.values())
    worst_tpr = max(result.tpr_at_fpr for result in attack_results.values())
    mse = float(np.mean((model_embeddings - exact_embeddings) ** 2))
    forgotten_mse, retained_mse = split_embedding_mse(
        model_embeddings,
        exact_embeddings,
        forget_all,
        retain_test,
    )
    result = {
        "forgotten_verification_auc": forgotten.auc,
        "functional_embedding_mse_to_exact": mse,
        "membership_attack_auc": membership_auc,
        "privacy_confidence_symmetric_auc": attack_results["confidence"].symmetric_auc,
        "privacy_energy_symmetric_auc": attack_results["energy"].symmetric_auc,
        "privacy_margin_symmetric_auc": attack_results["margin"].symmetric_auc,
        "privacy_negative_entropy_symmetric_auc": attack_results[
            "negative_entropy"
        ].symmetric_auc,
        "privacy_worst_case_advantage": worst_advantage,
        "privacy_worst_case_tpr_at_fpr": worst_tpr,
        "retained_cka_to_exact": linear_cka(
            model_embeddings[retain_test], exact_embeddings[retain_test]
        ),
        "retained_tar_at_far": retained.tar_at_far,
        "retained_verification_auc": retained.auc,
        "runtime_seconds": runtime,
        "speedup_vs_exact": exact_runtime / max(runtime, 1e-9),
    }
    if "identity_deletion_lira" in privacy_attacks:
        if identity_shadow_calibration is None:
            raise ValueError("identity deletion LiRA requires identity-level shadow calibration")
        target_cohesion = identity_cohesion_scores(model_embeddings, forget_all)
        log_lr = gaussian_likelihood_ratio_scores(
            target_cohesion,
            identity_shadow_calibration.in_scores,
            identity_shadow_calibration.out_scores,
        )
        clipped = np.clip(log_lr, -60, 60)
        result["privacy_identity_deletion_lira_in_probability"] = float(
            np.mean(1 / (1 + np.exp(-clipped)))
        )
        result["privacy_identity_deletion_lira_mean_log_lr"] = float(np.mean(log_lr))
    if "embedding_nn" in attack_results:
        result["privacy_embedding_nn_advantage"] = attack_results[
            "embedding_nn"
        ].advantage
    result.update(
        {
            "forgotten_embedding_mse_to_exact": forgotten_mse,
            "retained_embedding_mse_to_exact": retained_mse,
            **{
                f"privacy_{name}_advantage": attack_results[name].advantage
                for name in LOGIT_ATTACKS
            },
        }
    )
    if "embedding_nn" in attack_results:
        result["privacy_embedding_nn_symmetric_auc"] = attack_results[
            "embedding_nn"
        ].symmetric_auc
        result["privacy_embedding_nn_tpr_at_fpr"] = attack_results[
            "embedding_nn"
        ].tpr_at_fpr
    if "task_agnostic_lira" in attack_results:
        result["privacy_lira_symmetric_auc"] = attack_results[
            "task_agnostic_lira"
        ].symmetric_auc
        result["privacy_lira_tpr_at_fpr"] = attack_results[
            "task_agnostic_lira"
        ].tpr_at_fpr
    return result


def run_split(protocol_path: Path, split: str, output: Path) -> dict[str, Any]:
    if split != "development" and is_dirty():
        raise RuntimeError("non-development evaluation requires a clean working tree")
    protocol = json.loads(protocol_path.read_text())
    dataset_settings = protocol["datasets"][split]
    source_protocol = json.loads(Path(dataset_settings["protocol"]).read_text())
    if dataset_settings["name"] == "mufac_external":
        bundle = joblib.load(dataset_settings["bundle"])
        features = np.asarray(bundle["embeddings"], dtype=np.float32)
        external_targets = np.asarray(bundle["targets"], dtype=np.int64)
        external_train, external_test = _split_general(
            external_targets,
            test_fraction=float(source_protocol["test_fraction_per_identity"]),
            seed=int(source_protocol["split_seed"]),
        )
        dataset = DatasetView(
            np.empty((len(features), 0), dtype=np.float32),
            external_targets,
            external_train,
            external_test,
            -1,
            "MUFAC content-unseen subset",
        )
        embeddings_path = Path(dataset_settings["bundle"])
    else:
        dataset = _load_dataset(dataset_settings["name"], source_protocol, Path("data/real"))
        embeddings_path = Path(dataset_settings["embeddings"])
        features = np.asarray(joblib.load(embeddings_path), dtype=np.float32)
    train = np.asarray(dataset.train_indices)
    test = np.asarray(dataset.test_indices)
    targets = dataset.targets
    classes = np.unique(targets)
    local = protocol["local_model"]
    privacy_attacks = tuple(
        str(value)
        for value in protocol.get(
            "privacy_attacks", ["confidence", "negative_entropy", "margin", "energy"]
        )
    )
    expected_attacks = set(LOGIT_ATTACKS)
    if protocol["schema_version"] == "erasemap-task-agnostic-v2.2":
        expected_attacks |= {"task_agnostic_lira", "embedding_nn"}
    if protocol["schema_version"] == "erasemap-task-agnostic-v3":
        expected_attacks |= {"identity_deletion_lira", "embedding_nn"}
    if set(privacy_attacks) != expected_attacks:
        raise ValueError("privacy attack suite does not match the registered schema")
    output.mkdir(parents=True, exist_ok=True)
    if split != "development":
        lock = output / f"{split}.lock.json"
        if lock.exists():
            raise RuntimeError("evaluation lock already exists")
        lock.write_text(
            canonical_json(
                {
                    "code_revision": revision(),
                    "protocol_sha256": sha256_file(protocol_path),
                    "schema_version": f"erasemap-task-agnostic-{split}-lock-v1",
                }
            )
            + "\n"
        )
    trials: list[dict[str, Any]] = []
    for seed in protocol["random_seeds"]:
        shadow_calibration = None
        if "task_agnostic_lira" in privacy_attacks:
            shadow_calibration = train_shadow_calibration(
                features,
                targets,
                classes,
                local,
                protocol["shadow_models"],
                seed=int(seed),
            )
        original, _ = train_adapter(
            features[train],
            targets[train],
            classes=classes,
            hidden_dimension=int(local["hidden_dimension"]),
            epochs=int(local["epochs"]),
            learning_rate=float(local["learning_rate"]),
            weight_decay=float(local["weight_decay"]),
            seed=int(seed),
        )
        rng = np.random.default_rng(int(seed))
        selected_subjects = rng.choice(
            classes,
            size=min(int(protocol["forget_identities_per_seed"]), len(classes)),
            replace=False,
        )
        for forget_subject_value in selected_subjects:
            forget_subject = int(forget_subject_value)
            forget_train = train[targets[train] == forget_subject]
            retain_train = train[targets[train] != forget_subject]
            retained_classes = classes[classes != forget_subject]
            exact, exact_runtime = train_adapter(
                features[retain_train],
                targets[retain_train],
                classes=retained_classes,
                hidden_dimension=int(local["hidden_dimension"]),
                epochs=int(local["epochs"]),
                learning_rate=float(local["learning_rate"]),
                weight_decay=float(local["weight_decay"]),
                seed=int(seed),
            )
            identity_shadow_calibration = None
            if "identity_deletion_lira" in privacy_attacks:
                identity_shadow_calibration = train_identity_shadow_calibration(
                    features,
                    targets,
                    train,
                    forget_subject,
                    local,
                    protocol["identity_shadow_models"],
                    seed=int(seed) + forget_subject * 100,
                )
            encoder_state = {
                name: value.detach().clone()
                for name, value in original.encoder.state_dict().items()
            }
            head_only, head_runtime = train_adapter(
                features[retain_train],
                targets[retain_train],
                classes=retained_classes,
                hidden_dimension=int(local["hidden_dimension"]),
                epochs=int(local["epochs"]),
                learning_rate=float(local["learning_rate"]),
                weight_decay=float(local["weight_decay"]),
                seed=int(seed),
                encoder_state=encoder_state,
                freeze_encoder=True,
            )
            gradient, gradient_runtime = gradient_ascent_unlearn(
                original,
                features[retain_train],
                targets[retain_train],
                features[forget_train],
                targets[forget_train],
                classes,
                protocol["gradient_ascent"],
                int(seed),
            )
            if "deletion_matched_restart" in protocol["methods"]:
                restart_settings = protocol.get("deletion_matched_restart")
                if not isinstance(restart_settings, dict):
                    raise ValueError("deletion-matched restart settings are required")
                selective, selective_runtime = deletion_matched_restart(
                    features[retain_train],
                    targets[retain_train],
                    retained_classes,
                    local,
                    restart_settings,
                    int(seed),
                )
                selective_name = "deletion_matched_restart"
                selected_fraction = 1.0
            else:
                selective_settings = protocol.get(
                    "influence_selective", protocol.get("lineage_guided")
                )
                if not isinstance(selective_settings, dict):
                    raise ValueError("influence-selective settings are required")
                selective, selective_runtime, selected_fraction = (
                    influence_selective_unlearn(
                        original,
                        features[retain_train],
                        targets[retain_train],
                        features[forget_train],
                        targets[forget_train],
                        classes,
                        selective_settings,
                        int(seed),
                    )
                )
                selective_name = (
                    "influence_selective"
                    if "influence_selective" in protocol["methods"]
                    else "lineage_guided"
                )
            models = {
                "stale": (original, 0.0),
                "head_only": (head_only, head_runtime),
                "gradient_ascent": (gradient, gradient_runtime),
                selective_name: (selective, selective_runtime),
                "exact_retrain": (exact, exact_runtime),
            }
            for method, (model, runtime) in models.items():
                metrics = evaluate_method(
                    model,
                    exact,
                    features,
                    targets,
                    train,
                    test,
                    forget_subject,
                    runtime=runtime,
                    exact_runtime=exact_runtime,
                    far_target=float(protocol["far_target"]),
                    privacy_attacks=privacy_attacks,
                    shadow_calibration=shadow_calibration,
                    identity_shadow_calibration=identity_shadow_calibration,
                    seed=int(seed) + forget_subject,
                )
                trials.append(
                    {
                        "anonymous_forget_subject": forget_subject,
                        "method": method,
                        "seed": int(seed),
                        "selected_parameter_fraction": (
                            selected_fraction if method == selective_name else None
                        ),
                        **metrics,
                    }
                )
    summary: dict[str, Any] = {}
    methods = tuple(str(value) for value in protocol["methods"])
    registered_metrics = METRICS + (
        V22_METRICS
        if protocol["schema_version"] == "erasemap-task-agnostic-v2.2"
        else ()
    )
    if protocol["schema_version"] == "erasemap-task-agnostic-v3":
        registered_metrics += V3_METRICS
    for method in methods:
        rows = [row for row in trials if row["method"] == method]
        summary[method] = {}
        for metric in registered_metrics:
            values = np.asarray([row[metric] for row in rows], dtype=np.float64)
            interval = bootstrap_mean_interval(
                values,
                seed=int(protocol["random_seeds"][0]),
                samples=int(protocol["bootstrap_samples"]),
            )
            summary[method][metric] = {
                "ci95": list(interval),
                "mean": float(np.mean(values)),
                "std": float(np.std(values, ddof=1)),
            }
    selective_name = next(
        name
        for name in (
            "deletion_matched_restart",
            "influence_selective",
            "lineage_guided",
        )
        if name in methods
    )
    selective = summary[selective_name]
    exact = summary["exact_retrain"]
    stale = summary["stale"]
    criteria = protocol["success_criteria"]
    endpoints: dict[str, float] = {}
    paired_privacy: dict[str, Any] = {}
    if protocol["schema_version"] == "erasemap-task-agnostic-v3":
        stale_forgotten_mse = float(stale["forgotten_embedding_mse_to_exact"]["mean"])
        stale_retained_mse = float(stale["retained_embedding_mse_to_exact"]["mean"])
        forgotten_ratio = float(selective["forgotten_embedding_mse_to_exact"]["mean"]) / max(
            stale_forgotten_mse, 1e-12
        )
        retained_ratio = float(selective["retained_embedding_mse_to_exact"]["mean"]) / max(
            stale_retained_mse, 1e-12
        )
        gated_attacks = tuple(str(value) for value in protocol["paired_privacy_attacks"])
        paired_results = paired_attack_differences(
            trials,
            gated_attacks,
            selective_method=selective_name,
            exact_method="exact_retrain",
            bootstrap_seed=int(protocol["random_seeds"][0]),
            bootstrap_samples=int(protocol["bootstrap_samples"]),
        )
        paired_privacy = {
            result.attack: {
                "ci95": list(result.ci95),
                "mean_difference": result.mean_difference,
                "trials": result.trials,
            }
            for result in paired_results
        }
        max_attack_upper_ci = max(result.ci95[1] for result in paired_results)
        stale_exact_lira_separation = float(
            stale["privacy_identity_deletion_lira_in_probability"]["mean"]
        ) - float(exact["privacy_identity_deletion_lira_in_probability"]["mean"])
        endpoints = {
            "forgotten_embedding_mse_ratio_to_stale": forgotten_ratio,
            "retained_embedding_mse_ratio_to_stale": retained_ratio,
            "max_attack_paired_advantage_upper_ci": max_attack_upper_ci,
            "identity_lira_stale_minus_exact": stale_exact_lira_separation,
        }
        primary_endpoint = str(protocol["primary_endpoint"])
        if primary_endpoint not in endpoints:
            raise ValueError("registered primary endpoint was not computed")
        success = (
            float(endpoints[primary_endpoint]) <= float(criteria["primary_endpoint_max"])
            and retained_ratio <= float(criteria["retained_embedding_mse_ratio_to_stale_max"])
            and max_attack_upper_ci
            <= float(criteria["max_attack_paired_advantage_upper_ci_max"])
            and stale_exact_lira_separation
            >= float(criteria["identity_lira_stale_minus_exact_min"])
            and float(selective["retained_verification_auc"]["mean"])
            - float(exact["retained_verification_auc"]["mean"])
            >= float(criteria["candidate_retained_auc_delta_min"])
            and float(selective["speedup_vs_exact"]["mean"])
            >= float(criteria["candidate_speedup_min"])
        )
    elif protocol["schema_version"] in {
        "erasemap-task-agnostic-v2.1",
        "erasemap-task-agnostic-v2.2",
    }:
        stale_mse = float(stale["functional_embedding_mse_to_exact"]["mean"])
        mse_ratio = float(selective["functional_embedding_mse_to_exact"]["mean"]) / max(
            stale_mse, 1e-12
        )
        privacy_gap = abs(
            float(selective["privacy_worst_case_advantage"]["mean"])
            - float(exact["privacy_worst_case_advantage"]["mean"])
        )
        endpoints = {
            "functional_embedding_mse_ratio_to_stale": mse_ratio,
            "worst_privacy_advantage_gap_to_exact": privacy_gap,
        }
        primary_endpoint = str(protocol["primary_endpoint"])
        if primary_endpoint not in endpoints:
            raise ValueError("registered primary endpoint was not computed")
        success = (
            float(endpoints[primary_endpoint])
            <= float(criteria["primary_endpoint_max"])
            and float(selective["retained_verification_auc"]["mean"])
            - float(exact["retained_verification_auc"]["mean"])
            >= float(criteria["influence_selective_retained_auc_delta_min"])
            and privacy_gap
            <= float(
                criteria[
                    "influence_selective_worst_privacy_advantage_gap_to_exact_max"
                ]
            )
            and float(selective["speedup_vs_exact"]["mean"])
            >= float(criteria["influence_selective_speedup_min"])
        )
    else:
        success = (
            float(selective["retained_verification_auc"]["mean"])
            - float(exact["retained_verification_auc"]["mean"])
            >= float(criteria["lineage_guided_retained_auc_delta_min"])
            and abs(
                float(selective["membership_attack_auc"]["mean"])
                - float(exact["membership_attack_auc"]["mean"])
            )
            <= float(criteria["lineage_guided_mia_auc_gap_to_exact_max"])
            and float(selective["speedup_vs_exact"]["mean"])
            >= float(criteria["lineage_guided_speedup_min"])
        )
    payload = {
        "claim_boundary": (
            "Task-agnostic verification over a trainable local embedding encoder; "
            "the pretrained MobileFaceNet input backbone remains frozen."
        ),
        "dataset": {"images": len(features), "name": dataset.name, "subjects": len(classes)},
        "endpoints": endpoints,
        "manifests": {
            "embeddings": sha256_file(embeddings_path),
            "protocol": sha256_file(protocol_path),
        },
        "privacy_evaluation": {
            "attacks": list(privacy_attacks),
            "shadow_models": (
                int(protocol["shadow_models"]["models"])
                if "task_agnostic_lira" in privacy_attacks
                else 0
            ),
        },
        "paired_privacy": paired_privacy,
        "split": split,
        "success": success,
        "summary": summary,
        "trial_count": len(trials),
        "trials": trials,
    }
    (output / "result.json").write_text(canonical_json(payload) + "\n")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", default="benchmark/task-agnostic-v2.json")
    parser.add_argument(
        "--split", choices=("development", "evaluation", "external"), required=True
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = run_split(Path(args.protocol), args.split, Path(args.output))
    print(
        canonical_json(
            {
                "split": args.split,
                "success": payload["success"],
                "trial_count": payload["trial_count"],
            }
        )
    )
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
