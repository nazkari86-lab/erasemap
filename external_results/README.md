# External evidence registry

This directory intentionally contains no accepted result yet. A submission counts as independent
only after it arrives through a pull request from an externally identifiable evaluator, passes the
cryptographic/statistical workflow, and receives a public identity/conflict-of-interest review.

Each evaluation uses one subdirectory containing:

- `manifest.json`
- `public-package.json`
- `frozen-predictions.json`
- `reveal-key.txt`
- `score.json`
- `attestation.json`

The registry CI recomputes predictions and scores and rejects a tested commit if the audit
implementation changed between that commit and the submission. Technical CI success still reports
`PENDING_IDENTITY_AND_CONFLICT_REVIEW`; repository maintainers must verify the evaluator's public
identity, external challenge-repository history, and conflict declaration before accepting the PR.
