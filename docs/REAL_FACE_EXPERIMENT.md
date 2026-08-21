# Real Face Model-Deletion Experiment v1

## What was actually tested

On 2026-08-21, EraseMap downloaded the public Olivetti Faces dataset through the official
scikit-learn interface. It contains 400 grayscale face images of 40 people, ten images per person.
The raw Figshare download matched scikit-learn's expected SHA-256
`b612fb967f2dc77c9c62d3e1266e0c73d5fca46a4b8906c18e454d41af987794` before scikit-learn
converted it into its local cache.

Sources:

- https://scikit-learn.org/stable/datasets/real_world.html#the-olivetti-faces-dataset
- https://scikit-learn.org/stable/modules/generated/sklearn.datasets.fetch_olivetti_faces.html
- https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.resnet18.html

The primary split and success criteria were written to
[`benchmark/real-face-protocol-v1.json`](../benchmark/real-face-protocol-v1.json) before the first
successful training run. Seven images per identity were used for training and three for testing.
Subject 0 was the preselected deletion request. Exact unlearning means training a fresh model from
the same seed and hyperparameters after excluding all seven training images of that subject.

Two real classifiers were evaluated:

1. Standardized 4,096-pixel vectors, 80-component whitened PCA, and multinomial logistic
   regression.
2. Official ResNet-18 `IMAGENET1K_V1` weights as a frozen 512-dimensional feature extractor,
   followed by a locally trained PCA and logistic identification head. The weights file matched
   SHA-256 `f37072fd47e89c5e827621c5baffa7500819f7896bbacec160b1a16c560e07ec`.

The ResNet backbone was trained on ImageNet, not on the local Olivetti identities. Therefore, the
second experiment tests deletion from the locally trained PCA/classifier head only. It does not
claim to unlearn anything from the frozen backbone.

## Pre-registered subject-0 result

| Measurement | Pixel/PCA model | ResNet-18 feature model |
|---|---:|---:|
| Stale model retains deleted class | Yes | Yes |
| Stale mean probability of deleted class on forgotten test faces | 55.36% | 56.36% |
| Exact model retains deleted class | No | No |
| Exact probability of deleted class | 0.00% | 0.00% |
| Stale retained-person accuracy | 97.44% | 97.44% |
| Exact retained-person accuracy | 97.44% | 97.44% |
| Retained accuracy delta | 0.00 percentage points | 0.00 percentage points |
| EraseMap verdict for stale model | `INCOMPLETE` | `INCOMPLETE` |
| EraseMap verdict after exact retraining | `COMPLETE` | `COMPLETE` |

Both runs passed the frozen requirement that retained-person accuracy must not fall by more than
five percentage points. The stale-model counterexample was
`source -> template -> model`: deleting records while continuing to deploy the original model did
not erase the model artifact.

## Exploratory all-subject robustness sweep

After the primary result, the ResNet-18 experiment was repeated as an explicitly exploratory
sweep, forgetting each of the 40 identities in turn:

- 40/40 exact-retrained heads removed the requested class.
- 40/40 passed the already frozen accuracy criterion.
- Mean retained-person accuracy was 97.65%; the minimum was 96.58%.
- Mean retained-accuracy change was +0.15 percentage points; the worst was −0.85 points.
- In stale heads, forgotten-class probability ranged from 35.23% to 95.41%, with an 82.51%
  median.

This sweep is stronger than a single demonstration but is not a locked holdout because it uses the
same small dataset, architecture, and protocol family as development.

## Reproduction and artifacts

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev,real]'
PYTHONPATH=src .venv/bin/python -m erasemap.real_experiment

TORCH_HOME=data/real/torch PYTHONPATH=src python3 \
  experiments/run_resnet18_face_unlearning.py
TORCH_HOME=data/real/torch PYTHONPATH=src python3 \
  experiments/sweep_resnet18_subjects.py
```

Local outputs are stored under:

- `outputs/real-face-v1/`
- `outputs/real-face-resnet18-v1/`
- `outputs/real-face-resnet18-sweep-v1/`

Raw face images, model weights, trained models, and outputs are intentionally ignored by Git.
Result JSON files contain metrics and SHA-256 commitments, not face pixels.

## What this does not prove

This is a real-data, real-training experiment, but not production validation. It does not test
Apple Face ID, eGov, a government database, secret replicas, backup deletion, or a face-specific
production embedding network. The public benchmark cache still contains the source dataset; it is
an immutable research input outside the simulated application's registered storage. `COMPLETE`
means that the registered application model path satisfied this experiment's evidence contract,
not that every physical copy of the public dataset vanished.

The next phase added a face-specific recognition network, approximate-unlearning baselines,
membership inference, a real multi-artifact storage lab, and a pre-frozen LFW holdout. See
[`ADVANCED_UNLEARNING_REPORT.md`](ADVANCED_UNLEARNING_REPORT.md). The remaining external step is an
authorized integration with a real biometric service whose storage, index, backup, key-management,
and training pipelines can emit signed evidence.
