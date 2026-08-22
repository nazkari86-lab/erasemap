# EraSeMap external evaluator kit

This kit lets an evaluator create answer-blind PCUG records without receiving holdout truth. Install
the committed wheel in a clean Python 3.11+ environment, then run:

```bash
python external_evaluator/run.py \
  --sources benchmark/external-sources-v1.json \
  --output evaluator-output
python external_evaluator/verify.py evaluator-output/evaluation-records.json
```

The output directory must not exist. The tools reject duplicate records, unknown fields, invalid
verdicts, changed source excerpts, and source-hash mismatches.

For a private organization pilot, replace the public source manifest and case mappings with a
locally reviewed manifest that contains no personal data or credentials. Keep topology truth and
signing keys under evaluator control. Return only signed records and non-sensitive provenance.

Running this kit is not production validation by itself. A production claim additionally requires
written authorization, complete instrumentation, representative populations, operational threat
modelling, and independently controlled keys.

