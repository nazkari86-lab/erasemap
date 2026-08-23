# External temporal hidden challenge

This kit lets an external person or organization author RSE transition systems and labels without
revealing the answers before EraSeMap predictions are frozen.

## Four phases

1. The external author creates an authored suite containing public case fields plus `expected`
   labels (`verdict` and optional `minimum_cost`).
2. `seal.py` writes public cases, private answers, and SHA-256 commitments. Publish the public cases
   and commitment manifest; keep `answers.private.json` private.
3. Run EraSeMap on only the public cases and freeze `predictions.json`.
4. Reveal the original answer file and score it against the commitments.

Start from [`example-author-suite.json`](example-author-suite.json). Author metadata is intentionally
strict: name, organization, stable public identifier, external repository and its frozen commit,
plus an explicit independent-authorship declaration. The example declares `false` and is only a
schema demonstration; duplicating it cannot satisfy the official gate.

```bash
python -m external_temporal_challenge.seal authored-suite.json --output sealed
python -m external_temporal_challenge.runner \
  sealed/public-cases.json --output predictions.json
python -m external_temporal_challenge.score \
  --public sealed/public-cases.json \
  --predictions predictions.json \
  --answers sealed/answers.private.json \
  --manifest sealed/commitment-manifest.json \
  --protocol external_temporal_challenge/protocol-v1.json \
  --output score.json
```

The competition gate requires at least 120 cases, four externally authored families, at least 100
non-verified cases, zero false `RSE_VERIFIED` decisions, verdict accuracy at least 0.95, and exact
control-cost accuracy at least 0.95 where the author provides an optimum. The runner refuses a dirty
EraSeMap worktree, records the full tested Git commit, and binds predictions to the exact public-suite bytes.
The official scorer also requires `independently_authored: true`; that declaration still needs
human-verifiable repository history and evaluator identity to count as independent evidence.

The kit is executable readiness, not independent evidence. Independence remains pending until an
identifiable external author actually freezes, reveals, and submits a result against an unchanged
EraSeMap commit.
