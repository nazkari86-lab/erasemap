# EraseMap

EraseMap answers one concrete question: **after a biometric deletion request, which registered
copy or derivative can still be used?** It models the source record, Face ID template, search
index, cache, backup, model influence, and audit receipt as a typed lineage graph. The auditor
returns `COMPLETE`, `INCOMPLETE`, or `UNVERIFIED`, plus the shortest counterexample path and a
cost-aware remediation plan.

The project is intentionally system-neutral: the same graph contract can describe a school
access system, a bank KYC flow, or a government identity service. That portability is a research
hypothesis to test, not a claim of production validation.

EraseMap covers only artifacts registered by trusted instrumentation. It does not prove global
physical erasure, detect secret unregistered copies, provide legal advice, or claim validation on
eGov, Face ID, or another production identity system.

## Quick demonstration

```bash
erasemap audit examples/five_branch_system.json --subject subject-1
erasemap generate --seed 7 --nodes 100 --fault STALE_CACHE --output /tmp/case.json
erasemap benchmark dev --protocol benchmark/protocol-v1.json --output outputs/dev-v1
```

The fixed example contains an erased enrollment record with one still-active face template, so
the first command returns `INCOMPLETE` and the path `source -> template`. An incomplete audit is a
valid scientific result and therefore exits successfully.

See [docs/CORE_PROTOCOL.md](docs/CORE_PROTOCOL.md) for the frozen experiment, baselines, evidence
contracts, receipt boundary, and interpretation rules.

## Real-face unlearning benchmark

The repository contains reproducible biometric-deletion experiments on Olivetti Faces and a
locked LFW holdout. A face-specific MobileFaceNet embedding network feeds a locally trained neural
identifier. Four post-deletion strategies are compared: leaving the model stale, retraining only
its output head, approximate gradient-ascent unlearning, and exact retraining without the requested
identity. The benchmark separately measures visible deletion, retained-user utility, membership
leakage, and distance from the exact-retraining reference.

![Measured comparison of four deletion strategies](docs/assets/unlearning-comparison.png)

```bash
.venv/bin/pip install -e '.[dev,face]'
PYTHONPATH=src python experiments/prepare_face_assets.py
python -m erasemap.real_experiment
TORCH_HOME=data/real/torch PYTHONPATH=src \
  python experiments/run_resnet18_face_unlearning.py
PYTHONPATH=src python experiments/advanced_face_unlearning.py \
  --dataset olivetti --protocol benchmark/advanced-face-unlearning-v1.json \
  --output outputs/advanced-face-unlearning-v1
PYTHONPATH=src python experiments/advanced_face_unlearning.py \
  --dataset lfw --protocol benchmark/lfw-holdout-v1.json \
  --output outputs/lfw-holdout-v1
PYTHONPATH=src python experiments/run_registered_storage_lab.py
```

See [docs/ADVANCED_UNLEARNING_REPORT.md](docs/ADVANCED_UNLEARNING_REPORT.md) for the locked results,
and [docs/REAL_FACE_EXPERIMENT.md](docs/REAL_FACE_EXPERIMENT.md) for the earlier baseline and strict
claim boundaries.

## Task-agnostic v2.1

Version 2.1 keeps the unchanged face-verification task, corrects the v2 primary-endpoint gate,
renames the neural update honestly to influence-selective unlearning, and evaluates four
orientation-invariant privacy attacks. The lineage graph now selects whether model remediation is
exact retraining, a protocol-approved approximate update, or blocked pending evidence.

The method passed 100 deletion trials on each of Olivetti development, locked LFW confirmation,
and a content-unseen MUFAC subset frozen before its 572 images were accessed. On MUFAC it preserved
retained verification AUC at 0.92624 versus 0.92565 for exact retraining, stayed within the frozen
1% primary non-inferiority margin, and ran 3.49× faster. This is external benchmark evidence, not
production validation or a formal privacy guarantee.

See [docs/TASK_AGNOSTIC_V21_REPORT.md](docs/TASK_AGNOSTIC_V21_REPORT.md) for the frozen endpoints,
confidence intervals, critique response, and remaining limitations. The historical v2 result is
preserved in [docs/TASK_AGNOSTIC_V2_REPORT.md](docs/TASK_AGNOSTIC_V2_REPORT.md). A real service can
map its components through [docs/INTEGRATION_CONTRACT.md](docs/INTEGRATION_CONTRACT.md).

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy src/erasemap
```
