# Sequential deletion privacy v1 — frozen result

## Result

The first confirmatory run at preregistration commit
`5086151af0e59f4dd8ed34a15b09dde510cee039` **passed all six frozen gates**. The run contains five
independent seeded deletion orders, five consecutive identity deletions per order, and 25 paired
release transitions. The protocol, implementation, thresholds, and tests were committed and pushed
before this result directory existed.

This is a project-authored result on externally published Olivetti Faces inputs. It is evidence for
the registered bounded method, not independent validation, certified privacy, or a production
Face ID/eGov claim.

## Frozen endpoints

| Endpoint | Frozen requirement | Observed worst case | Decision |
|---|---:|---:|---|
| Deleted classifier classes absent | all transitions | 25/25 | PASS |
| Candidate epoch-budget speedup | at least 1.5× | 1.667× on every transition | PASS |
| Retained accuracy difference vs exact | at least −0.020 | −0.00952 | PASS |
| Retained embedding MSE vs exact | at most 0.001 | 0.00000823 | PASS |
| Forgotten verification AUC gap vs exact | at most 0.050 | 0.00395 | PASS |
| Largest paired privacy upper 95% CI | at most 0.050 | 0.00624 | PASS |

The candidate is a fresh 60-epoch deletion-matched restart, not an in-place update. Exact retraining
uses 100 epochs. The registered 1.667× value is therefore an epoch-budget ratio. Mean measured local
training time was 0.0471 s for the candidate and 0.0773 s for exact, but runtime was not a primary
gate and should not be generalized beyond this machine.

## Sequential retained-user privacy result

An observer sees two consecutive releases and uses the absolute change in one score to distinguish
retained training samples from retained test samples. The confirmatory statistic is the paired
candidate-minus-exact membership advantage over the 25 release transitions.

| Release-change attack | Candidate mean advantage | Exact mean advantage | Paired difference | Bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Confidence | 0.35922 | 0.44293 | −0.08370 | [−0.11263, −0.05977] |
| Energy | 0.06222 | 0.06366 | −0.00144 | [−0.00781, 0.00624] |
| Margin | 0.36551 | 0.44238 | −0.07687 | [−0.10252, −0.05515] |
| Negative entropy | 0.34663 | 0.43175 | −0.08512 | [−0.11802, −0.05614] |

The result says that none of the four registered attacks had evidence of more than 0.05 additional
membership advantage for the candidate relative to exact retraining. It does **not** say either
model is private: several absolute advantages are large. It also does not cover shadow-model,
adaptive-query, reconstruction, population-shift, or production attacks.

## Integrity and reproduction

The raw records, summary, and SHA-256 manifest are committed under
`benchmark/results/sequential-deletion-privacy-v1/`. A separate verifier reloads all 25 records,
checks the protocol and embedding hashes, confirms the preregistration commit exists, reconstructs
the registered units, recomputes all bootstrap intervals, endpoints, gates, and the final decision,
and rejects changed records.

```bash
python scripts/verify_sequential_deletion_privacy_v1.py
```

The output must report `decision: PASS`, `manifest: PASS`, and `transitions_checked: 25`.

## Interpretation

This closes the previously explicit gap “sequential deletions and retained-user release privacy
have not been tested” for one bounded external dataset and one fixed attack panel. Exact retraining
remains the mandatory fallback outside the registered domain or after any failed gate. The
independence score must remain unchanged: an independently authored hidden challenge has still not
been executed by an identifiable external evaluator.
