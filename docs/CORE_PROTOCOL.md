# EraseMap Core Protocol v1

## Research question

Can a typed lineage graph reduce false claims of complete biometric erasure compared with a
signed-receipt check, a flat store checklist, and an untyped graph traversal under controlled,
seeded faults?

The primary endpoint is **false-complete rate**: among trials containing an injected prohibited
residual, the fraction in which a method declares deletion complete. Lower is better. Recall,
precision, false-alarm rate, exact faulty-node recall, runtime, and remediation cost are secondary
endpoints. Every zero denominator is reported as `null`; it is never replaced with zero.

## Registered erasure graph

Each artifact has an opaque ID, opaque subject ID, type, lifecycle state, optional active-sink
flag, purpose, pre-deletion commitment, and evidence ID. The v1 artifact types are source record,
biometric template, search-index entry, cache entry, backup copy, model influence, and audit
receipt. Edges describe copying, derivation, indexing, backup, training use, or supersession.

JSON decoding rejects missing fields, unknown fields, duplicate nodes or edges, unknown edge
endpoints, and implicit cross-subject edges. Canonical encoding sorts nodes, edges, and JSON keys.

The fixed demonstration has five branches from `source`: template, index, cache, backup, and model.
Its active template is a test fixture, not a measured prevalence estimate.

## Evidence contracts and states

Evidence is typed because one generic signed message cannot establish every deletion fact:

| Artifact | Required evidence |
|---|---|
| Source, template, index | Matching pre-deletion commitment and observed absence |
| Cache | Invalidation plus elapsed propagation deadline and observed absence |
| Backup | Future expiry schedule, or signed destruction of its encryption key |
| Model influence | Frozen protocol, exact-retraining reference, and passing model audit |
| Blocked artifact | Signed and enforced processing control |
| Receipt | Valid envelope, unreplayed nonce, and matching graph-root commitment |

`COMPLETE` means every reachable registered artifact satisfies its contract. `INCOMPLETE` means an
active residual is reachable and includes the shortest counterexample. `UNVERIFIED` means no
active residual was established, but evidence is missing, invalid, or still waiting for expiry.

## Remediation

Actions declare covered artifacts, cost, resulting erased or blocked state, and policy
permission. Exact branch-and-bound is used for at most 30 permitted actions; a deterministic
cost-per-newly-covered-node greedy solver handles larger sets. Costs are protocol fixtures unless
explicitly labelled as measured operational costs.

## Fixed comparators

- `receipt-only` trusts a signed receipt without inspecting downstream artifacts.
- `flat-checklist` inspects only source, template, and index stores.
- `untyped-traversal` follows the graph but treats non-empty evidence kinds as interchangeable.
- `erasemap` traverses the graph and validates the artifact-specific evidence contract.

These comparators are deliberately simple and frozen before holdout evaluation. They are not
claimed to represent every commercial deletion product.

## Controlled benchmark

[`benchmark/protocol-v1.json`](../benchmark/protocol-v1.json) freezes development and holdout
seeds, graph sizes, ten fault types plus clean trials, method names, bootstrap seed, bootstrap
sample count, and primary endpoint. The generator uses a local seeded random stream and never
mutates global randomness. It emits government-identity, bank-KYC, and school-access labels over
the same controlled graph semantics.

Run only development trials while the method can still change:

```bash
erasemap benchmark dev --protocol benchmark/protocol-v1.json --output outputs/dev-v1
```

Each run writes a revision/protocol manifest, one record per method-trial pair, aggregate metrics
with deterministic percentile-bootstrap 95% intervals, and a failure journal. Exceptions are
recorded, never silently dropped. Holdout execution refuses a dirty Git tree and creates a
one-time lock containing the protocol and commit hashes. The holdout must not be run during method
development.

### Development result, 2026-08-21

The local development run for protocol
`sha256:5436399094aa1f867f70c4276aeed5875565950839ce4631cbb7e00ef6099ed0`
completed 396 method-trial pairs with zero recorded exceptions. There were 99 trials per method,
including 90 fault-positive trials. These are measured synthetic **development** results and are
not independent validation:

| Method | False-complete rate (bootstrap 95% interval) | Fault recall | Exact-node recall |
|---|---:|---:|---:|
| EraseMap | 0.000 (0.000–0.000) | 1.000 | 1.000 |
| Flat checklist | 0.600 (0.494–0.690) | 0.400 | 0.400 |
| Receipt only | 0.967 (0.924–1.000) | 0.033 | 0.000 |
| Untyped traversal | 0.400 (0.300–0.494) | 0.600 | 0.600 |

The perfect EraseMap development score is expected because generator and detector share the v1
contract. It demonstrates implementation consistency, not real-world generalization. The locked
holdout and externally sourced schemas remain unopened requirements.

## Receipt boundary

The Ed25519 receipt signs only schema version, request ID, graph-root commitment, audit status,
timestamp, random nonce, and previous-receipt hash. It excludes subject identifiers, biometric
values, raw lineage paths, evidence contents, and free text. Verification checks the envelope,
timestamp, chain, and nonce replay.

A valid signature proves integrity and signer possession of a key. It does **not** prove that the
signed deletion statement is true. EraseMap therefore evaluates artifact evidence before issuing
or trusting an audit result.

## Scope and falsifiability

The core experiment can support claims about detection on seeded registered graphs. It cannot
support claims about unknown physical copies, legal compliance, real-world adoption, production
latency, or transfer to eGov/Face ID without independent integrations and external validation.
The generalization hypothesis should be tested later on separately sourced schemas and a locked
holdout; failed transfer remains a valid and reportable outcome.
