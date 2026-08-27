from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, ClassVar, cast

from erasemap.llm_unlearning_v2 import score_v2_trial, summarize_v2_trials
from erasemap.llm_unlearning_v3 import (
    NoRobustCandidateError,
    PathPoint,
    robust_intervals,
    select_robust_point,
    summarize_path_point,
)
from experiments.qwen_tofu_v3_data import (
    ConfirmationView,
    DeletionFold,
    DevelopmentView,
    compute_selection_commitment,
    load_confirmation_view,
    load_development_view,
    row_fingerprint,
)
from experiments.run_qwen_tofu_kaggle_v1 import (
    QACollator,
    _adapter_digest,
    _even_sample,
    _fresh_adapter,
    _load_base,
    _load_dependencies,
    _move,
    _release,
    _train_adapter,
)
from experiments.run_qwen_tofu_kaggle_v2 import (
    _candidate_trial,
    _cycle_loader,
    _evaluate_model,
    _maximum_difference,
    _normal,
    _semantic_forget_rows,
)

ROOT = Path(__file__).resolve().parents[1]


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class EvidenceJournal:
    """Append-only evidence writer with a digest-linked phase state machine."""

    _STATE_FILES: ClassVar[dict[str, str]] = {
        "INITIAL": "state-00-initial.json",
        "DEVELOPMENT_COMPLETE": "state-01-development-complete.json",
        "SELECTION_COMMITTED": "state-02-selection-committed.json",
        "CONFIRMATION_COMPLETE": "state-03-confirmation-complete.json",
        "SECONDARY_COMPLETE": "state-04-secondary-complete.json",
        "SEALED": "state-05-sealed.json",
    }

    def __init__(self, root: Path, *, protocol_path: Path, code_revision: str) -> None:
        if root.exists():
            raise FileExistsError(f"refusing to overwrite evidence directory: {root}")
        if len(code_revision) != 40 or any(
            value not in "0123456789abcdef" for value in code_revision
        ):
            raise ValueError("code revision must be a full lowercase git SHA-1")
        protocol = json.loads(protocol_path.read_text())
        if not isinstance(protocol, dict) or protocol.get("status") != (
            "FROZEN_BEFORE_FIRST_V3_GPU_RUN"
        ):
            raise ValueError("v3 protocol must be frozen")
        self.root = root
        self.protocol_path = protocol_path
        self.protocol = cast(Mapping[str, object], protocol)
        self.protocol_sha256 = _sha256(protocol_path)
        self.code_revision = code_revision
        self.state = "INITIAL"
        self._last_state: Path | None = None
        root.mkdir(parents=True, exist_ok=False)
        self._transition(
            "INITIAL",
            {
                "code_revision": code_revision,
                "protocol_sha256": self.protocol_sha256,
                "scientific_inputs_frozen": True,
            },
            expected=None,
        )

    def _write_once(self, name: str, value: object, *, jsonl: bool = False) -> Path:
        path = self.root / name
        if path.exists():
            raise FileExistsError(f"refusing to overwrite evidence file: {path}")
        if jsonl:
            rows = cast(Sequence[Mapping[str, object]], value)
            path.write_bytes(b"".join(_canonical(row) + b"\n" for row in rows))
        else:
            path.write_bytes(_canonical(value) + b"\n")
        return path

    def _transition(
        self,
        next_state: str,
        payload: Mapping[str, object],
        *,
        expected: str | None,
    ) -> None:
        if expected is not None and self.state != expected:
            raise ValueError(f"invalid state transition: {self.state} -> {next_state}")
        state_file = self._STATE_FILES[next_state]
        value = {
            "payload": dict(payload),
            "previous_state_sha256": (
                _sha256(self._last_state) if self._last_state is not None else None
            ),
            "schema_version": "erasemap-qwen-tofu-v3-state-v1",
            "state": next_state,
        }
        self._last_state = self._write_once(state_file, value)
        self.state = next_state

    def complete_development(self, development: Mapping[str, object]) -> None:
        decision = development.get("decision")
        if decision not in {"CANDIDATE_AVAILABLE", "NO_CANDIDATE", "NON_SCIENTIFIC_SMOKE"}:
            raise ValueError("invalid development decision")
        path = self._write_once("development.json", development)
        self._transition(
            "DEVELOPMENT_COMPLETE",
            {"decision": decision, "development_sha256": _sha256(path)},
            expected="INITIAL",
        )

    def commit_selection(self, selection: Mapping[str, object]) -> Mapping[str, object]:
        if self.state != "DEVELOPMENT_COMPLETE":
            raise ValueError("development must complete before selection")
        development = json.loads((self.root / "development.json").read_text())
        if development.get("decision") != "CANDIDATE_AVAILABLE":
            raise ValueError("selection commitment requires an available candidate")
        value = dict(selection)
        value["protocol_sha256"] = self.protocol_sha256
        value["code_revision"] = self.code_revision
        value["selection_commitment"] = compute_selection_commitment(value)
        path = self._write_once("selection.json", value)
        self._transition(
            "SELECTION_COMMITTED",
            {
                "selection_commitment": value["selection_commitment"],
                "selection_sha256": _sha256(path),
            },
            expected="DEVELOPMENT_COMPLETE",
        )
        return value

    def begin_confirmation(self) -> Mapping[str, object]:
        selection_path = self.root / "selection.json"
        if self.state != "SELECTION_COMMITTED" or not selection_path.is_file():
            raise ValueError("selection commitment is required before confirmation")
        value = json.loads(selection_path.read_text())
        if not isinstance(value, dict) or value.get("selection_commitment") != (
            compute_selection_commitment(value)
        ):
            raise ValueError("selection commitment is invalid")
        return cast(Mapping[str, object], value)

    def complete_confirmation(
        self,
        trials: Sequence[Mapping[str, object]],
        baseline_trials: Sequence[Mapping[str, object]],
    ) -> None:
        self.begin_confirmation()
        trial_path = self._write_once("trials.jsonl", trials, jsonl=True)
        baseline_path = self._write_once("baseline_trials.jsonl", baseline_trials, jsonl=True)
        self._transition(
            "CONFIRMATION_COMPLETE",
            {
                "baseline_trials_sha256": _sha256(baseline_path),
                "trial_count": len(trials),
                "trials_sha256": _sha256(trial_path),
            },
            expected="SELECTION_COMMITTED",
        )

    def complete_secondary(self, trials: Sequence[Mapping[str, object]]) -> None:
        path = self._write_once("secondary_trials.jsonl", trials, jsonl=True)
        self._transition(
            "SECONDARY_COMPLETE",
            {"secondary_trial_count": len(trials), "secondary_trials_sha256": _sha256(path)},
            expected="CONFIRMATION_COMPLETE",
        )

    def _seal(self, summary: Mapping[str, object], *, expected: str) -> dict[str, object]:
        value = {
            **summary,
            "code_revision": self.code_revision,
            "protocol_sha256": self.protocol_sha256,
            "schema_version": "erasemap-qwen-tofu-kaggle-result-v3",
        }
        summary_path = self._write_once("summary.json", value)
        self._transition(
            "SEALED",
            {"decision": value["decision"], "summary_sha256": _sha256(summary_path)},
            expected=expected,
        )
        manifest_files = sorted(
            path.name
            for path in self.root.iterdir()
            if path.is_file() and path.name != "MANIFEST.sha256.json"
        )
        self._write_once(
            "MANIFEST.sha256.json",
            {
                "files": {name: _sha256(self.root / name) for name in manifest_files},
                "protocol_sha256": self.protocol_sha256,
            },
        )
        return value

    def seal_no_candidate(self) -> dict[str, object]:
        development = json.loads((self.root / "development.json").read_text())
        if development.get("decision") != "NO_CANDIDATE":
            raise ValueError("NO_CANDIDATE seal requires that development outcome")
        return self._seal(
            {
                "decision": "NO_CANDIDATE",
                "scientific": True,
                "confirmation_loaded": False,
            },
            expected="DEVELOPMENT_COMPLETE",
        )

    def seal_smoke(self) -> dict[str, object]:
        development = json.loads((self.root / "development.json").read_text())
        if development.get("decision") != "NON_SCIENTIFIC_SMOKE":
            raise ValueError("smoke seal requires a smoke development outcome")
        return self._seal(
            {
                "decision": "NON_SCIENTIFIC_SMOKE",
                "scientific": False,
                "confirmation_loaded": False,
            },
            expected="DEVELOPMENT_COMPLETE",
        )

    def seal_scientific(self, summary: Mapping[str, object]) -> dict[str, object]:
        if summary.get("decision") not in {"PASS", "FAIL"}:
            raise ValueError("scientific confirmation decision must be PASS or FAIL")
        return self._seal(summary, expected="SECONDARY_COMPLETE")


def run_smoke(protocol_path: Path, output: Path, *, code_revision: str) -> dict[str, object]:
    journal = EvidenceJournal(
        output,
        protocol_path=protocol_path,
        code_revision=code_revision,
    )
    journal.complete_development(
        {
            "decision": "NON_SCIENTIFIC_SMOKE",
            "selection_uses_confirmation": False,
            "trials": [],
        }
    )
    return journal.seal_smoke()


def _dataset_rows(
    protocol: Mapping[str, Any], deps: Mapping[str, Any], config_key: str
) -> list[Mapping[str, Any]]:
    dataset_root_value = os.environ.get("ERASEMAP_TOFU_PATH")
    if not dataset_root_value:
        raise RuntimeError("ERASEMAP_TOFU_PATH is required for pinned offline v3 data")
    dataset_root = Path(dataset_root_value)
    dataset = protocol["dataset"]
    path = dataset_root / f"{dataset[config_key]}.json"
    if not path.is_file():
        raise RuntimeError(f"pinned TOFU asset is missing: {path.name}")
    loaded = deps["load_dataset"]("json", data_files=str(path), split="train")
    return [cast(Mapping[str, Any], row) for row in loaded]


def _verify_source_assets(protocol: Mapping[str, Any]) -> None:
    dataset_root_value = os.environ.get("ERASEMAP_TOFU_PATH")
    if not dataset_root_value:
        raise RuntimeError("ERASEMAP_TOFU_PATH is required")
    root = Path(dataset_root_value)
    dataset = protocol["dataset"]
    expected = protocol["author_blocks"]["source_sha256"]
    for config_key, hash_key in (
        ("author_source", "forget10"),
        ("author_source_perturbed", "forget10_perturbed"),
    ):
        path = root / f"{dataset[config_key]}.json"
        if not path.is_file() or _sha256(path) != expected[hash_key]:
            raise RuntimeError(f"pinned TOFU source hash mismatch: {path.name}")


def _normal_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [_normal(row.get("question"), row.get("answer")) for row in rows]


def _load_common_inputs(protocol: Mapping[str, Any], deps: Mapping[str, Any]) -> dict[str, object]:
    _verify_source_assets(protocol)
    direct = _dataset_rows(protocol, deps, "author_source")
    perturbed = _dataset_rows(protocol, deps, "author_source_perturbed")
    full = _normal_rows(_dataset_rows(protocol, deps, "full"))
    evaluation = protocol["evaluation"]
    holdout = _normal_rows(
        _even_sample(
            _dataset_rows(protocol, deps, "holdout"),
            int(evaluation["holdout_rows"]),
        )
    )
    world = _normal_rows(
        _even_sample(
            _dataset_rows(protocol, deps, "world_facts"),
            int(evaluation["world_facts_rows"]),
        )
    )
    real = _dataset_rows(protocol, deps, "real_authors")
    anchor_count = int(evaluation["real_author_anchor_rows"])
    test_count = int(evaluation["real_author_test_rows"])
    real_anchor = _normal_rows(real[::2][:anchor_count])
    real_test = _normal_rows(real[1::2][:test_count])
    if len(real_anchor) != anchor_count or len(real_test) != test_count:
        raise ValueError("real-author anchor/test rows are incomplete")
    if {row["answer"].casefold() for row in real_anchor} & {
        row["answer"].casefold() for row in real_test
    }:
        raise ValueError("real-author identities overlap")
    return {
        "direct": direct,
        "full": full,
        "holdout": holdout,
        "perturbed": perturbed,
        "real_anchor": real_anchor,
        "real_test": real_test,
        "world": world,
    }


def _development_view(inputs: Mapping[str, object], protocol_path: Path) -> DevelopmentView:
    return load_development_view(
        cast(Sequence[Mapping[str, object]], inputs["direct"]),
        cast(Sequence[Mapping[str, object]], inputs["perturbed"]),
        protocol_path=protocol_path,
        holdout_rows=cast(Sequence[Mapping[str, object]], inputs["holdout"]),
        world_fact_rows=cast(Sequence[Mapping[str, object]], inputs["world"]),
        real_anchor_rows=cast(Sequence[Mapping[str, object]], inputs["real_anchor"]),
        real_test_rows=cast(Sequence[Mapping[str, object]], inputs["real_test"]),
    )


def _confirmation_view(
    inputs: Mapping[str, object],
    protocol_path: Path,
    selection_path: Path,
) -> ConfirmationView:
    return load_confirmation_view(
        cast(Sequence[Mapping[str, object]], inputs["direct"]),
        cast(Sequence[Mapping[str, object]], inputs["perturbed"]),
        protocol_path=protocol_path,
        selection_path=selection_path,
        expected_protocol_sha256=_sha256(protocol_path),
        holdout_rows=cast(Sequence[Mapping[str, object]], inputs["holdout"]),
        world_fact_rows=cast(Sequence[Mapping[str, object]], inputs["world"]),
        real_test_rows=cast(Sequence[Mapping[str, object]], inputs["real_test"]),
    )


def _scenario(
    fold: DeletionFold,
    inputs: Mapping[str, object],
    *,
    protocol: Mapping[str, Any],
) -> dict[str, object]:
    direct, paraphrase, perturbed = _semantic_forget_rows(
        cast(Sequence[Mapping[str, Any]], fold.perturbed),
        expected_perturbations=int(protocol["evaluation"]["perturbed_answers_per_row"]),
    )
    forget_fingerprints = {row_fingerprint(row) for row in fold.direct}
    full = cast(Sequence[Mapping[str, str]], inputs["full"])
    retain = [row for row in full if row_fingerprint(row) not in forget_fingerprints]
    expected = len(full) - len(fold.direct)
    if len(retain) != expected:
        raise ValueError("exact-retraining retain set has unexpected size")
    return {
        "evaluation": {
            "forget_answer": direct,
            "forget_paraphrase": paraphrase,
            "forget_perturbed": perturbed,
            "holdout": inputs["holdout"],
            "real_authors": inputs["real_test"],
            "retain": _even_sample(retain, int(protocol["evaluation"]["retain_rows"])),
            "world_facts": inputs["world"],
        },
        "train_forget": _normal_rows(cast(Sequence[Mapping[str, Any]], fold.direct)),
        "train_retain": retain,
    }


def _train_target_once(
    seed: int,
    inputs: Mapping[str, object],
    *,
    protocol: Mapping[str, Any],
    checkpoint_root: Path,
    collator: QACollator,
    deps: Mapping[str, Any],
) -> Path:
    torch = deps["torch"]
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    target = _fresh_adapter(protocol, deps)
    _train_adapter(
        target,
        cast(Sequence[Mapping[str, str]], inputs["full"]),
        protocol=protocol,
        collator=collator,
        seed=seed,
        epochs=int(protocol["training"]["target_epochs"]),
        deps=deps,
    )
    path = checkpoint_root / f"seed-{seed}-target"
    target.save_pretrained(path)
    _release(target, torch)
    return path


def _prepare_fold(
    seed: int,
    scenario: Mapping[str, Any],
    target_path: Path,
    *,
    protocol: Mapping[str, Any],
    collator: QACollator,
    deps: Mapping[str, Any],
) -> dict[str, object]:
    from experiments.qwen_tofu_v3_rbep import adapter_sha256

    torch = deps["torch"]
    evaluation = cast(Mapping[str, object], scenario["evaluation"])
    batch_size = int(protocol["evaluation"]["batch_size"])
    base = _load_base(protocol, deps)
    base_eval = _evaluate_model(
        base, evaluation, collator=collator, batch_size=batch_size, torch_module=torch
    )
    target_base = _load_base(protocol, deps)
    target = deps["PeftModel"].from_pretrained(target_base, target_path)
    target_eval = _evaluate_model(
        target, evaluation, collator=collator, batch_size=batch_size, torch_module=torch
    )
    exact = _fresh_adapter(protocol, deps)
    started = time.perf_counter()
    _train_adapter(
        exact,
        cast(Sequence[Mapping[str, str]], scenario["train_retain"]),
        protocol=protocol,
        collator=collator,
        seed=seed,
        epochs=int(protocol["training"]["exact_epochs"]),
        deps=deps,
    )
    exact_runtime = time.perf_counter() - started
    exact_eval = _evaluate_model(
        exact, evaluation, collator=collator, batch_size=batch_size, torch_module=torch
    )
    exact_state = {
        name: parameter.detach().cpu().clone()
        for name, parameter in exact.named_parameters()
        if parameter.requires_grad
    }
    exact_digest = adapter_sha256(exact_state)
    _release(exact, torch)
    return {
        "base": base,
        "base_eval": base_eval,
        "exact_digest": exact_digest,
        "exact_eval": exact_eval,
        "exact_runtime": exact_runtime,
        "target": target,
        "target_digest": _adapter_digest(target_path),
        "target_eval": target_eval,
    }


def _path_id(temperature: float, keep_weight: float, checkpoint: int) -> str:
    return f"rbep-t{temperature:.1f}-k{keep_weight:.1f}-s{checkpoint:03d}".replace(".", "p")


def _train_and_evaluate_paths(
    seed: int,
    fold_id: str,
    scenario: Mapping[str, Any],
    prepared: Mapping[str, object],
    target_path: Path,
    inputs: Mapping[str, object],
    *,
    protocol: Mapping[str, Any],
    collator: QACollator,
    deps: Mapping[str, Any],
    selected_config: Mapping[str, object] | None = None,
    artifact_root: Path | None = None,
) -> list[dict[str, object]]:
    from experiments.qwen_tofu_v3_rbep import (
        adapter_sha256,
        bounded_rbep_loss,
        interpolate_adapter,
        train_rbep_path,
    )

    torch = deps["torch"]
    method = protocol["method"]
    configs = (
        [selected_config]
        if selected_config is not None
        else [
            {"keep_weight": keep, "temperature": temperature}
            for temperature in method["temperatures"]
            for keep in method["keep_weights"]
        ]
    )
    trials: list[dict[str, object]] = []
    for config in configs:
        if config is None:
            raise ValueError("selected RBEP configuration is missing")
        candidate_base = _load_base(protocol, deps)
        candidate = deps["PeftModel"].from_pretrained(
            candidate_base, target_path, is_trainable=True
        )
        parameters = {
            name: parameter
            for name, parameter in candidate.named_parameters()
            if parameter.requires_grad
        }
        target_state = {name: parameter.detach().clone() for name, parameter in parameters.items()}
        forget_stream = iter(
            _cycle_loader(
                cast(Sequence[Mapping[str, str]], scenario["train_forget"]),
                collator,
                int(protocol["training"]["micro_batch_size"]),
                seed + 202,
                torch,
            )
        )
        keep_rows = [
            *cast(Sequence[Mapping[str, str]], scenario["train_retain"]),
            *cast(Sequence[Mapping[str, str]], inputs["real_anchor"]),
        ]
        keep_stream = iter(
            _cycle_loader(
                keep_rows,
                collator,
                int(protocol["training"]["micro_batch_size"]),
                seed + 303,
                torch,
            )
        )
        base = prepared["base"]
        target = prepared["target"]
        base.eval()
        target.eval()
        candidate.train()

        def loss_step(
            _: int,
            *,
            forget_stream: Any = forget_stream,
            keep_stream: Any = keep_stream,
            candidate: Any = candidate,
            base: Any = base,
            target: Any = target,
            config: Mapping[str, object] = config,
        ) -> Any:
            forget_batch = _move(next(forget_stream), candidate.device)
            keep_batch = _move(next(keep_stream), candidate.device)
            candidate_forget = (
                candidate(
                    input_ids=forget_batch["input_ids"],
                    attention_mask=forget_batch["attention_mask"],
                )
                .logits[:, :-1, :]
                .float()
            )
            candidate_keep = (
                candidate(
                    input_ids=keep_batch["input_ids"],
                    attention_mask=keep_batch["attention_mask"],
                )
                .logits[:, :-1, :]
                .float()
            )
            with torch.no_grad():
                base_forget = (
                    base(
                        input_ids=forget_batch["input_ids"],
                        attention_mask=forget_batch["attention_mask"],
                    )
                    .logits[:, :-1, :]
                    .float()
                )
                target_keep = (
                    target(
                        input_ids=keep_batch["input_ids"],
                        attention_mask=keep_batch["attention_mask"],
                    )
                    .logits[:, :-1, :]
                    .float()
                )
            forget_labels = forget_batch["labels"][:, 1:]
            keep_labels = keep_batch["labels"][:, 1:]
            return bounded_rbep_loss(
                candidate_forget=candidate_forget,
                base_forget=base_forget,
                candidate_keep=candidate_keep,
                target_keep=target_keep,
                keep_labels=keep_labels,
                forget_answer_mask=forget_labels != -100,
                keep_answer_mask=keep_labels != -100,
                temperature=float(config["temperature"]),
                keep_weight=float(config["keep_weight"]),
                cross_entropy_weight=float(method["cross_entropy_weight"]),
            )

        selected_step = int(config.get("checkpoint", method["steps"]))
        checkpoint_steps = (
            (selected_step,)
            if selected_config is not None
            else tuple(int(value) for value in method["checkpoint_steps"])
        )
        optimizer = torch.optim.AdamW(parameters.values(), lr=float(method["learning_rate"]))
        path = train_rbep_path(
            candidate_parameters=parameters,
            target_state=target_state,
            optimizer=optimizer,
            loss_step=loss_step,
            steps=selected_step,
            checkpoint_steps=checkpoint_steps,
            gradient_clip_norm=float(method["gradient_clip_norm"]),
            delta_norm_ratio_max=float(method["delta_norm_ratio_max"]),
        )
        alphas = (
            [float(config["alpha"])]
            if selected_config is not None
            else [float(value) for value in method["alphas"]]
        )
        for checkpoint in path.checkpoints:
            checkpoint_state = {
                key: value.to(parameters[key].device, dtype=parameters[key].dtype)
                for key, value in checkpoint.state.items()
            }
            for alpha in alphas:
                state = interpolate_adapter(target_state, checkpoint_state, alpha=alpha)
                with torch.no_grad():
                    for key, value in state.items():
                        parameters[key].copy_(value)
                candidate_eval = _evaluate_model(
                    candidate,
                    cast(Mapping[str, object], scenario["evaluation"]),
                    collator=collator,
                    batch_size=int(protocol["evaluation"]["batch_size"]),
                    torch_module=torch,
                )
                artifact_path: Path | None = None
                candidate_digest = adapter_sha256(state)
                if selected_config is not None:
                    if artifact_root is None:
                        raise ValueError("confirmation artifact root is required")
                    artifact_path = artifact_root / f"{fold_id}-seed-{seed}-candidate"
                    candidate.save_pretrained(artifact_path)
                    candidate_digest = _adapter_digest(artifact_path)
                    reloaded_base = _load_base(protocol, deps)
                    reloaded = deps["PeftModel"].from_pretrained(reloaded_base, artifact_path)
                    reloaded_eval = _evaluate_model(
                        reloaded,
                        cast(Mapping[str, object], scenario["evaluation"]),
                        collator=collator,
                        batch_size=int(protocol["evaluation"]["batch_size"]),
                        torch_module=torch,
                    )
                    _release(reloaded, torch)
                else:
                    with torch.no_grad():
                        for key, value in state.items():
                            parameters[key].copy_(value.detach().clone())
                    reloaded_eval = _evaluate_model(
                        candidate,
                        cast(Mapping[str, object], scenario["evaluation"]),
                        collator=collator,
                        batch_size=int(protocol["evaluation"]["batch_size"]),
                        torch_module=torch,
                    )
                recurrence = _maximum_difference(candidate_eval, reloaded_eval)
                evaluations = {
                    "base": prepared["base_eval"],
                    "candidate": candidate_eval,
                    "candidate_reloaded": reloaded_eval,
                    "exact": prepared["exact_eval"],
                    "target": prepared["target_eval"],
                }
                runtime = {
                    "candidate_seconds": checkpoint.runtime_seconds,
                    "exact_seconds": prepared["exact_runtime"],
                }
                trials.append(
                    {
                        "adapter_sha256": {
                            "candidate": candidate_digest,
                            "exact": prepared["exact_digest"],
                            "target": prepared["target_digest"],
                        },
                        "alpha": alpha,
                        "artifact_path": (
                            str(artifact_path.relative_to(artifact_root.parent))
                            if artifact_path is not None and artifact_root is not None
                            else None
                        ),
                        "block": fold_id,
                        "checkpoint": checkpoint.step,
                        "evaluations": evaluations,
                        "keep_weight": float(config["keep_weight"]),
                        "metrics": score_v2_trial(
                            cast(Mapping[str, Mapping[str, object]], evaluations),
                            recurrence_after_reload=recurrence,
                            candidate_runtime_seconds=checkpoint.runtime_seconds,
                            exact_runtime_seconds=float(prepared["exact_runtime"]),
                        ),
                        "path_id": _path_id(
                            float(config["temperature"]),
                            float(config["keep_weight"]),
                            checkpoint.step,
                        ),
                        "recurrence_after_reload": recurrence,
                        "runtime": runtime,
                        "seed": seed,
                        "temperature": float(config["temperature"]),
                    }
                )
        _release(candidate, torch)
    return trials


def _point_record(point: PathPoint, trials: Sequence[Mapping[str, object]]) -> dict[str, object]:
    return {
        "alpha": point.alpha,
        "path_id": point.path_id,
        "summary": {
            "feasible": point.feasible,
            "minimum_margin": point.minimum_margin,
            "minimum_speedup": point.minimum_speedup,
            "worst_exact_gap": point.worst_exact_gap,
        },
        "trials": list(trials),
    }


def _selection_config(
    selected: PathPoint, trials: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    matching = [
        trial
        for trial in trials
        if trial.get("path_id") == selected.path_id
        and math.isclose(float(trial.get("alpha")), selected.alpha, abs_tol=1e-12)
    ]
    if not matching:
        raise ValueError("selected development trial metadata is missing")
    first = matching[0]
    return {
        "alpha": selected.alpha,
        "checkpoint": int(first["checkpoint"]),
        "keep_weight": float(first["keep_weight"]),
        "temperature": float(first["temperature"]),
    }


def _run_descriptive_baselines(
    seed: int,
    block: str,
    scenario: Mapping[str, Any],
    prepared: Mapping[str, object],
    target_path: Path,
    inputs: Mapping[str, object],
    *,
    collator: QACollator,
    tokenizer: Any,
    deps: Mapping[str, Any],
    checkpoint_root: Path,
) -> list[dict[str, object]]:
    v2_protocol = cast(
        dict[str, Any],
        json.loads((ROOT / "benchmark/qwen-tofu-kaggle-v2.json").read_text()),
    )
    legacy_prepared = {
        "base": prepared["base_eval"],
        "exact": prepared["exact_eval"],
        "exact_digest": prepared["exact_digest"],
        "exact_runtime": prepared["exact_runtime"],
        "target": prepared["target_eval"],
        "target_digest": prepared["target_digest"],
        "target_path": target_path,
    }
    configs = {str(config["id"]): config for config in v2_protocol["candidate"]["development_grid"]}
    rows = {"real_anchor": inputs["real_anchor"]}
    baseline_root = checkpoint_root / "baselines" / block
    baseline_root.mkdir(parents=True, exist_ok=True)
    result: list[dict[str, object]] = []
    for candidate_id, config in (
        (str(v2_protocol["baseline"]["id"]), None),
        ("ucsgp-f035-a025", configs["ucsgp-f035-a025"]),
    ):
        trial = _candidate_trial(
            seed,
            scenario,
            legacy_prepared,
            rows,
            protocol=v2_protocol,
            candidate_id=f"{block}-{candidate_id}",
            config=config,
            checkpoint_root=baseline_root,
            collator=collator,
            tokenizer=tokenizer,
            deps=deps,
        )
        trial["block"] = block
        trial["recipe_id"] = candidate_id
        result.append(trial)
    return result


def _run_secondary_relearning(
    trial: Mapping[str, Any],
    scenario: Mapping[str, Any],
    *,
    protocol: Mapping[str, Any],
    collator: QACollator,
    deps: Mapping[str, Any],
    output: Path,
) -> dict[str, object]:
    torch = deps["torch"]
    relative = trial.get("artifact_path")
    if not isinstance(relative, str):
        raise ValueError("secondary relearning requires a candidate artifact")
    artifact = output / relative
    base = _load_base(protocol, deps)
    model = deps["PeftModel"].from_pretrained(base, artifact, is_trainable=True)
    secondary = protocol["secondary"]
    stream = iter(
        _cycle_loader(
            cast(Sequence[Mapping[str, str]], scenario["train_retain"]),
            collator,
            int(protocol["training"]["micro_batch_size"]),
            int(trial["seed"]) + 707,
            torch,
        )
    )
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = torch.optim.AdamW(parameters, lr=float(secondary["learning_rate"]))
    model.train()
    for _ in range(int(secondary["retain_only_steps"])):
        batch = _move(next(stream), model.device)
        loss = model(**batch).loss
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(parameters, 1.0)
        optimizer.step()
    after = _evaluate_model(
        model,
        cast(Mapping[str, object], scenario["evaluation"]),
        collator=collator,
        batch_size=int(protocol["evaluation"]["batch_size"]),
        torch_module=torch,
    )
    _release(model, torch)
    before_metrics = cast(Mapping[str, Any], trial["metrics"])
    target_nll = float(before_metrics["target_forget_answer_nll"])
    exact_nll = float(before_metrics["exact_forget_answer_nll"])
    after_nll = sum(float(value) for value in after["forget_answer"]) / len(after["forget_answer"])
    denominator = exact_nll - target_nll
    if denominator <= 0.0:
        raise ValueError("secondary exact forgetting denominator is invalid")
    before_recovery = float(before_metrics["candidate_exact_normalized_recovery"])
    after_recovery = (after_nll - target_nll) / denominator
    recurrence_increase = before_recovery - after_recovery
    return {
        "after_evaluations": after,
        "after_normalized_recovery": after_recovery,
        "before_normalized_recovery": before_recovery,
        "block": trial["block"],
        "forget_recovery_increase": recurrence_increase,
        "passes_secondary_threshold": recurrence_increase
        <= float(secondary["forget_recovery_increase_max"]),
        "seed": trial["seed"],
    }


def run_scientific(protocol_path: Path, output: Path, *, code_revision: str) -> dict[str, object]:
    protocol = cast(dict[str, Any], json.loads(protocol_path.read_text()))
    deps = _load_dependencies()
    torch = deps["torch"]
    if not torch.cuda.is_available():
        raise RuntimeError("a CUDA GPU is required for the frozen v3 experiment")
    journal = EvidenceJournal(output, protocol_path=protocol_path, code_revision=code_revision)
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
    inputs = _load_common_inputs(protocol, deps)
    development_view = _development_view(inputs, protocol_path)
    development_trials: list[dict[str, object]] = []
    for seed_value in protocol["development_seeds"]:
        seed = int(seed_value)
        target_path = _train_target_once(
            seed,
            inputs,
            protocol=protocol,
            checkpoint_root=checkpoint_root,
            collator=collator,
            deps=deps,
        )
        for fold_index, fold in enumerate(development_view.folds):
            scenario = _scenario(fold, inputs, protocol=protocol)
            prepared = _prepare_fold(
                seed,
                scenario,
                target_path,
                protocol=protocol,
                collator=collator,
                deps=deps,
            )
            development_trials.extend(
                _train_and_evaluate_paths(
                    seed,
                    f"development-{fold_index}",
                    scenario,
                    prepared,
                    target_path,
                    inputs,
                    protocol=protocol,
                    collator=collator,
                    deps=deps,
                )
            )
            _release(prepared["base"], torch)
            _release(prepared["target"], torch)
    grouped: dict[tuple[str, float], list[dict[str, object]]] = {}
    for trial in development_trials:
        grouped.setdefault((str(trial["path_id"]), float(trial["alpha"])), []).append(trial)
    points_by_path: dict[str, list[PathPoint]] = {}
    point_records: list[dict[str, object]] = []
    criteria = cast(Mapping[str, object], protocol["success_criteria"])
    for (path_id, alpha), trials in sorted(grouped.items()):
        point = summarize_path_point(path_id, alpha, trials, criteria)
        points_by_path.setdefault(path_id, []).append(point)
        point_records.append(_point_record(point, trials))
    minimum_width = int(protocol["method"]["minimum_contiguous_feasible_alphas"])
    try:
        selected = select_robust_point(points_by_path, minimum_width=minimum_width)
    except NoRobustCandidateError:
        journal.complete_development(
            {
                "decision": "NO_CANDIDATE",
                "points": point_records,
                "selection_uses_confirmation": False,
            }
        )
        return journal.seal_no_candidate()
    all_intervals = robust_intervals(
        [point for rows in points_by_path.values() for point in rows],
        minimum_width=minimum_width,
    )
    winner_interval = next(
        interval
        for interval in all_intervals
        if any(
            point.path_id == selected.path_id and point.alpha == selected.alpha
            for point in interval
        )
    )
    selected_config = _selection_config(selected, development_trials)
    development_payload = {
        "decision": "CANDIDATE_AVAILABLE",
        "points": point_records,
        "selection_uses_confirmation": False,
    }
    journal.complete_development(development_payload)
    journal.commit_selection(
        {
            **selected_config,
            "development_sha256": _sha256(output / "development.json"),
            "interval_alphas": [point.alpha for point in winner_interval],
            "minimum_margin": min(point.minimum_margin for point in winner_interval),
            "minimum_speedup": min(point.minimum_speedup for point in winner_interval),
            "selected_alpha": selected.alpha,
            "selected_path_id": selected.path_id,
            "worst_exact_gap": max(point.worst_exact_gap for point in winner_interval),
        }
    )
    confirmation_view = _confirmation_view(inputs, protocol_path, output / "selection.json")
    confirmation_trials: list[dict[str, object]] = []
    baseline_trials: list[dict[str, object]] = []
    scenarios: dict[tuple[str, int], Mapping[str, Any]] = {}
    for seed_value in protocol["confirmation_seeds"]:
        seed = int(seed_value)
        target_path = _train_target_once(
            seed,
            inputs,
            protocol=protocol,
            checkpoint_root=checkpoint_root,
            collator=collator,
            deps=deps,
        )
        for block, fold in (
            ("primary", confirmation_view.primary),
            ("replication", confirmation_view.replication),
        ):
            scenario = _scenario(fold, inputs, protocol=protocol)
            scenarios[(block, seed)] = scenario
            prepared = _prepare_fold(
                seed,
                scenario,
                target_path,
                protocol=protocol,
                collator=collator,
                deps=deps,
            )
            trial_rows = _train_and_evaluate_paths(
                seed,
                block,
                scenario,
                prepared,
                target_path,
                inputs,
                protocol=protocol,
                collator=collator,
                deps=deps,
                selected_config=selected_config,
                artifact_root=checkpoint_root,
            )
            if len(trial_rows) != 1:
                raise ValueError("confirmation must produce exactly one selected trial")
            confirmation_trials.extend(trial_rows)
            baseline_trials.extend(
                _run_descriptive_baselines(
                    seed,
                    block,
                    scenario,
                    prepared,
                    target_path,
                    inputs,
                    collator=collator,
                    tokenizer=tokenizer,
                    deps=deps,
                    checkpoint_root=checkpoint_root,
                )
            )
            _release(prepared["base"], torch)
            _release(prepared["target"], torch)
    journal.complete_confirmation(confirmation_trials, baseline_trials)
    secondary_trials = [
        _run_secondary_relearning(
            trial,
            scenarios[(str(trial["block"]), int(trial["seed"]))],
            protocol=protocol,
            collator=collator,
            deps=deps,
            output=output,
        )
        for trial in confirmation_trials
    ]
    journal.complete_secondary(secondary_trials)
    primary = summarize_v2_trials(
        [row for row in confirmation_trials if row["block"] == "primary"], criteria
    )
    replication = summarize_v2_trials(
        [row for row in confirmation_trials if row["block"] == "replication"], criteria
    )
    combined = summarize_v2_trials(confirmation_trials, criteria)
    return journal.seal_scientific(
        {
            "combined": combined,
            "decision": combined["decision"],
            "environment": {
                "cuda": torch.version.cuda,
                "gpu": torch.cuda.get_device_name(0),
            },
            "primary": primary,
            "replication": replication,
            "scientific": True,
            "secondary_all_pass": all(
                bool(row["passes_secondary_threshold"]) for row in secondary_trials
            ),
        }
    )


def run_development_shard(
    protocol_path: Path,
    output: Path,
    *,
    code_revision: str,
    fold_index: int,
) -> dict[str, object]:
    """Run one execution-only shard without changing the frozen protocol."""
    protocol = cast(dict[str, Any], json.loads(protocol_path.read_text()))
    deps = _load_dependencies()
    torch = deps["torch"]
    if not torch.cuda.is_available():
        raise RuntimeError("a CUDA GPU is required for the frozen v3 experiment")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite shard directory: {output}")
    output.mkdir(parents=True)
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
    inputs = _load_common_inputs(protocol, deps)
    development_view = _development_view(inputs, protocol_path)
    if fold_index < 0 or fold_index >= len(development_view.folds):
        raise ValueError(f"development fold must be in [0, {len(development_view.folds)})")
    fold = development_view.folds[fold_index]
    trials: list[dict[str, object]] = []
    for seed_value in protocol["development_seeds"]:
        seed = int(seed_value)
        target_path = _train_target_once(
            seed,
            inputs,
            protocol=protocol,
            checkpoint_root=checkpoint_root,
            collator=collator,
            deps=deps,
        )
        scenario = _scenario(fold, inputs, protocol=protocol)
        prepared = _prepare_fold(
            seed,
            scenario,
            target_path,
            protocol=protocol,
            collator=collator,
            deps=deps,
        )
        trials.extend(
            _train_and_evaluate_paths(
                seed,
                f"development-{fold_index}",
                scenario,
                prepared,
                target_path,
                inputs,
                protocol=protocol,
                collator=collator,
                deps=deps,
            )
        )
        _release(prepared["base"], torch)
        _release(prepared["target"], torch)
    trial_path = output / "development-trials.jsonl"
    trial_path.write_bytes(b"".join(_canonical(row) + b"\n" for row in trials))
    manifest: dict[str, object] = {
        "code_revision": code_revision,
        "development_seeds": [int(value) for value in protocol["development_seeds"]],
        "environment": {
            "cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
        },
        "fold_index": fold_index,
        "parent_protocol_sha256": _sha256(protocol_path),
        "phase": "development",
        "schema_version": "erasemap-qwen-tofu-v3-shard-v1",
        "scientific_inputs_frozen": True,
        "trial_count": len(trials),
        "trials_sha256": _sha256(trial_path),
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_bytes(_canonical(manifest) + b"\n")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run frozen Qwen-TOFU Kaggle v3")
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "benchmark/qwen-tofu-kaggle-v3.json",
    )
    parser.add_argument("--output", type=Path, default=Path("/kaggle/working/qwen-tofu-v3"))
    parser.add_argument("--code-revision", default=os.environ.get("ERASEMAP_CODE_REVISION"))
    parser.add_argument("--development-fold", type=int)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    revision = args.code_revision or _git_revision()
    if args.smoke and args.development_fold is not None:
        parser.error("--smoke and --development-fold are mutually exclusive")
    if args.development_fold is not None:
        result = run_development_shard(
            args.protocol,
            args.output,
            code_revision=revision,
            fold_index=args.development_fold,
        )
    elif args.smoke:
        result = run_smoke(args.protocol, args.output, code_revision=revision)
    else:
        result = run_scientific(args.protocol, args.output, code_revision=revision)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
