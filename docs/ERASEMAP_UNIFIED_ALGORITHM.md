# EraSeMap: one deletion-verification algorithm

## The simple idea

A database saying `DELETE succeeded` does not prove that a person's data disappeared from backups,
indexes, caches, exports, replicas, or trained models. EraSeMap treats deletion as one end-to-end
decision problem:

> Find every registered way the data can remain or return, choose the least-cost sufficient set of
> actions, replay the result over time, and issue a certificate only if every mandatory check passes.

EraSeMap is the only public algorithm name. PCUG, GhostGraph, CDC, RSE, MSC, and TRE are retained as
implementation and paper identifiers for reproducibility; they are internal stages and solvers.

## Input and output

Input:

- one subject's deletion request;
- a typed graph of stored copies, derivatives, services, and model influence;
- bounded hypotheses for hidden recovery paths;
- safe active probes and candidate deletion/control actions;
- mandatory evidence channels and a temporal observation window.

Output:

- `COMPLETE_WITHIN_ENVELOPE`: every registered physical, derivative, model, and future-recovery
  obligation passed;
- `INCOMPLETE`: a concrete residual path or an unstabilized recovery mechanism remains;
- `UNVERIFIED`: the available topology or evidence is not sufficient to decide safely.

`COMPLETE_WITHIN_ENVELOPE` is deliberately not an open-world promise. A topology, policy, model, or
observation change invalidates the certificate and requires replay.

## Five stages

| Public stage | Plain-language question | Internal implementation |
|---|---|---|
| 1. Map | Where can this person's data or influence exist? | PCUG typed graph and mandatory evidence channels |
| 2. Discover | Can an unlisted recovery path recreate it? | GhostGraph / erasure-tomography active probes |
| 3. Minimize | What is the cheapest sufficient set of actions? | exact CDC plus robust control selection |
| 4. Verify over time | Can data return after deletion succeeds now? | RSE closure over the discovered topology envelope |
| 5. Certify | Can another verifier replay the decision? | signed proof bundle and time-bound certificate |

Model unlearning is an action inside stage 3, not a separate top-level algorithm. It passes only if
its preregistered utility, privacy, and deletion-matched gates pass; otherwise exact retraining is
the fallback.

## Decision rule

Let:

- `P = 1` when the selected physical and model action plan closes every active path and mandatory
  channel;
- `D = 1` when active evidence identifies an actionable registered topology envelope;
- `T = 1` when every scenario in that envelope remains residual-free after temporal replay.

Then:

```text
COMPLETE_WITHIN_ENVELOPE  iff  P = 1 and D = 1 and T = 1
INCOMPLETE                if   a residual or unstabilized path is demonstrated
UNVERIFIED                otherwise
```

The rule is asymmetric by design: missing evidence can never be converted into `COMPLETE`.

## Executable pseudocode

```text
EraSeMap(request, graph, hypotheses, probes, actions, observations):
    map_report = replay_all_registered_paths(graph, request)
    discovery = run_safe_active_probes(hypotheses, probes, observations)
    deletion_plan = exact_minimum_sufficient_actions(graph, actions)

    if discovery is not evidence-backed and actionable:
        return INCOMPLETE if deletion_plan proves a residual else UNVERIFIED

    envelope = build_temporal_envelope(discovery)
    stabilization_plan = exact_robust_controls(envelope)

    if deletion_plan is incomplete or stabilization_plan is infeasible:
        return INCOMPLETE with shortest counterexample
    if either plan or any mandatory observation is unknown:
        return UNVERIFIED

    return COMPLETE_WITHIN_ENVELOPE with replayable certificate inputs
```

The production Python entry point is `erasemap.unified.run_erasemap`. It is a deterministic decision
facade: a service-specific adapter performs the safe probes and supplies its `DiscoveryReport`, while
this function composes that evidence with the registered graph, exact action search, and temporal
replay. Keeping probing at the adapter boundary prevents the pure verifier from making unreviewed
network or destructive calls.

## What the comparison figure does and does not show

The unified comparison dashboard uses six committed same-protocol experiments. Each panel reports
the relevant EraSeMap stage under test against non-EraSeMap baseline strategies: full typed audit,
native service status, random and exhaustive testing, greedy set cover, delete/rebuild-all, and
snapshot audit. The dashboard is a readable evidence map, not a pooled leaderboard.

These baseline implementations were executed by the project under the frozen protocols. They are
not independently authored external reproductions, and results from different panels are not
pooled into a single superiority score. The current evidence contains both wins and a real tie:
EraSeMap's exact action minimizer tied greedy set cover on the small development set.
