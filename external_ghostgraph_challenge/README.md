# External GhostGraph challenge v1

This kit lets a person outside the EraSeMap project author hidden deletion-resurrection graphs and
observations without disclosing answers before execution. It does not turn a project-authored test
into independent evidence: independence begins only after a real evaluator authors, seals, runs,
reveals, and signs a bundle.

## Evaluator workflow

1. Copy the clean repository and record its full commit.
2. Author at least five cases in `erasemap-external-ghostgraph-suite-v1` format, covering all five
   kinds listed in `protocol-v1.json`. Use only synthetic subject commitments.
3. Run `seal.py`. Keep `truth-reveal.json` and the generated key private; give the project only
   `public.json`, `commitment.json`, and `sealed.bin` before execution.
4. Run `run.py` against the frozen `benchmark/ghostgraph-v1.json`. The public input contains traces
   and evidence but no truth labels or expected verdicts.
5. Reveal the original suite, create `manifest.json` with all nine evidence gates, and sign the
   canonical manifest using a fresh Ed25519 evaluator key.
6. Run `verify.py --submission BUNDLE`. A cryptographically valid result remains pending human
   identity, conflict-of-interest, and organizational-authorization review.

Without such a bundle, the only valid public status is `NOT_COLLECTED`. Never commit a
project-generated signature as independent validation.
