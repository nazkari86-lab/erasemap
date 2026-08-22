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

## Task-agnostic v2.2

Version 2.2 keeps the unchanged face-verification task, corrects the v2 primary-endpoint gate,
renames the neural update honestly to influence-selective unlearning, and evaluates six attacks:
four logit statistics, a 16-shadow-model task-agnostic LiRA variant, and an embedding nearest-
neighbour attack. The lineage graph selects whether model remediation is exact retraining, a
protocol-approved approximate update, or blocked pending evidence.

The method passed 100 deletion trials on each of Olivetti development, locked LFW confirmation,
and a content-unseen MUFAC subset frozen before its 572 images were accessed. The stronger v2.2
privacy audit was frozen later and passed on all three datasets without changing the unlearning
method. On MUFAC its LiRA AUC was 0.69519 versus 0.68865 for exact retraining, with 3.51× update
speedup. This is external benchmark evidence, not production validation or a privacy guarantee.

See [docs/TASK_AGNOSTIC_V22_REPORT.md](docs/TASK_AGNOSTIC_V22_REPORT.md) for the shadow-model threat
model, confidence intervals, critique response, and limitations. Earlier v2/v2.1 records remain
available. A real service can map its components through
[docs/INTEGRATION_CONTRACT.md](docs/INTEGRATION_CONTRACT.md).

## Registered v3 deletion-matched evaluation

Version 3 replaces the weak global-MSE/non-inferiority claim with separate forgotten and retained
endpoints. Its primary candidate is a fresh 60-epoch restart on retained identities only, compared
with a 200-epoch exact retrain using the same initialization. Privacy is gated per deletion request
and per attack using paired bootstrap confidence intervals, including an identity-level shadow
attack whose in-model shadows contain the whole identity and whose out-model shadows omit it.

The frozen development protocol passed 100 deletion requests: forgotten embedding MSE was 0.134×
the stale baseline, retained MSE was 0.152×, and the largest paired attack 95% upper bound was
0.076. Locked LFW also passed. MUFAC passed all deletion/privacy gates but failed the retained-AUC
gate (`−0.01324` versus the preregistered `−0.01` limit); that negative result is retained. The
adaptive 80-epoch v3.1 ablation did not fix the cross-dataset gate and exposed a privacy trade-off.
See [docs/TASK_AGNOSTIC_V3_REPORT.md](docs/TASK_AGNOSTIC_V3_REPORT.md) for all results and boundaries.

The separate pixel-backbone benchmark trains every convolutional and classifier parameter directly
from Olivetti images. It addresses the frozen-backbone limitation while explicitly remaining a
small-dataset research result, not a production FaceID claim. See
[docs/NOVELTY_AND_PRIOR_ART.md](docs/NOVELTY_AND_PRIOR_ART.md) for the narrow novelty boundary and
[docs/EXTERNAL_EVALUATOR_PROTOCOL.md](docs/EXTERNAL_EVALUATOR_PROTOCOL.md) for a precommitted hidden
suite interface.

Production evidence can be supplied as Ed25519-signed envelopes with trusted key identifiers,
freshness checks, and replay protection. A caller-supplied `valid_signature: true` boolean is a
legacy fixture mechanism, not a production trust boundary.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy src/erasemap
```

One-command release checks are available as `scripts/reproduce_release.sh core`; the `face-open`
profile additionally rebuilds the open face assets and registered face experiments. EraseMap code
is MIT licensed; third-party datasets and weights retain their own terms as documented in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
