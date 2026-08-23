# EraSeMap Open Transfer Challenge v1 design

Date: 2026-08-23
Status: approved direction; written specification awaiting final user review before implementation

## Objective

Increase four evidence dimensions without inflating claims:

1. make the deletion problem understandable to an unfamiliar reviewer in under one minute;
2. quantify why ordinary deletion success signals are operationally insufficient;
3. exercise EraSeMap against stock open-source service processes and a public face dataset;
4. test whether one frozen core contract transfers across identity, experiment-tracking, and vector
   retrieval systems without system-specific changes to the decision algorithm.

The supported result will remain project-authored. Human usability, organization deployment, and
independent topology authorship remain pending until an identifiable external participant performs
them.

## Approaches considered

### A. Extend the existing local storage simulator

This is fast and deterministic, but it would add little transfer evidence because the storage
semantics and faults would remain authored entirely inside EraSeMap.

### B. Run stock open-source services through narrow adapters — selected

Use unmodified Keycloak, MLflow, and Qdrant distributions through their documented interfaces.
Adapters translate observed state into the existing PCUG/RSE/TRE contract but do not alter the core
decision algorithm. This provides the strongest evidence that can be produced locally and openly.

### C. Wait for an organization or external evaluator

This is the only route to high independence and production evidence, but it is externally blocked.
The project will produce a complete evaluator and usability kit now, without recording invented
human or organization results.

The implementation combines B with a handoff-ready version of C.

## Thirty-second demonstration contract

Every service family must expose the same seven-step story:

1. register one subject and a usable derivative;
2. invoke the product's normal deletion operation;
3. show the native success signal;
4. replay one legitimate recovery or materialization workflow;
5. demonstrate whether the subject becomes usable again;
6. show EraSeMap's shortest residual or regeneration path and selected control;
7. rerun the workflow after control and show the final verdict.

The generated showcase must use the same visual vocabulary for all families: source, derivative,
latent carrier, replay transition, and usable sink. It must label every result as observed,
project-authored, externally supplied, or pending.

## Stock service families

### Identity: Keycloak

- Launch an official pinned Keycloak container without modifying its source.
- Create a realm and deterministic synthetic user through the Admin REST API.
- Export or otherwise register a recoverable realm representation through supported container or
  administrative behavior.
- Delete the user through the Admin REST API and preserve the native HTTP success evidence.
- Test whether the registered recovery path can reintroduce the identity.
- Controls are limited to documented subject deletion plus removal or invalidation of the declared
  recovery carrier. The experiment does not claim to model a government identity deployment.

### ML lineage: MLflow

- Launch a pinned stock MLflow tracking server.
- Record a run derived from the public face-data experiment with the subject commitment in declared
  metadata and a real artifact in the configured artifact store.
- Invoke the normal run deletion endpoint and preserve its success evidence.
- Observe soft-deleted metadata and physical artifacts separately; exercise a documented cleanup or
  restore path where available.
- EraSeMap must fail closed when evidence for either store is unavailable.

### Biometric retrieval: Qdrant

- Launch the already pinned Qdrant distribution.
- Store embeddings computed from a documented public face dataset, not invented vectors.
- Delete one subject through the stock points API and preserve the response.
- Register a real Qdrant snapshot or declared import carrier and replay it.
- Query by the deleted subject's embedding before deletion, after native deletion, after replay, and
  after the selected robust control.
- The result is a vector-retrieval analogue of FaceID, not a test of Apple Face ID or any government
  biometric service.

## Input and provenance rules

- Public face samples and embeddings must have source URL, retrieval date, license or terms pointer,
  file hashes, preprocessing code hash, and subject-disjoint split metadata.
- Container images must be referenced by immutable digest in the frozen protocol and recorded again
  from the runtime.
- Every HTTP request/response used as evidence must be canonicalized, redacted of credentials, and
  hashed.
- Synthetic Keycloak identities must be explicitly labeled synthetic. Real public face images are
  real research inputs but are not production records.
- No network response, mutable tag, or local cache alone may be treated as provenance.

## Frozen transfer protocol

The unit of analysis is a service-family deletion case. The confirmatory set contains exactly 60
cases: 20 per family, with five fixed seeds crossed with four fault states:

1. safe native deletion;
2. surviving materialized derivative;
3. recovery-driven regeneration;
4. incomplete observation coverage.

The development/calibration set is disjoint by subject, service object identifier, and seed. The
core algorithm and canonical schema are frozen before confirmatory execution.

### Leave-one-family-out check

For each of the three rotations, two families may be used to validate schema compatibility and tune
only presentation defaults. The held-out family is then evaluated without changing:

- PCUG, RSE, MSC, or TRE implementation;
- verdict thresholds or mandatory channels;
- baseline rules;
- metric code;
- success gates.

System adapters may contain declarative field mappings, but the result records adapter line count,
process startup/runtime, core diff, and any manual exception. Independently measured integration
time is reserved for the external evaluator, who records signed start and finish timestamps. A
rotation fails transfer if core code or a frozen decision rule changes after the held-out run begins.

## Comparators and equal evidence budgets

Each case is scored by three frozen methods over the same registered observations:

1. `native-success`: trusts the product's deletion response or visible absence;
2. `typed-node-audit`: inspects registered stores as nodes but does not replay transitions;
3. `EraSeMap`: evaluates channels and temporal transitions, failing closed on missing coverage.

The primary scientific claim is not that EraSeMap must beat typed-node audit in every safe case. It
must reduce false-complete decisions on regeneration cases without lowering specificity on safe
cases under the same observation budget.

## Primary endpoints and success gates

All confirmatory gates are conjunctive:

- 60/60 cases execute with valid provenance and no unregistered manual repair;
- EraSeMap false-complete count is 0;
- coverage-fault cases are `UNVERIFIED`, never `COMPLETE`;
- post-control physical recurrence is 0 in every regeneration case;
- retained-subject loss is 0;
- native-success has at least one witnessed false-complete case in each family;
- EraSeMap specificity is not lower than typed-node audit on safe cases;
- exact selected controls match a separately implemented exhaustive oracle on every feasible case;
- all three leave-one-family-out rotations have core diff 0;
- every run records service version/digest, input hashes, raw redacted evidence hashes, and teardown.

Secondary outcomes are adapter non-comment line count, service startup time, remediation latency,
bytes rewritten, shortest witness length, and robustness premium. Secondary outcomes cannot rescue
a failed primary gate.

## Usability and significance study kit

The repository will contain a standalone Russian/English packet with twelve one-minute task cards:
four safe, four residual, and four insufficient-evidence cases. It will include:

- randomized answer-blind participant form;
- sealed gold labels and deterministic scoring tool;
- comprehension questions for the problem, verdict, shortest path, and next action;
- preregistered endpoints: unaided explanation, verdict accuracy, path accuracy, action accuracy,
  and completion time;
- consent language that collects no unnecessary personal data;
- an external evaluator attestation and result-signing flow.

No human score is committed until real participants complete the packet. Mechanical validation of
the packet is engineering readiness, not usability evidence. The score-changing target is at least
10 unfamiliar participants, at least 80% correct unaided problem explanations, and at least 80%
accuracy on each primary comprehension endpoint.

Practical significance will be reported through observed false-complete recurrence, remediation
latency, bytes rewritten, and retained-subject preservation. Monetary, legal, breach, or production
risk estimates are excluded unless supplied by an authorized external organization.

## Components

- `benchmark/open-transfer-v1.json`: immutable images, inputs, splits, gates, and claim boundary.
- `src/erasemap/open_transfer.py`: canonical family-neutral records and scoring.
- `experiments/run_open_transfer_v1.py`: stock-service lifecycle and raw evidence capture.
- `scripts/verify_open_transfer_v1.py`: offline verifier for committed and fresh results.
- `external_transfer/`: independent execution, attestation, and submission package.
- `usability/`: bilingual task packet, schemas, scorer, sealed-gold verifier, and empty results area.
- `outputs/open-transfer-v1/`: first confirmatory result and provenance if every service executes.

Service-specific process management belongs in the experiment layer. No Docker, Keycloak, MLflow,
or Qdrant dependency may enter the package's core runtime.

## Failure handling

- Missing Docker, unavailable immutable image, input hash drift, startup timeout, or API mismatch
  aborts the run and produces no passing result.
- Cleanup is scoped to uniquely named containers and temporary directories created by the runner.
- Existing containers, databases, caches, and user files are never reused or deleted.
- Credentials are generated per run, kept outside evidence records, and destroyed during teardown.
- A first confirmatory failure remains visible in git history; fixes require a new protocol version.
- Partial service success may be reported diagnostically but cannot satisfy transfer gates.

## Testing and release gates

- unit and property tests for records, scoring, provenance, redaction, rotations, and fail-closed
  behavior;
- adapter contract tests against frozen response fixtures;
- one live smoke per stock service before the confirmatory run;
- full confirmatory execution only after the protocol commit;
- offline result verification and rerun determinism checks;
- inclusion in the jury showcase, scientific claim matrix, bilingual papers, release reproduction,
  and GitHub Actions verification;
- local full test, strict typing, lint, package build, existing evidence verifiers, and clean-worktree
  release reproduction before publication.

CI will always verify committed artifacts. Live container reruns may use an explicitly separate job
when runtime and image availability are deterministic; otherwise CI must not silently replace the
real process run with mocks.

## Claim and score boundary

A passing local experiment supports transfer across three stock open-source service families under
project-authored mappings and faults. It does not establish production FaceID/eGov/KYC behavior,
independent generalization, legal compliance, or arbitrary unknown-topology coverage.

The evidence can justify approximately:

- problem clarity 9.5 to 9.6 from the executable common demonstration; 9.7 requires actual users;
- practical relevance 9.6 to 9.7 from witnessed failures and measured remediation;
- real inputs and transfer 9.0 to 9.3 or 9.4 if all stock services and public-face gates pass;
- independence remains 7.8 until external authorship and signed execution occur;
- RKNP remains 9.8 until an external evidence event supports 9.9.
