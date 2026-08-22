# Blinded external challenge

This package is for an evaluator who is independent of the EraSeMap author.

1. The evaluator writes cases with public topology under `case` and private `truth_verdict` plus
   `expected_path` beside it.
2. The evaluator creates at least 120 cases across at least four independently authored mapping
   families, including at least 100 non-complete cases, then runs
   `seal.py seal`. The public package contains encrypted answers and SHA-256 commitments, but no
   plaintext labels.
3. The evaluator keeps the generated key file outside the EraSeMap repository and gives only the public
   package to the project author.
4. EraSeMap produces answer-blind records once with `runner.py`, then runs `seal.py freeze`;
   missing, duplicate, or extra case IDs are rejected and the predictions receive their own
   commitment.
5. The evaluator runs `seal.py score` with `protocol-v1.json`. It verifies both commitments and
   applies preregistered gates: at least 120 cases, four families, at least 100 non-complete cases,
   at least 90% verdict accuracy, at least 80% exact shortest-path accuracy, and a 95% Wilson upper
   bound of at most 5% for false-complete rate.

With zero false-complete errors, 100 non-complete cases give a 95% Wilson upper bound of about
3.7%. This is why the protocol requires substantially more than 30-50 cases.

Example command sequence:

```bash
python external_challenge/seal.py seal --input authored.json --output public.json \
  --key-file-out evaluator-key.txt
python external_challenge/runner.py --package public.json --output predictions.json
python external_challenge/seal.py freeze --package public.json --input predictions.json \
  --output frozen.json
python external_challenge/seal.py score --package public.json --input frozen.json \
  --key-file evaluator-key.txt --protocol external_challenge/protocol-v1.json \
  --output score.json
python external_challenge/attest.py generate --private-key evaluator.pem \
  --public-key evaluator.pub
python external_challenge/attest.py sign --score score.json --attestation attestation.json \
  --private-key evaluator.pem --evaluator REVIEWER --affiliation ORGANIZATION
python external_challenge/attest.py verify --score score.json --attestation attestation.json
```

For registry submission, copy `manifest-template.json`, replace every placeholder, calculate the
raw SHA-256 of `public-package.json`, `frozen-predictions.json`, `reveal-key.txt`, and `score.json`,
then bind the entire manifest and score with:

```bash
python external_challenge/attest.py sign-submission \
  --score score.json --manifest manifest.json \
  --private-key evaluator.pem --attestation attestation.json
python external_challenge/submission.py \
  --submission /path/to/submission \
  --expected-erasemap-commit FULL_TESTED_COMMIT
```

The verifier recomputes answer-blind predictions, the full score, file hashes, repository and
commit bindings, family provenance, timestamp order, and signature. A technical pass deliberately
returns `PENDING_IDENTITY_AND_CONFLICT_REVIEW`; cryptography cannot prove the human identity behind
a key.

The public Ed25519 attestation makes later score or statement changes detectable. Identity and
institutional affiliation still require an external letter, public profile, or other independently
verifiable channel; a cryptographic signature alone does not establish who owns the key.

The independent evaluator must control case authorship, labels, key, reveal timing, and final
signature. A package created by the EraSeMap author is useful for testing but is not independent
evidence. Do not include personal data, credentials, private infrastructure names, or biometric
samples in a public package.

See [`docs/INDEPENDENCE_EVIDENCE_RUBRIC.md`](../docs/INDEPENDENCE_EVIDENCE_RUBRIC.md). The current
independence score remains 7.8 until a real external submission is accepted; readiness machinery is
not counted as completed external evidence.
