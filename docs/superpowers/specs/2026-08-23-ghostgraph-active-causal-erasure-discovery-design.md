# GhostGraph: active causal erasure discovery design

Date: 2026-08-23
Status: proposed design awaiting written-spec review

## One-sentence idea

GhostGraph actively chooses synthetic deletion-and-recovery experiments to discover a hidden,
bounded data-resurrection graph, returns the complete observational equivalence class when the graph
is not identifiable, and sends only justified recurrence paths into EraSeMap's PCUG/TRE repair and
physical-replay contract.

## Problem in plain language

Erasure Tomography answers a bounded catalogue question: which listed recovery mechanism can make
deleted data reappear? A real organization may not know the mechanism catalogue or the connections
between services. A backup may restore PostgreSQL, a worker may copy the restored row into Redis,
and a vector-index rebuild may reconstruct a biometric template. A flat mechanism label does not
reveal that causal chain.

GhostGraph treats the infrastructure as a bounded black box. It creates non-person synthetic
subjects, deletes them, selectively activates permitted recovery operations, observes where and
when their commitments recur, and chooses the next experiment that best separates the still
possible hidden graphs. The result is either a uniquely identified recurrence graph, a complete
class of indistinguishable graphs, an explicit model contradiction, or an unverified outcome.

The first version does not infer arbitrary infrastructure from the open world. It discovers a graph
inside a frozen service-and-transition grammar. "Unknown" means hidden from the algorithm and the
declared audit map, not absent from every possible hypothesis.

## Research question

Within a frozen finite grammar of service states, transition types, permitted interventions, and
observable checkpoints, can an exact active experiment planner identify the hidden
subject-resurrection graph, or its complete observational equivalence class, with fewer physical
experiments than exhaustive edge-by-edge auditing while producing zero false confident graphs?

## Scientific contribution under test

GhostGraph tests the composition of:

1. synthetic subject-scoped deletion interventions over real stock services;
2. an exact finite hypothesis space of typed temporal resurrection graphs;
3. deterministic active experiment selection with a machine-checkable one-step minimax
   certificate;
4. fail-closed version-space decoding and complete equivalence-class reporting;
5. shortest causal recurrence witnesses translated into PCUG/TRE controls; and
6. physical post-control replay that tests both non-recurrence and retained-subject specificity.

The contribution is not causal discovery, active learning, data lineage, runtime tracing, mutation
testing, group testing, model checking, shortest paths, or robust optimization individually.

## Relationship to Erasure Tomography

GhostGraph strictly retains ET rather than replacing it. An ET support catalogue can be embedded as
a hypothesis family in which every graph has one source-to-residual mechanism path. GhostGraph adds
hidden intermediate nodes, hidden typed edges, multi-step recurrence, checkpoint observations, and
adaptive experiment selection.

ET remains the cheaper method when the mechanism catalogue is trusted. GhostGraph is used when the
registered topology is incomplete or when ET returns `OUT_OF_MODEL`. No result may claim that
GhostGraph globally removes ET's topology-closure assumption; it replaces it with a larger but still
explicit graph-grammar assumption.

## Formal domain

### Hidden graph

Let the frozen typed node universe be

```text
V = {v_1, ..., v_n}
```

and the allowed typed transition universe be

```text
E_max subseteq V x TransitionType x V.
```

A hidden hypothesis is a temporal graph

```text
G = (V_G, E_G, s_G, R_G),
```

where `E_G subseteq E_max`, `s_G` is the seeded state after the declared deletion procedure, and
`R_G` is the set of subject-residual states. Every graph is immutable, canonically ordered, and
content-addressed. Duplicate graph encodings are rejected.

The hypothesis space

```text
H_0 = {G_1, ..., G_h}
```

is exhaustively generated from the frozen grammar and declared size/mutation limits. The first
confirmatory domain must be small enough that every hypothesis and every predicted outcome can be
enumerated independently.

For v1, the protocol caps the domain at eight nodes, twelve optional edges, 4,096 graph hypotheses,
32 feasible experiments, five checkpoints, three time buckets, and trace-error budget `e = 0`.
Smaller frozen limits are allowed when physical workflow constraints require them, but larger or
noisy domains require a separately preregistered v2. Hitting any cap before complete enumeration is
a capacity failure, not permission to sample hypotheses.

### Experiments

A permitted experiment `q` contains:

- a fresh synthetic subject commitment;
- an exact deletion procedure;
- a subset and order of externally permitted recovery interventions;
- observation checkpoints and time buckets;
- an execution cost declared before outcomes are observed; and
- a finite observation window with a frozen stopping rule.

For graph `G`, the executable semantics produce a Boolean observation trace

```text
f_q(G) in {0,1}^{checkpoint x time_bucket}.
```

The trace records recurrence of the subject commitment, not raw personal or biometric data.
Predictions use typed temporal reachability with only the transitions enabled by `q`.

### Version-space update

After executing experiment `q_t` and observing trace `y_t`, GhostGraph updates

```text
H_t = {G in H_(t-1) : distance(f_q_t(G), y_t) <= e},
```

where `e` is the preregistered trace-error budget. Version-space membership is exact. A heuristic
may accelerate search but cannot decide the scientific verdict.

If evidence validity fails, no update is trusted and the run returns `UNVERIFIED`. If `H_t` is
empty, the result is `OUT_OF_HYPOTHESIS`; GhostGraph reports the shortest observed-versus-predicted
inconsistency but does not invent a new edge.

### Active next-experiment rule

For every unused feasible experiment `q`, predicted traces partition the current version space into
buckets. GhostGraph selects the exact lexicographic minimum

```text
score(q) = (
    largest remaining bucket,
    sum of squared bucket sizes,
    declared physical cost,
    experiment ID
).
```

The first component is a one-step minimax objective: choose the experiment with the smallest
worst-case remaining hypothesis set. The second prefers a more balanced complete partition without
assuming a probability distribution. Cost and ID provide deterministic tie-breaking.

The planner emits a certificate containing every feasible experiment, its partition, score, and the
selected minimum. A separately implemented exhaustive verifier recomputes the certificate.

If no feasible unused experiment separates any pair in `H_t`, execution stops with the complete
observational equivalence class. It must not continue until a convenient singleton appears.

## Verdict contract

GhostGraph returns exactly one of:

- `NO_OBSERVED_RECURRENCE`: every valid executed trace is negative; this is limited to the frozen
  experiment set and observation window;
- `GRAPH_DISCOVERED`: exactly one graph remains consistent with every valid observation;
- `PATH_CLASS_DISCOVERED`: multiple graphs remain but they imply the same subject-relevant
  recurrence paths and the same justified PCUG/TRE control interface;
- `EQUIVALENCE_CLASS`: multiple materially different graphs remain and no feasible experiment can
  separate them;
- `OUT_OF_HYPOTHESIS`: no allowed graph explains the observations within the error budget; and
- `UNVERIFIED`: execution, provenance, isolation, stability, observability, or grammar evidence is
  incomplete.

`PATH_CLASS_DISCOVERED` is allowed only when an independent exact comparison proves equality of all
subject-relevant path and control signatures. It is not graph recovery. Public reports must keep
graph accuracy and path/control accuracy separate.

## Evidence contract

Every confident result requires machine-verifiable evidence for:

1. grammar and hypothesis-space commitment;
2. complete enumeration within declared limits;
3. adapter and container-image digests;
4. faithful execution of the selected intervention sequence;
5. fresh and isolated synthetic subjects;
6. observation coverage for every declared checkpoint;
7. stable behavior inside one discovery episode;
8. verified trace-noise bound;
9. absence of real personal identifiers or biometric material; and
10. no algorithm, planner, grammar, metric, or gate change after graph reveal.

Any missing field forces `UNVERIFIED`, even when one hypothesis remains computationally.

## Formal results

### Theorem 1: version-space soundness

If the true graph belongs to `H_0`, all experiment semantics are sound, and each observed trace is
within error distance `e` of the true prediction, then the true graph remains in every updated
version space.

### Theorem 2: unique-discovery soundness

Under Theorem 1's assumptions, if the final version space is the singleton `{G}`, then `G` is the
true graph within the frozen hypothesis domain.

### Theorem 3: equivalence-class completeness

If no feasible unused experiment gives different admissible predictions for any pair in the final
version space, no experiment in the frozen language can justify choosing one remaining graph over
another. Returning a singleton would be unsound.

### Theorem 4: one-step minimax optimality

The selected experiment minimizes the maximum next version-space size among all feasible unused
experiments, with the declared deterministic tie-break. This is a finite exact optimality claim,
not a claim of globally minimum adaptive decision-tree depth.

### Theorem 5: discovery-to-control safety

If every graph in a discovered graph/path class exposes the same relevant recurrence transitions,
the bridge into PCUG/TRE is sound, selected controls physically implement their declared effects,
and post-control replay observes no recurrence, the replay excludes the discovered recurrence paths
for that experiment domain.

This theorem does not exclude paths outside the frozen grammar or observation window.

The Lean model should formalize finite hypotheses, experiments as observation functions, exact
filtering, separating partitions, and path-signature agreement. It should avoid pretending that
Lean proves the fidelity of Docker adapters; adapter fidelity remains experimental evidence.

## Architecture

### Pure scientific core

`ghostgraph.py` owns immutable nodes, typed edges, graph hypotheses, experiments, traces, version
spaces, verdicts, evidence, exact updates, and canonical serialization.

`ghostgraph_planner.py` computes exact experiment partitions and the deterministic one-step minimax
choice. It has no service or Docker dependency.

`ghostgraph_oracle.py` independently represents graphs as integer masks and traces as packed bits.
It must not call production update, prediction, path, or planner functions.

`ghostgraph_conformance.py` exhaustively compares production and oracle behavior across bounded
grammars, hidden graphs, experiment orderings, and negative evidence cases.

### Physical execution layer

`ghostgraph_lab.py` maps abstract nodes and interventions to stock-service adapters. Each adapter
must support seed, delete, intervene, observe, and reset operations. The first physical graph uses at
least four distinct service/state families, selected from PostgreSQL, Redis, MinIO-compatible object
storage, Qdrant, MLflow artifacts, and a real queue/worker process.

Adapters may expose only subject commitments. Raw synthetic payloads remain local to the experiment
and are deleted during cleanup. Unit tests use fake adapters; evidence claims distinguish fakes from
live digest-pinned containers.

### Existing EraSeMap bridge

`ghostgraph_bridge.py` converts only graph/path-class-certified recurrence edges into existing typed
PCUG transitions and a TRE uncertainty envelope. Unresolved edges and equivalence classes remain
explicit. The bridge cannot silently collapse multiple transition types into one generic node.

## Prospective evaluation

### Phase A: source-committed internal hidden graphs

Before the confirmatory run, commit:

- grammar, node/edge limits, graph generator, and container digests;
- generator seed commitment and later reveal procedure;
- experiment language, costs, planner, and stopping rule;
- trace-error budget and observation window;
- all metrics, baselines, pass/fail gates, and invalid-run rules; and
- source hashes for core semantics and adapters.

Development uses disjoint seeds. The confirmatory graph reveal happens only after protocol and
runner commits. Outputs are append-only and carry provenance linking protocol, reveal, source, image,
and result hashes.

### Phase B: live multi-service transfer

A digest-pinned Docker experiment executes hidden graphs over real stock-service operations. At
least one valid graph must contain a multi-hop recurrence path not representable as a single ET
mechanism label. At least one negative case introduces an omitted transition or an unobservable
checkpoint and must fail closed.

This phase is project-authored stock-service transfer, not independent or production evidence.

### Phase C: independently authored hidden challenge

The repository provides a self-contained evaluator kit and adapter contract. An external evaluator
may author a hidden Docker topology, seal its graph and expected endpoint commitments, run the frozen
GhostGraph build once, and return a signed result bundle. Project authors cannot label this phase
complete, invent the topology, or sign on behalf of an evaluator.

Until an accepted external bundle exists, independence of evidence remains unchanged.

## Baselines

All baselines receive the same feasible experiment language, physical-cost catalogue, and maximum
execution budget:

1. **Passive declared lineage:** no active experiments; use only the initial registered map.
2. **Random feasible experiments:** deterministic frozen seed, same exact version-space decoder.
3. **Greedy pair count:** choose the experiment separating the largest raw number of graph pairs,
   without minimax balancing.
4. **Non-adaptive exhaustive audit:** execute every frozen experiment once.
5. **Erasure Tomography:** flat known-mechanism catalogue without hidden intermediate topology.

GhostGraph does not pass merely because it reconstructs project-authored graphs. It must preserve
zero false confident verdicts and improve at least one preregistered dimension: fewer experiments
than exhaustive audit, smaller worst-case version spaces than random/greedy at equal cost, or valid
discovery of multi-hop paths that the frozen ET representation cannot express.

## Metrics

Primary metrics:

- false confident graph/path-class count;
- exact graph recovery rate on uniquely identifiable cases;
- true-graph containment rate in every reported equivalence class;
- edge precision, edge recall, and graph edit distance;
- subject-relevant path precision and recall;
- experiments and declared physical cost to termination;
- maximum and final version-space size;
- `OUT_OF_HYPOTHESIS` detection rate for omitted-transition cases whose frozen trace lies outside
  the prediction union of the allowed hypothesis space;
- production/oracle mismatch count;
- post-control physical recurrence count; and
- retained synthetic-subject loss count.

Graph metrics are secondary when the frozen experiment language identifies only a path/control
class. The main safety metric is false confident output, not average edge accuracy.

## Confirmatory gates

The first confirmatory protocol passes only if:

- false confident graph/path-class count is zero;
- every valid uniquely identifiable frozen graph is recovered exactly;
- the true graph is contained in every reported equivalence class;
- every deliberately indistinguishable case returns the complete class;
- every preregistered omitted-transition case with a trace outside the allowed prediction union
  returns `OUT_OF_HYPOTHESIS` or `UNVERIFIED`;
- every missing-evidence case returns `UNVERIFIED`;
- production output and planner match the independent oracle everywhere in the conformance domain;
- every localized recurrence path is physically realized before repair;
- post-control recurrence is zero on every repaired valid case;
- retained-subject loss is zero; and
- the preregistered comparison condition against exhaustive/random/greedy/ET is met.

Failure is recorded as a scientific result. Gates are not weakened after reveal.

## Negative and ablation cases

The benchmark deliberately includes:

- two graphs with identical observable traces;
- an unobservable intermediate node;
- an omitted edge type outside the grammar with an observation trace deliberately outside the
  allowed prediction union;
- a trace with more than `e` flipped bits;
- unstable behavior across repeated intervention windows;
- a missing checkpoint observation;
- subject cross-contamination;
- identical path signatures but different irrelevant subgraphs;
- an experiment set with no separating query; and
- a graph where the flat ET label is correct but insufficient to identify the multi-hop cause.

Ablations remove active selection, temporal buckets, checkpoint observations, fail-closed evidence,
and path-class equivalence separately.

## Error handling and operational safety

- Limits on nodes, edges, hypotheses, experiments, and trace size are validated before enumeration.
- Exceeding an exact-domain limit returns an explicit capacity error; it never falls back to an
  unreported heuristic verdict.
- Adapter failure, timeout, partial reset, or container digest mismatch invalidates the episode.
- Every episode uses fresh subject commitments and an isolated namespace.
- Cleanup is verified but cleanup success is not counted as discovery evidence.
- Docker live profiles are opt-in; normal unit tests and CI verify committed results without
  requiring privileged containers.

## Testing and reproducibility

- unit tests for graph validation, canonicalization, reachability traces, version updates, every
  verdict, evidence failures, and deterministic tie-breaking;
- property tests for true-graph containment and experiment-order invariance of a fixed evidence set;
- exact planner versus the independent packed-bit oracle;
- exhaustive conformance over all graphs of several tiny grammars;
- mutation tests that ensure removed evidence checks cause failures;
- prospective protocol/result verifiers with source and image hashes;
- live Docker replay in a separate release profile;
- Lean build with warnings as errors and an axiom audit;
- package build, ruff, strict mypy, coverage gate, release reproduction, and GitHub Actions.

## Public demonstration

The judge-facing view uses one animated but evidence-backed sequence:

```text
delete synthetic user
  -> observe recurrence in vector store
  -> GhostGraph chooses backup-only probe
  -> chooses worker-disabled probe
  -> reveals backup -> PostgreSQL -> worker -> Qdrant path
  -> TRE selects controls
  -> replay shows no recurrence and no retained-user loss
```

The UI always shows the remaining hypothesis count. If two graphs are indistinguishable, both remain
visible; the demonstration must not turn an equivalence class into a dramatic false answer.

## Novelty and claim boundary

Prior work already covers active causal discovery, Boolean network tomography, automated static and
runtime lineage, recovered-state verification, dependency-aware meaningful erasure, deletion
canaries, and robust control. The targeted 2026-08-23 search did not identify the same tested
input/algorithm/output contract: active synthetic deletion interventions, exact fail-closed hidden
resurrection-graph discovery, complete equivalence-class reporting, PCUG/TRE translation, and
physical post-control replay.

That absence supports a high working novelty hypothesis, not world priority, patentability, or
freedom to operate. Before competition submission, update the structured literature and patent
search with the exact mechanism terms. If closer work is found, narrow the claim to the implemented
composition and measured result.

## Success interpretation

A passing internal and Docker result would raise scientific depth, explainability, and transfer
evidence. It would not independently raise the external-evidence score. The project can approach its
realistic ceiling only when a separately authored hidden topology passes the frozen evaluator
without code or gate changes.
