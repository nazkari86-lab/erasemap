# Independent evaluator protocol

EraseMap supports a hidden fixture suite without requiring its author to disclose the cases before
evaluation. This is an evaluator interface, not evidence that an independent evaluation has already
occurred.

1. The evaluator creates fixtures using the JSON schema demonstrated by
   `benchmark/manual-pipelines-v1.json` and keeps them outside this repository.
2. Before receiving a tested commit, the evaluator publishes `sha256sum hidden-suite.json` with a
   timestamp or signs that digest. This prevents after-the-fact suite replacement.
3. On a clean checkout at the declared commit, the evaluator runs:

   ```bash
   PYTHONPATH=src python experiments/run_manual_pipeline_benchmark.py \
     --fixtures /private/hidden-suite.json \
     --expected-sha256 <precommitted-sha256> \
     --output /private/hidden-result.json
   ```

4. The evaluator publishes the commit SHA, fixture commitment, EraseMap version, total cases,
   passed cases, and the SHA-256 of the result. The hidden fixtures may remain private.
5. A project author must not label this as independent validation until the evaluator, not the
   project author, controls the suite and publishes the signed result.

The runner fails before evaluation if the file does not match the supplied commitment. A hidden
suite can establish generalization across new graph cases; it cannot by itself establish access to
unregistered databases or production eGov/FaceID integrations.
