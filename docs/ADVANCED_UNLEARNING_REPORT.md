# Advanced Face-Unlearning Report

## One-sentence research question

After a person requests biometric deletion, can a system distinguish a model that merely stopped
displaying that person's label from one rebuilt without that person's training records?

EraseMap treats deletion as a verifiable chain across source storage, indexes, caches, backups,
and learned models. The experiment deliberately reports separate answers for visible model output,
retained-user utility, membership inference, and parameter distance from exact retraining.

## Frozen design

The Olivetti development protocol was frozen in
[`advanced-face-unlearning-v1.json`](../benchmark/advanced-face-unlearning-v1.json). Before LFW was
accessed, the external protocol was frozen in
[`lfw-holdout-v1.json`](../benchmark/lfw-holdout-v1.json) and the implementation was committed as
`7af99d2ebbf9ffacd03ffb1ffd5798333352861b`. The ignored result directory contains a holdout lock
with the code revision and SHA-256 commitments for the protocol, LFW archive, and recognition
model.

The recognition backbone was InsightFace `buffalo_sc`, whose recognition network is
MobileFaceNet trained on WebFace600K. Its 512-dimensional embeddings fed a locally trained
512→128→identity neural adapter. The backbone was frozen and is outside the deletion claim.

Four strategies used identical splits and seeds:

1. **Stale:** delete the source row but keep the original deployed model.
2. **Head only:** freeze the original encoder and retrain a new output layer without the deleted
   class.
3. **Gradient ascent:** approximately reverse the forgotten samples, then repair on retained data.
4. **Exact retraining:** initialize a fresh local adapter and train only on retained identities.

Exact retraining is the reference, not a proof that every possible influence has been erased. A
method passes the registered experiment only if the forgotten output is low, retained accuracy
stays within the frozen tolerance, and its membership-attack AUC stays below the frozen threshold.

## Locked results

| Dataset / method | Forgotten probability | Retained accuracy | Membership AUC | Encoder L2 to exact |
|---|---:|---:|---:|---:|
| Olivetti dev — stale | 97.13% | 100.00% | 0.952 | 32.890 |
| Olivetti dev — head only | 0.00% | 100.00% | 0.500 | 32.890 |
| Olivetti dev — gradient ascent | 0.00% | 82.05% | 0.500 | 46.225 |
| Olivetti dev — exact | 0.00% | 100.00% | 0.500 | 0.000 |
| LFW holdout — stale | 91.34% | 97.23% | 0.571 | 24.866 |
| LFW holdout — head only | 0.00% | 96.90% | 0.500 | 24.866 |
| LFW holdout — gradient ascent | 0.00% | 76.30% | 0.500 | 40.034 |
| LFW holdout — exact | 0.00% | 97.12% | 0.500 | 0.000 |

The face embeddings themselves separated same-person from different-person pairs with AUC 0.979
on Olivetti and 0.943 on the locked LFW holdout.

### What the numbers establish

- Deleting only the source record fails: the stale model predicted the forgotten label for 100%
  of its held-out faces on both datasets.
- Head-only retraining creates a clean-looking interface but leaves the local encoder exactly as
  far from exact retraining as the stale model: 32.890 on Olivetti and 24.866 on LFW. EraseMap can
  therefore expose a deletion claim that output-only testing would accept.
- The tested gradient-ascent recipe overscrubbed. Retained accuracy fell by 17.95 percentage points
  on Olivetti and 20.93 points on LFW, so it is not a safe replacement for retraining here.
- Exact retraining removed the output class while matching the stale model's retained accuracy to
  within 0.12 percentage points on LFW and exactly on the Olivetti development run.
- Membership inference was strong for the stale Olivetti model but only 0.571 on stale LFW. The
  holdout therefore supports class persistence and utility conclusions, not a broad claim of
  privacy leakage detectable by this particular attack.

## Real registered-storage audit

The companion storage lab materializes five distinct artifacts: a SQLite source record, NumPy
vector index, JSON cache, AES-GCM encrypted backup with a separate key, and model-training
manifest. Deleting only SQLite produced `INCOMPLETE`; EraseMap still found the subject in the
index, cache, backup, and model lineage.

The remediation run cleared the index, cache, and training manifest and destroyed the unique
backup key. The ciphertext intentionally remained, demonstrating crypto-erasure rather than
pretending the backup bytes vanished. The final registered-artifact verdict was `COMPLETE`.

## Reproduction

```bash
.venv/bin/pip install -e '.[dev,face]'
PYTHONPATH=src .venv/bin/python experiments/prepare_face_assets.py
PYTHONPATH=src .venv/bin/python experiments/advanced_face_unlearning.py \
  --dataset olivetti --protocol benchmark/advanced-face-unlearning-v1.json \
  --output outputs/advanced-face-unlearning-v1
PYTHONPATH=src .venv/bin/python experiments/advanced_face_unlearning.py \
  --dataset lfw --protocol benchmark/lfw-holdout-v1.json \
  --output outputs/lfw-holdout-v1
PYTHONPATH=src .venv/bin/python experiments/run_registered_storage_lab.py
PYTHONPATH=src .venv/bin/python experiments/render_unlearning_results.py
```

Checksums and source URLs are recorded in
[`real-data-manifest-v1.json`](../benchmark/real-data-manifest-v1.json). Raw faces, downloaded
weights, trained checkpoints, and subject-bearing outputs are ignored by Git.

## Strict limits

This is a controlled benchmark, not a production certification. It does not inspect Apple Face ID,
eGov, a government database, hidden replicas, or artifacts that a system failed to register. The
single-forgotten-identity membership samples are small, so those attack metrics are descriptive,
not population estimates. LFW is an external locked dataset relative to development, but it is not
guaranteed independent of the broader face-recognition training ecosystem. The InsightFace model
pack is licensed for non-commercial research, and the frozen backbone was not unlearned.

The next decisive evidence is an authorized pilot where a real identity service emits signed
events from its database, template store, cache, backup key manager, and model registry. Until
then, portability to Face ID-like, eGov, or government systems remains a testable architecture
claim—not validated deployment.
