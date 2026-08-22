# External production-pilot protocol

This protocol converts the PostgreSQL laboratory pilot into a frozen procedure that a school,
bank, identity provider, government contractor, or public agency can execute without exposing
personal data to the EraSeMap repository.

## Roles and freeze boundary

The external evaluator controls topology authorship, residual-fault placement, labels, evidence
collection, and reveal timing. Before any labels are revealed, the evaluator records the exact Git
commit in `pilot/manifest-template.json`; EraSeMap predictions are frozen with the blinded challenge
tool. The project author must not tune the algorithm or cases after that boundary.

## Minimum execution

1. Use synthetic or explicitly consented test identities only.
2. Query at least two independently persisted systems, such as a source database and a derived
   index, backup, export, cache, feature store, or model-evidence service.
3. Collect redacted, hashed artifacts at three stages: before deletion, after source deletion, and
   after remediation.
4. Do not commit credentials, infrastructure names, biometric samples, raw database dumps, or
   personal records. The public manifest contains hashes and aliases only.
5. Run `python -m pilot.validate manifest.json`. A `READY` result proves structural completeness of
   the evidence package, not that the organization's factual attestations are true.
6. Publish the frozen prediction commitment, answer commitment, score, pilot manifest, evaluator
   signature or institutional letter, and the exact EraSeMap commit.

## Success criteria

The blinded challenge must pass `external_challenge/protocol-v1.json`. The pilot must demonstrate at
least one intentionally retained residual path after source deletion, require EraSeMap to return
`INCOMPLETE` or `UNVERIFIED`, and then return `COMPLETE` only after the evaluator independently
confirms remediation. Operational latency and connector failures must be reported, even when the
audit verdict is correct.

Until a manifest is completed and signed outside the project, this repository claims only
production-pilot readiness—not a production deployment or independent organizational validation.
