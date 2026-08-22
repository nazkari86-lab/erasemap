# External hidden challenge handoff

## Frozen target

The immutable evaluator target is EraSeMap commit
`39a3a7797d4d25b67675cd6ed0c90eb0526b32f5`. The file
`external_challenge/evaluator-freeze-v2.json` binds the answer-blind runner, seal/freeze/score
logic, submission verifier, attestation code, and statistical protocol to their Git object bytes.

Verify the handoff before authoring cases:

```bash
git clone https://github.com/nazkari86-lab/erasemap.git
cd erasemap
git checkout 39a3a7797d4d25b67675cd6ed0c90eb0526b32f5
python scripts/verify_external_freeze.py
python -m pip install -e '.[dev]'
python -m pytest tests/test_external_challenge.py tests/test_external_submission.py
```

The evaluator should then follow `external_challenge/README.md` on an externally controlled
machine and repository. The EraSeMap author must receive only the public encrypted package until
predictions are frozen.

## Non-negotiable independence controls

- The evaluator authors at least 120 cases and at least four genuinely different mapping families.
- At least 100 cases are non-complete; families must include channel, edge, replay, and
  hidden-artifact interactions rather than renaming one template.
- The evaluator controls plaintext labels, encryption key, timestamps, external repository,
  identity evidence, and signing key.
- EraSeMap produces predictions exactly once from the public encrypted package at the frozen commit.
- Labels are revealed only after `frozen-predictions.json` exists.
- Every failure remains in the signed score. No code, threshold, or case is changed after reveal.
- Identity and conflict-of-interest are reviewed outside cryptography using the public profile or
  institutional letter named in the manifest.

## Current status

`READY_NOT_EXECUTED`. This handoff proves that the evaluation target is immutable and executable;
it does **not** prove that an independent evaluator or hidden result exists.
