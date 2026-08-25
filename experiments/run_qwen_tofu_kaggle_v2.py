from __future__ import annotations

import argparse
import collections
import json
import math
import os
import platform
import random
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from erasemap.llm_unlearning_v2 import (
    score_v2_trial,
    select_development_candidate,
    summarize_v2_trials,
)
from experiments.run_qwen_tofu_kaggle_v1 import (
    QACollator,
    _adapter_digest,
    _canonical,
    _even_sample,
    _fresh_adapter,
    _git_revision,
    _load_base,
    _load_dependencies,
    _loader,
    _move,
    _release,
    _sha256,
    _train_adapter,
)

ROOT = Path(__file__).resolve().parents[1]


def _fingerprint(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row["question"]), str(row["answer"]))


def _normal(question: object, answer: object) -> dict[str, str]:
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("answer must be a non-empty string")
    return {"answer": answer, "question": question}


def _semantic_forget_rows(
    rows: Sequence[Mapping[str, Any]], *, expected_perturbations: int
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[list[dict[str, str]]]]:
    direct: list[dict[str, str]] = []
    paraphrase: list[dict[str, str]] = []
    perturbed: list[list[dict[str, str]]] = []
    for index, row in enumerate(rows):
        direct.append(_normal(row.get("question"), row.get("answer")))
        paraphrase.append(
            _normal(row.get("paraphrased_question"), row.get("paraphrased_answer"))
        )
        answers = row.get("perturbed_answer")
        if not isinstance(answers, list) or len(answers) != expected_perturbations:
            raise ValueError(f"perturbed row {index} has an unexpected answer count")
        perturbed.append([_normal(row.get("question"), answer) for answer in answers])
    return direct, paraphrase, perturbed


def _load_rows(
    protocol: Mapping[str, Any], deps: Mapping[str, Any]
) -> dict[str, object]:
    dataset = protocol["dataset"]
    evaluation = protocol["evaluation"]
    load_dataset = deps["load_dataset"]

    def config(name: str) -> list[Mapping[str, Any]]:
        local_dataset = os.environ.get("ERASEMAP_TOFU_PATH")
        if local_dataset:
            loaded = load_dataset(
                "json", data_files=str(Path(local_dataset) / f"{dataset[name]}.json"), split="train"
            )
        else:
            loaded = load_dataset(
                dataset["repository"], dataset[name], revision=dataset["revision"], split="train"
            )
        return [cast(Mapping[str, Any], row) for row in loaded]

    full = config("full")
    final_forget = config("confirmation_forget")
    final_fingerprints = {_fingerprint(row) for row in final_forget}
    development_forget = [
        row
        for row in config("development_forget")
        if _fingerprint(row) not in final_fingerprints
    ]
    development_fingerprints = {_fingerprint(row) for row in development_forget}
    if not development_forget or development_fingerprints & final_fingerprints:
        raise ValueError("development and confirmation deletion rows are not disjoint")
    development_retain = config("development_retain")
    development_retain_fingerprints = {_fingerprint(row) for row in development_retain}
    if development_retain_fingerprints & (
        development_fingerprints | final_fingerprints
    ):
        raise ValueError("development retain rows contain reserved deletion authors")
    confirmation_retain = config("confirmation_retain")

    final_perturbed = config("confirmation_forget_perturbed")
    development_perturbed = [
        row
        for row in config("development_forget_perturbed")
        if _fingerprint(row) not in final_fingerprints
    ]
    if not development_perturbed:
        raise ValueError("development perturbed rows are empty")

    real_authors = config("real_authors")
    anchor_count = int(evaluation["real_author_anchor_rows"])
    test_count = int(evaluation["real_author_test_rows"])
    anchors = [_normal(row.get("question"), row.get("answer")) for row in real_authors[::2]][
        :anchor_count
    ]
    real_test = [_normal(row.get("question"), row.get("answer")) for row in real_authors[1::2]][
        :test_count
    ]
    if len(anchors) != anchor_count or len(real_test) != test_count:
        raise ValueError("real-author anchor/test split is too small")
    if {_fingerprint(row) for row in anchors} & {_fingerprint(row) for row in real_test}:
        raise ValueError("real-author anchor and test rows overlap")
    anchor_answers = {row["answer"].strip().casefold() for row in anchors}
    test_answers = {row["answer"].strip().casefold() for row in real_test}
    if anchor_answers & test_answers:
        raise ValueError("real-author anchor and test identities overlap")

    common = {
        "full": [_normal(row.get("question"), row.get("answer")) for row in full],
        "holdout": [
            _normal(row.get("question"), row.get("answer"))
            for row in _even_sample(config("holdout"), int(evaluation["holdout_rows"]))
        ],
        "real_anchor": anchors,
        "real_test": real_test,
        "world_facts": [
            _normal(row.get("question"), row.get("answer"))
            for row in _even_sample(
                config("world_facts"), int(evaluation["world_facts_rows"])
            )
        ],
    }

    def scenario(
        forget_train: Sequence[Mapping[str, Any]],
        retain_train: Sequence[Mapping[str, Any]],
        perturbed_rows: Sequence[Mapping[str, Any]],
    ) -> dict[str, object]:
        sampled = _even_sample(perturbed_rows, int(evaluation["forget_rows"]))
        direct, paraphrase, perturb = _semantic_forget_rows(
            sampled,
            expected_perturbations=int(evaluation["perturbed_answers_per_row"]),
        )
        return {
            "evaluation": {
                "forget_answer": direct,
                "forget_paraphrase": paraphrase,
                "forget_perturbed": perturb,
                "holdout": common["holdout"],
                "real_authors": common["real_test"],
                "retain": _even_sample(
                    [_normal(row.get("question"), row.get("answer")) for row in retain_train],
                    int(evaluation["retain_rows"]),
                ),
                "world_facts": common["world_facts"],
            },
            "train_forget": [
                _normal(row.get("question"), row.get("answer")) for row in forget_train
            ],
            "train_retain": [
                _normal(row.get("question"), row.get("answer")) for row in retain_train
            ],
        }

    return {
        "development": scenario(
            development_forget, development_retain, development_perturbed
        ),
        "confirmation": scenario(final_forget, confirmation_retain, final_perturbed),
        "full": common["full"],
        "real_anchor": common["real_anchor"],
    }


def _evaluate_model(
    model: Any,
    evaluation: Mapping[str, object],
    *,
    collator: QACollator,
    batch_size: int,
    torch_module: Any,
) -> dict[str, object]:
    result: dict[str, object] = {}
    for channel, rows in evaluation.items():
        if channel == "forget_perturbed":
            groups = cast(Sequence[Sequence[Mapping[str, str]]], rows)
            flattened = [row for group in groups for row in group]
            flat_losses = _losses_per_example(
                model,
                flattened,
                collator=collator,
                batch_size=batch_size,
                torch_module=torch_module,
            )
            width = len(groups[0])
            result[channel] = [
                flat_losses[index : index + width]
                for index in range(0, len(flat_losses), width)
            ]
        else:
            result[channel] = _losses_per_example(
                model,
                cast(Sequence[Mapping[str, str]], rows),
                collator=collator,
                batch_size=batch_size,
                torch_module=torch_module,
            )
    return result


def _losses_per_example(
    model: Any,
    rows: Sequence[Mapping[str, str]],
    *,
    collator: QACollator,
    batch_size: int,
    torch_module: Any,
) -> list[float]:
    loader = _loader(
        rows,
        collator=collator,
        batch_size=batch_size,
        seed=0,
        shuffle=False,
        torch_module=torch_module,
    )
    result: list[float] = []
    model.eval()
    with torch_module.inference_mode():
        for batch in loader:
            moved = _move(batch, model.device)
            labels = moved["labels"][:, 1:]
            logits = model(
                input_ids=moved["input_ids"], attention_mask=moved["attention_mask"]
            ).logits[:, :-1, :]
            token_loss = torch_module.nn.functional.cross_entropy(
                logits.float().reshape(-1, logits.shape[-1]),
                labels.reshape(-1),
                ignore_index=-100,
                reduction="none",
            ).reshape_as(labels)
            mask = labels != -100
            per_row = (token_loss * mask).sum(dim=1) / mask.sum(dim=1)
            result.extend(float(value) for value in per_row.detach().cpu())
    return result


def _maximum_difference(left: object, right: object) -> float:
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            raise ValueError("reload evaluation channels differ")
        return max(
            (_maximum_difference(left[key], right[key]) for key in left),
            default=0.0,
        )
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            raise ValueError("reload evaluation shapes differ")
        return max(
            (_maximum_difference(a, b) for a, b in zip(left, right, strict=True)),
            default=0.0,
        )
    return abs(float(left) - float(right))


def _selected_token_ids(
    tokenizer: Any,
    forget_rows: Sequence[Mapping[str, str]],
    utility_rows: Sequence[Mapping[str, str]],
    *,
    fraction: float,
    minimum_frequency: int,
) -> tuple[int, ...]:
    if not 0 < fraction <= 1:
        raise ValueError("selective token fraction must be in (0, 1]")

    def counts(rows: Sequence[Mapping[str, str]]) -> collections.Counter[int]:
        result: collections.Counter[int] = collections.Counter()
        for row in rows:
            result.update(
                int(value)
                for value in tokenizer(
                    row["answer"], add_special_tokens=False, truncation=True
                )["input_ids"]
            )
        return result

    forget_counts = counts(forget_rows)
    utility_counts = counts(utility_rows)
    candidates = [
        token
        for token, count in forget_counts.items()
        if count >= minimum_frequency
        and token not in {tokenizer.eos_token_id, tokenizer.pad_token_id}
    ]
    ranked = sorted(
        candidates,
        key=lambda token: (
            -(forget_counts[token] / (utility_counts[token] + 1)),
            -forget_counts[token],
            token,
        ),
    )
    selected_count = max(1, math.ceil(len(ranked) * fraction)) if ranked else 0
    selected = tuple(sorted(ranked[:selected_count]))
    if not selected:
        raise ValueError("selective token rule produced an empty set")
    return selected


def _selective_answer_loss(model: Any, batch: Mapping[str, Any], token_ids: Any, torch: Any) -> Any:
    moved = _move(batch, model.device)
    labels = moved["labels"]
    logits = model(input_ids=moved["input_ids"], attention_mask=moved["attention_mask"]).logits
    shifted_labels = labels[:, 1:]
    token_loss = torch.nn.functional.cross_entropy(
        logits[:, :-1, :].float().reshape(-1, logits.shape[-1]),
        shifted_labels.reshape(-1),
        ignore_index=-100,
        reduction="none",
    ).reshape_as(shifted_labels)
    valid = shifted_labels != -100
    selective = valid & torch.isin(shifted_labels, token_ids)
    mask = selective if bool(selective.any()) else valid
    return (token_loss * mask).sum() / mask.sum()


def _train_ucsgp(
    model: Any,
    retain_rows: Sequence[Mapping[str, str]],
    forget_rows: Sequence[Mapping[str, str]],
    anchor_rows: Sequence[Mapping[str, str]],
    *,
    protocol: Mapping[str, Any],
    config: Mapping[str, Any],
    collator: QACollator,
    tokenizer: Any,
    seed: int,
    deps: Mapping[str, Any],
) -> tuple[float, int]:
    torch = deps["torch"]
    settings = protocol["training"]
    candidate = protocol["candidate"]
    batch_size = int(settings["micro_batch_size"])
    retain_stream = iter(
        _cycle_loader(retain_rows, collator, batch_size, seed + 101, torch)
    )
    forget_stream = iter(
        _cycle_loader(forget_rows, collator, batch_size, seed + 202, torch)
    )
    anchor_stream = iter(
        _cycle_loader(anchor_rows, collator, batch_size, seed + 303, torch)
    )
    selected = _selected_token_ids(
        tokenizer,
        forget_rows,
        [*retain_rows, *anchor_rows],
        fraction=float(candidate["selective_token_fraction"]),
        minimum_frequency=int(candidate["minimum_forget_token_frequency"]),
    )
    selected_tensor = torch.tensor(selected, device=model.device, dtype=torch.long)
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = torch.optim.AdamW(parameters, lr=float(candidate["learning_rate"]))
    model.train()
    started = time.perf_counter()
    for _ in range(int(candidate["steps"])):
        retain_loss = model(**_move(next(retain_stream), model.device)).loss
        anchor_loss = model(**_move(next(anchor_stream), model.device)).loss
        utility_loss = retain_loss + float(config["anchor_weight"]) * anchor_loss
        utility_gradients = torch.autograd.grad(utility_loss, parameters, allow_unused=True)
        forget_loss = _selective_answer_loss(
            model, next(forget_stream), selected_tensor, torch
        )
        forget_gradients = torch.autograd.grad(-forget_loss, parameters, allow_unused=True)
        pairs = [
            (parameter, utility, forget)
            for parameter, utility, forget in zip(
                parameters, utility_gradients, forget_gradients, strict=True
            )
            if utility is not None and forget is not None
        ]
        if not pairs:
            raise RuntimeError("candidate produced no paired gradients")
        dot = sum((utility * forget).sum() for _, utility, forget in pairs)
        utility_norm = sum((utility * utility).sum() for _, utility, _ in pairs)
        coefficient = torch.minimum(dot / utility_norm.clamp_min(1e-12), torch.zeros_like(dot))
        optimizer.zero_grad(set_to_none=True)
        for parameter, utility, forget in pairs:
            projected_forget = forget - coefficient * utility
            parameter.grad = utility + float(config["forget_weight"]) * projected_forget
        torch.nn.utils.clip_grad_norm_(parameters, float(candidate["gradient_clip_norm"]))
        optimizer.step()
    return time.perf_counter() - started, len(selected)


def _cycle_loader(
    rows: Sequence[Mapping[str, str]],
    collator: QACollator,
    batch_size: int,
    seed: int,
    torch: Any,
) -> Any:
    while True:
        yield from _loader(
            rows,
            collator=collator,
            batch_size=batch_size,
            seed=seed,
            shuffle=True,
            torch_module=torch,
        )
        seed += 1


def _train_baseline(
    model: Any,
    retain_rows: Sequence[Mapping[str, str]],
    forget_rows: Sequence[Mapping[str, str]],
    *,
    protocol: Mapping[str, Any],
    collator: QACollator,
    seed: int,
    deps: Mapping[str, Any],
) -> float:
    torch = deps["torch"]
    settings = protocol["training"]
    baseline = protocol["baseline"]
    batch_size = int(settings["micro_batch_size"])
    retain_stream = iter(_cycle_loader(retain_rows, collator, batch_size, seed + 101, torch))
    forget_stream = iter(_cycle_loader(forget_rows, collator, batch_size, seed + 202, torch))
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = torch.optim.AdamW(parameters, lr=float(baseline["learning_rate"]))
    model.train()
    started = time.perf_counter()
    for _ in range(int(baseline["steps"])):
        retain_loss = model(**_move(next(retain_stream), model.device)).loss
        forget_loss = model(**_move(next(forget_stream), model.device)).loss
        loss = retain_loss - float(baseline["forget_weight"]) * forget_loss
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(parameters, float(baseline["gradient_clip_norm"]))
        optimizer.step()
    return time.perf_counter() - started


def _prepare_seed(
    seed: int,
    scenario: Mapping[str, Any],
    rows: Mapping[str, object],
    *,
    protocol: Mapping[str, Any],
    checkpoint_root: Path,
    collator: QACollator,
    deps: Mapping[str, Any],
) -> dict[str, object]:
    torch = deps["torch"]
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    evaluation = cast(Mapping[str, object], scenario["evaluation"])
    evaluation_batch_size = int(protocol["evaluation"]["batch_size"])
    base = _load_base(protocol, deps)
    base_eval = _evaluate_model(
        base,
        evaluation,
        collator=collator,
        batch_size=evaluation_batch_size,
        torch_module=torch,
    )
    _release(base, torch)

    target = _fresh_adapter(protocol, deps)
    _train_adapter(
        target,
        cast(Sequence[Mapping[str, str]], rows["full"]),
        protocol=protocol,
        collator=collator,
        seed=seed,
        epochs=int(protocol["training"]["target_epochs"]),
        deps=deps,
    )
    target_path = checkpoint_root / f"seed-{seed}-target"
    target.save_pretrained(target_path)
    target_eval = _evaluate_model(
        target,
        evaluation,
        collator=collator,
        batch_size=evaluation_batch_size,
        torch_module=torch,
    )
    _release(target, torch)

    exact = _fresh_adapter(protocol, deps)
    exact_started = time.perf_counter()
    _train_adapter(
        exact,
        cast(Sequence[Mapping[str, str]], scenario["train_retain"]),
        protocol=protocol,
        collator=collator,
        seed=seed,
        epochs=int(protocol["training"]["exact_epochs"]),
        deps=deps,
    )
    exact_runtime = time.perf_counter() - exact_started
    exact_path = checkpoint_root / f"seed-{seed}-exact"
    exact.save_pretrained(exact_path)
    exact_eval = _evaluate_model(
        exact,
        evaluation,
        collator=collator,
        batch_size=evaluation_batch_size,
        torch_module=torch,
    )
    exact_digest = _adapter_digest(exact_path)
    _release(exact, torch)
    return {
        "base": base_eval,
        "exact": exact_eval,
        "exact_digest": exact_digest,
        "exact_runtime": exact_runtime,
        "target": target_eval,
        "target_digest": _adapter_digest(target_path),
        "target_path": target_path,
    }


def _candidate_trial(
    seed: int,
    scenario: Mapping[str, Any],
    prepared: Mapping[str, object],
    rows: Mapping[str, object],
    *,
    protocol: Mapping[str, Any],
    candidate_id: str,
    config: Mapping[str, Any] | None,
    checkpoint_root: Path,
    collator: QACollator,
    tokenizer: Any,
    deps: Mapping[str, Any],
) -> dict[str, object]:
    torch = deps["torch"]
    candidate_base = _load_base(protocol, deps)
    candidate = deps["PeftModel"].from_pretrained(
        candidate_base, prepared["target_path"], is_trainable=True
    )
    if config is None:
        runtime = _train_baseline(
            candidate,
            cast(Sequence[Mapping[str, str]], scenario["train_retain"]),
            cast(Sequence[Mapping[str, str]], scenario["train_forget"]),
            protocol=protocol,
            collator=collator,
            seed=seed,
            deps=deps,
        )
        selected_token_count = 0
    else:
        runtime, selected_token_count = _train_ucsgp(
            candidate,
            cast(Sequence[Mapping[str, str]], scenario["train_retain"]),
            cast(Sequence[Mapping[str, str]], scenario["train_forget"]),
            cast(Sequence[Mapping[str, str]], rows["real_anchor"]),
            protocol=protocol,
            config=config,
            collator=collator,
            tokenizer=tokenizer,
            seed=seed,
            deps=deps,
        )
    candidate_path = checkpoint_root / f"seed-{seed}-{candidate_id}"
    candidate.save_pretrained(candidate_path)
    candidate_eval = _evaluate_model(
        candidate,
        cast(Mapping[str, object], scenario["evaluation"]),
        collator=collator,
        batch_size=int(protocol["evaluation"]["batch_size"]),
        torch_module=torch,
    )
    candidate_digest = _adapter_digest(candidate_path)
    _release(candidate, torch)
    reloaded_base = _load_base(protocol, deps)
    reloaded = deps["PeftModel"].from_pretrained(reloaded_base, candidate_path)
    reloaded_eval = _evaluate_model(
        reloaded,
        cast(Mapping[str, object], scenario["evaluation"]),
        collator=collator,
        batch_size=int(protocol["evaluation"]["batch_size"]),
        torch_module=torch,
    )
    recurrence = _maximum_difference(candidate_eval, reloaded_eval)
    _release(reloaded, torch)
    evaluations = {
        "base": prepared["base"],
        "target": prepared["target"],
        "exact": prepared["exact"],
        "candidate": candidate_eval,
        "candidate_reloaded": reloaded_eval,
    }
    return {
        "adapter_sha256": {
            "candidate": candidate_digest,
            "exact": prepared["exact_digest"],
            "target": prepared["target_digest"],
        },
        "candidate_id": candidate_id,
        "evaluations": evaluations,
        "metrics": score_v2_trial(
            cast(Mapping[str, Mapping[str, object]], evaluations),
            recurrence_after_reload=recurrence,
            candidate_runtime_seconds=runtime,
            exact_runtime_seconds=float(prepared["exact_runtime"]),
        ),
        "seed": seed,
        "selected_token_count": selected_token_count,
    }


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(_canonical(value) + b"\n")


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.write_bytes(b"".join(_canonical(row) + b"\n" for row in rows))


def run(protocol_path: Path, output: Path, *, code_revision: str) -> dict[str, object]:
    protocol = cast(dict[str, Any], json.loads(protocol_path.read_text()))
    deps = _load_dependencies()
    torch = deps["torch"]
    if not torch.cuda.is_available():
        raise RuntimeError("a CUDA GPU is required for the frozen Kaggle experiment")
    output.mkdir(parents=True, exist_ok=False)
    checkpoint_root = output / "adapters"
    checkpoint_root.mkdir()
    model_source = os.environ.get("ERASEMAP_MODEL_PATH", protocol["model"]["repository"])
    tokenizer_options = (
        {"revision": protocol["model"]["revision"]}
        if model_source == protocol["model"]["repository"]
        else {"local_files_only": True}
    )
    tokenizer = deps["AutoTokenizer"].from_pretrained(model_source, **tokenizer_options)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    collator = QACollator(tokenizer, int(protocol["training"]["max_length"]), torch)
    rows = _load_rows(protocol, deps)
    development = cast(Mapping[str, Any], rows["development"])
    confirmation = cast(Mapping[str, Any], rows["confirmation"])

    development_trials: dict[str, list[dict[str, object]]] = {
        str(config["id"]): [] for config in protocol["candidate"]["development_grid"]
    }
    configs = {str(config["id"]): config for config in protocol["candidate"]["development_grid"]}
    for seed_value in protocol["development_seeds"]:
        seed = int(seed_value)
        prepared = _prepare_seed(
            seed,
            development,
            rows,
            protocol=protocol,
            checkpoint_root=checkpoint_root,
            collator=collator,
            deps=deps,
        )
        for candidate_id, config in configs.items():
            development_trials[candidate_id].append(
                _candidate_trial(
                    seed,
                    development,
                    prepared,
                    rows,
                    protocol=protocol,
                    candidate_id=candidate_id,
                    config=config,
                    checkpoint_root=checkpoint_root,
                    collator=collator,
                    tokenizer=tokenizer,
                    deps=deps,
                )
            )
        _release(prepared, torch)

    development_summaries = []
    for candidate_id, trials in development_trials.items():
        summary = summarize_v2_trials(trials, protocol["success_criteria"])
        development_summaries.append({"candidate_id": candidate_id, **summary})
    selected_id = select_development_candidate(
        development_summaries, protocol["development_selection_criteria"]
    )
    selected_config = configs[selected_id]
    _write_json(
        output / "development.json",
        {
            "selected_candidate_id": selected_id,
            "selection_uses_confirmation": False,
            "summaries": development_summaries,
            "trials": development_trials,
        },
    )

    trials: list[dict[str, object]] = []
    baseline_trials: list[dict[str, object]] = []
    for seed_value in protocol["confirmation_seeds"]:
        seed = int(seed_value)
        prepared = _prepare_seed(
            seed,
            confirmation,
            rows,
            protocol=protocol,
            checkpoint_root=checkpoint_root,
            collator=collator,
            deps=deps,
        )
        trials.append(
            _candidate_trial(
                seed,
                confirmation,
                prepared,
                rows,
                protocol=protocol,
                candidate_id=selected_id,
                config=selected_config,
                checkpoint_root=checkpoint_root,
                collator=collator,
                tokenizer=tokenizer,
                deps=deps,
            )
        )
        baseline_trials.append(
            _candidate_trial(
                seed,
                confirmation,
                prepared,
                rows,
                protocol=protocol,
                candidate_id=str(protocol["baseline"]["id"]),
                config=None,
                checkpoint_root=checkpoint_root,
                collator=collator,
                tokenizer=tokenizer,
                deps=deps,
            )
        )
        _release(prepared, torch)
    _write_jsonl(output / "trials.jsonl", trials)
    _write_jsonl(output / "baseline_trials.jsonl", baseline_trials)
    computed = summarize_v2_trials(trials, protocol["success_criteria"])
    baseline_summary = summarize_v2_trials(baseline_trials, protocol["success_criteria"])
    summary = {
        **computed,
        "baseline": baseline_summary,
        "claim_boundary": protocol["evidence_boundary"],
        "code_revision": code_revision,
        "dataset_revision": protocol["dataset"]["revision"],
        "development_candidate_count": len(configs),
        "development_seed_count": len(protocol["development_seeds"]),
        "environment": {
            "cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "model_revision": protocol["model"]["revision"],
        "protocol_sha256": _sha256(protocol_path),
        "schema_version": "erasemap-qwen-tofu-kaggle-result-v2",
        "selected_candidate_id": selected_id,
        "trial_count": len(trials),
    }
    summary_path = output / "summary.json"
    _write_json(summary_path, summary)
    manifest_files = (
        "baseline_trials.jsonl",
        "development.json",
        "summary.json",
        "trials.jsonl",
    )
    manifest = {
        "files": {name: _sha256(output / name) for name in manifest_files},
        "protocol_sha256": _sha256(protocol_path),
    }
    _write_json(output / "MANIFEST.sha256.json", manifest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frozen Qwen-TOFU Kaggle v2")
    parser.add_argument(
        "--protocol", type=Path, default=ROOT / "benchmark/qwen-tofu-kaggle-v2.json"
    )
    parser.add_argument("--output", type=Path, default=Path("/kaggle/working/qwen-tofu-v2"))
    parser.add_argument("--code-revision", default=os.environ.get("ERASEMAP_CODE_REVISION"))
    args = parser.parse_args()
    result = run(args.protocol, args.output, code_revision=args.code_revision or _git_revision())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
