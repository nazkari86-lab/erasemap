from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import random
import subprocess
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from erasemap.llm_unlearning import score_trial, summarize_trials

ROOT = Path(__file__).resolve().parents[1]


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _even_sample(rows: Sequence[Mapping[str, str]], count: int) -> list[Mapping[str, str]]:
    if count <= 0 or len(rows) < count:
        raise ValueError(f"cannot take {count} rows from {len(rows)}")
    return [rows[(index * len(rows)) // count] for index in range(count)]


def _load_dependencies() -> dict[str, Any]:
    try:
        import torch
        from datasets import load_dataset
        from peft import (
            LoraConfig,
            PeftModel,
            get_peft_model,
            prepare_model_for_kbit_training,
        )
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    except ImportError as error:
        raise RuntimeError(
            "GPU dependencies are missing; install torch, transformers, datasets, peft, "
            "accelerate, and bitsandbytes"
        ) from error
    return {
        "AutoModelForCausalLM": AutoModelForCausalLM,
        "AutoTokenizer": AutoTokenizer,
        "BitsAndBytesConfig": BitsAndBytesConfig,
        "LoraConfig": LoraConfig,
        "PeftModel": PeftModel,
        "get_peft_model": get_peft_model,
        "load_dataset": load_dataset,
        "prepare_model_for_kbit_training": prepare_model_for_kbit_training,
        "torch": torch,
    }


class QACollator:
    def __init__(self, tokenizer: Any, max_length: int, torch_module: Any) -> None:
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.torch = torch_module

    def __call__(self, rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
        encoded: list[tuple[list[int], list[int]]] = []
        for row in rows:
            prompt = f"Question: {row['question']}\nAnswer:"
            full = f"{prompt} {row['answer']}{self.tokenizer.eos_token}"
            prompt_ids = self.tokenizer(
                prompt, add_special_tokens=True, truncation=True, max_length=self.max_length
            )["input_ids"]
            full_ids = self.tokenizer(
                full, add_special_tokens=True, truncation=True, max_length=self.max_length
            )["input_ids"]
            labels = [-100] * min(len(prompt_ids), len(full_ids)) + full_ids[len(prompt_ids) :]
            if not any(label != -100 for label in labels):
                raise ValueError("answer was truncated completely")
            encoded.append((full_ids, labels))
        width = max(len(input_ids) for input_ids, _ in encoded)
        pad_id = int(self.tokenizer.pad_token_id)
        input_batch: list[list[int]] = []
        label_batch: list[list[int]] = []
        masks: list[list[int]] = []
        for input_ids, labels in encoded:
            padding = width - len(input_ids)
            input_batch.append(input_ids + [pad_id] * padding)
            label_batch.append(labels + [-100] * padding)
            masks.append([1] * len(input_ids) + [0] * padding)
        return {
            "attention_mask": self.torch.tensor(masks, dtype=self.torch.long),
            "input_ids": self.torch.tensor(input_batch, dtype=self.torch.long),
            "labels": self.torch.tensor(label_batch, dtype=self.torch.long),
        }


def _move(batch: Mapping[str, Any], device: Any) -> dict[str, Any]:
    return {name: value.to(device) for name, value in batch.items()}


def _loader(
    rows: Sequence[Mapping[str, str]],
    *,
    collator: QACollator,
    batch_size: int,
    seed: int,
    shuffle: bool,
    torch_module: Any,
) -> Any:
    generator = torch_module.Generator().manual_seed(seed)
    return torch_module.utils.data.DataLoader(
        list(rows),
        batch_size=batch_size,
        collate_fn=collator,
        generator=generator,
        shuffle=shuffle,
    )


def _infinite(loader: Iterable[Mapping[str, Any]]) -> Iterator[Mapping[str, Any]]:
    while True:
        yield from loader


def _load_base(protocol: Mapping[str, Any], deps: Mapping[str, Any]) -> Any:
    model_spec = protocol["model"]
    quantization = deps["BitsAndBytesConfig"](
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=deps["torch"].float16,
        bnb_4bit_use_double_quant=True,
    )
    model = deps["AutoModelForCausalLM"].from_pretrained(
        model_spec["repository"],
        revision=model_spec["revision"],
        device_map={"": 0},
        quantization_config=quantization,
        torch_dtype=deps["torch"].float16,
    )
    model.config.use_cache = False
    return model


def _fresh_adapter(protocol: Mapping[str, Any], deps: Mapping[str, Any]) -> Any:
    model = _load_base(protocol, deps)
    model = deps["prepare_model_for_kbit_training"](model, use_gradient_checkpointing=True)
    settings = protocol["training"]
    config = deps["LoraConfig"](
        r=int(settings["lora_rank"]),
        lora_alpha=int(settings["lora_alpha"]),
        lora_dropout=float(settings["lora_dropout"]),
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=list(settings["target_modules"]),
    )
    return deps["get_peft_model"](model, config)


def _train_adapter(
    model: Any,
    rows: Sequence[Mapping[str, str]],
    *,
    protocol: Mapping[str, Any],
    collator: QACollator,
    seed: int,
    epochs: int,
    deps: Mapping[str, Any],
) -> None:
    torch = deps["torch"]
    settings = protocol["training"]
    loader = _loader(
        rows,
        collator=collator,
        batch_size=int(settings["micro_batch_size"]),
        seed=seed,
        shuffle=True,
        torch_module=torch,
    )
    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=float(settings["learning_rate"]),
        weight_decay=float(settings["weight_decay"]),
    )
    accumulation = int(settings["gradient_accumulation_steps"])
    model.train()
    optimizer.zero_grad(set_to_none=True)
    for _ in range(epochs):
        for batch_index, batch in enumerate(loader, start=1):
            loss = model(**_move(batch, model.device)).loss / accumulation
            loss.backward()
            if batch_index % accumulation == 0 or batch_index == len(loader):
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)


def _train_candidate(
    model: Any,
    retain_rows: Sequence[Mapping[str, str]],
    forget_rows: Sequence[Mapping[str, str]],
    *,
    protocol: Mapping[str, Any],
    collator: QACollator,
    seed: int,
    deps: Mapping[str, Any],
) -> None:
    torch = deps["torch"]
    settings = protocol["training"]
    candidate = protocol["candidate"]
    retain_loader = _loader(
        retain_rows,
        collator=collator,
        batch_size=int(settings["micro_batch_size"]),
        seed=seed + 101,
        shuffle=True,
        torch_module=torch,
    )
    forget_loader = _loader(
        forget_rows,
        collator=collator,
        batch_size=int(settings["micro_batch_size"]),
        seed=seed + 202,
        shuffle=True,
        torch_module=torch,
    )
    retain_stream = _infinite(retain_loader)
    forget_stream = _infinite(forget_loader)
    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=float(candidate["learning_rate"]),
    )
    model.train()
    for _ in range(int(candidate["steps"])):
        retain_loss = model(**_move(next(retain_stream), model.device)).loss
        forget_loss = model(**_move(next(forget_stream), model.device)).loss
        loss = retain_loss - float(candidate["forget_weight"]) * forget_loss
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            (parameter for parameter in model.parameters() if parameter.requires_grad),
            float(candidate["gradient_clip_norm"]),
        )
        optimizer.step()


def _losses(
    model: Any,
    rows: Sequence[Mapping[str, str]],
    *,
    collator: QACollator,
    torch_module: Any,
) -> list[float]:
    loader = _loader(
        rows,
        collator=collator,
        batch_size=1,
        seed=0,
        shuffle=False,
        torch_module=torch_module,
    )
    result: list[float] = []
    model.eval()
    with torch_module.inference_mode():
        for batch in loader:
            result.append(float(model(**_move(batch, model.device)).loss.detach().cpu()))
    return result


def _evaluate(
    model: Any,
    evaluation_rows: Mapping[str, Sequence[Mapping[str, str]]],
    *,
    collator: QACollator,
    torch_module: Any,
) -> dict[str, list[float]]:
    return {
        dataset_id: _losses(model, rows, collator=collator, torch_module=torch_module)
        for dataset_id, rows in evaluation_rows.items()
    }


def _release(model: Any, torch_module: Any) -> None:
    del model
    gc.collect()
    torch_module.cuda.empty_cache()


def _adapter_digest(path: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(item for item in path.rglob("*") if item.is_file())
    for item in files:
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(item.read_bytes())
    return "sha256:" + digest.hexdigest()


def _load_rows(
    protocol: Mapping[str, Any], deps: Mapping[str, Any]
) -> dict[str, list[Mapping[str, str]]]:
    dataset = protocol["dataset"]
    evaluation = protocol["evaluation"]
    load_dataset = deps["load_dataset"]

    def config(name: str) -> list[Mapping[str, str]]:
        loaded = load_dataset(
            dataset["repository"], dataset[name], revision=dataset["revision"], split="train"
        )
        return [cast(Mapping[str, str], row) for row in loaded]

    full = config("full")
    retain = config("retain")
    forget = config("forget")
    return {
        "train_full": full,
        "train_retain": retain,
        "train_forget": forget,
        "forget": _even_sample(forget, int(evaluation["forget_rows"])),
        "forget_perturbed": _even_sample(
            config("forget_perturbed"), int(evaluation["forget_perturbed_rows"])
        ),
        "holdout": _even_sample(config("holdout"), int(evaluation["holdout_rows"])),
        "retain": _even_sample(retain, int(evaluation["retain_rows"])),
        "retain_perturbed": _even_sample(
            config("retain_perturbed"), int(evaluation["retain_perturbed_rows"])
        ),
        "world_facts": _even_sample(
            config("world_facts"), int(evaluation["world_facts_rows"])
        ),
    }


def run(protocol_path: Path, output: Path, *, code_revision: str) -> dict[str, object]:
    protocol = cast(dict[str, Any], json.loads(protocol_path.read_text()))
    deps = _load_dependencies()
    torch = deps["torch"]
    if not torch.cuda.is_available():
        raise RuntimeError("a CUDA GPU is required for the frozen Kaggle experiment")
    output.mkdir(parents=True, exist_ok=False)
    checkpoint_root = output / "adapters"
    checkpoint_root.mkdir()
    tokenizer = deps["AutoTokenizer"].from_pretrained(
        protocol["model"]["repository"], revision=protocol["model"]["revision"]
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    collator = QACollator(tokenizer, int(protocol["training"]["max_length"]), torch)
    rows = _load_rows(protocol, deps)
    evaluation_rows = {
        key: value for key, value in rows.items() if not key.startswith("train_")
    }
    trials: list[dict[str, object]] = []
    trials_path = output / "trials.jsonl"

    for seed_value in protocol["random_seeds"]:
        seed = int(seed_value)
        random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)

        base = _load_base(protocol, deps)
        base_losses = _evaluate(base, evaluation_rows, collator=collator, torch_module=torch)
        _release(base, torch)

        target = _fresh_adapter(protocol, deps)
        _train_adapter(
            target,
            rows["train_full"],
            protocol=protocol,
            collator=collator,
            seed=seed,
            epochs=int(protocol["training"]["target_epochs"]),
            deps=deps,
        )
        target_path = checkpoint_root / f"seed-{seed}-target"
        target.save_pretrained(target_path)
        target_losses = _evaluate(target, evaluation_rows, collator=collator, torch_module=torch)
        _release(target, torch)

        exact = _fresh_adapter(protocol, deps)
        _train_adapter(
            exact,
            rows["train_retain"],
            protocol=protocol,
            collator=collator,
            seed=seed,
            epochs=int(protocol["training"]["exact_epochs"]),
            deps=deps,
        )
        exact_path = checkpoint_root / f"seed-{seed}-exact"
        exact.save_pretrained(exact_path)
        exact_losses = _evaluate(exact, evaluation_rows, collator=collator, torch_module=torch)
        _release(exact, torch)

        candidate_base = _load_base(protocol, deps)
        candidate = deps["PeftModel"].from_pretrained(
            candidate_base, target_path, is_trainable=True
        )
        _train_candidate(
            candidate,
            rows["train_retain"],
            rows["train_forget"],
            protocol=protocol,
            collator=collator,
            seed=seed,
            deps=deps,
        )
        candidate_path = checkpoint_root / f"seed-{seed}-candidate"
        candidate.save_pretrained(candidate_path)
        candidate_losses = _evaluate(
            candidate, evaluation_rows, collator=collator, torch_module=torch
        )
        _release(candidate, torch)

        reloaded_base = _load_base(protocol, deps)
        reloaded = deps["PeftModel"].from_pretrained(reloaded_base, candidate_path)
        reloaded_losses = _evaluate(
            reloaded, evaluation_rows, collator=collator, torch_module=torch
        )
        recurrence = max(
            abs(left - right)
            for dataset_id in evaluation_rows
            for left, right in zip(
                candidate_losses[dataset_id], reloaded_losses[dataset_id], strict=True
            )
        )
        _release(reloaded, torch)

        loss_matrix = {
            "base": base_losses,
            "target": target_losses,
            "exact": exact_losses,
            "candidate": candidate_losses,
            "candidate_reloaded": reloaded_losses,
        }
        trial: dict[str, object] = {
            "adapter_sha256": {
                "candidate": _adapter_digest(candidate_path),
                "exact": _adapter_digest(exact_path),
                "target": _adapter_digest(target_path),
            },
            "losses": loss_matrix,
            "metrics": score_trial(loss_matrix, recurrence_after_reload=recurrence),
            "seed": seed,
        }
        trials.append(trial)
        with trials_path.open("a") as stream:
            stream.write(_canonical(trial).decode() + "\n")

    computed = summarize_trials(trials, protocol["success_criteria"])
    summary = {
        **computed,
        "claim_boundary": protocol["evidence_boundary"],
        "code_revision": code_revision,
        "dataset_revision": protocol["dataset"]["revision"],
        "environment": {
            "cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "model_revision": protocol["model"]["revision"],
        "protocol_sha256": _sha256(protocol_path),
        "schema_version": "erasemap-qwen-tofu-kaggle-result-v1",
        "trial_count": len(trials),
    }
    summary_path = output / "summary.json"
    summary_path.write_bytes(_canonical(summary) + b"\n")
    manifest = {
        "protocol_sha256": _sha256(protocol_path),
        "summary_sha256": _sha256(summary_path),
        "trials_sha256": _sha256(trials_path),
    }
    (output / "MANIFEST.sha256.json").write_bytes(_canonical(manifest) + b"\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run preregistered Qwen-TOFU Kaggle v1")
    parser.add_argument(
        "--protocol", type=Path, default=ROOT / "benchmark/qwen-tofu-kaggle-v1.json"
    )
    parser.add_argument("--output", type=Path, default=Path("/kaggle/working/qwen-tofu-v1"))
    parser.add_argument("--code-revision", default=os.environ.get("ERASEMAP_CODE_REVISION"))
    args = parser.parse_args()
    revision = args.code_revision or _git_revision()
    result = run(args.protocol, args.output, code_revision=revision)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
