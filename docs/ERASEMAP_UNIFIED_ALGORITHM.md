# EraSeMap: specification of one deletion algorithm

## Purpose

EraSeMap decides whether one person's registered raw data, derivatives, model influence, and future
recovery paths have been erased. It intentionally exposes one algorithm and three stages.

## Inputs

- a subject deletion request;
- a typed graph of copies, derivatives, services, and model influence;
- mandatory evidence channels and local verifiers;
- a bounded catalogue of possible hidden recovery paths plus safe probes;
- permitted physical, model, and temporal actions with declared costs;
- a registered observation window and future-transition set.

## Outputs

- `COMPLETE_WITHIN_ENVELOPE`: all registered physical, derivative, model, and temporal obligations
  passed;
- `INCOMPLETE`: at least one concrete residual or unstable path remains;
- `UNVERIFIED`: evidence is insufficient for a safe conclusion.

Only the first verdict permits a certificate. The certificate is invalidated by relevant changes to
the topology, verifier, model, policy, or observation window.

## Stage 1 — FIND

FIND answers: **where can this person's data remain or return?**

It replays registered typed paths and filters bounded recovery-graph hypotheses using safe active
probes. A valid result may identify one graph or a complete observable path class. Out-of-catalogue,
inconsistent, missing, or tampered evidence produces `UNVERIFIED`, never success.

Internal components: PCUG path representation and GhostGraph bounded filtering/minimax probing.

## Stage 2 — ERASE

ERASE answers: **what minimum sufficient set of actions closes every active path?**

It selects a minimum-cost registered feasible plan. Physical actions cover rows, vectors, caches,
indexes, exports, replicas, and backup lineage. Model influence is mandatory: machine unlearning is
compared with exact retraining under preregistered forgetting, retained-utility, privacy-proxy, and
reload gates. A failed fast candidate triggers exact retraining or `INCOMPLETE`; speed alone never
passes the model channel.

Internal components: PCUG mandatory channels and exact CDC action selection.

## Stage 3 — PROVE

PROVE answers: **can the data return after deletion appears successful?**

It replays registered restore, synchronization, cache-warming, index-rebuild, and model-redeployment
transitions across the actionable recovery envelope. It emits a replayable certificate only if the
ERASE plan is complete and every registered temporal scenario remains residual-free.

Internal components: RSE transition closure, MSC exact control selection, evidence hashes, and
certificate readiness.

## Decision rule

Let:

- `P = 1` if physical and model paths are closed;
- `D = 1` if recovery-path evidence is actionable and valid;
- `T = 1` if temporal replay is safe.

```text
COMPLETE_WITHIN_ENVELOPE  iff  P = 1 and D = 1 and T = 1
INCOMPLETE                if   a concrete residual or unstable path is shown
UNVERIFIED                otherwise
```

## Executable pseudocode

```text
EraSeMap(request, graph, hypotheses, probes, actions):
    discovery = FIND(graph, hypotheses, probes)
    plan = ERASE(graph, actions, exact_retraining_reference)

    if discovery is not valid and actionable:
        return INCOMPLETE if plan proves a residual else UNVERIFIED
    if plan is incomplete:
        return INCOMPLETE
    if plan or a mandatory channel is unknown:
        return UNVERIFIED

    replay = PROVE(discovery.envelope, plan)
    if replay demonstrates recurrence:
        return INCOMPLETE
    if replay is missing or uncertain:
        return UNVERIFIED
    return COMPLETE_WITHIN_ENVELOPE with certificate inputs
```

The pure production facade is `erasemap.unified.run_erasemap`. Service adapters perform approved
probes and pass a signed or otherwise evidence-bound `DiscoveryReport`; the verifier itself does not
make unreviewed network or destructive calls.

## Claim boundary

EraSeMap is stronger than a database receipt because it combines physical, derivative, model, and
temporal evidence. It is not an oracle for uninstrumented infrastructure. Current external hidden
evaluation is `NOT_COLLECTED`, and production FaceID/eGov deployment is not established.
