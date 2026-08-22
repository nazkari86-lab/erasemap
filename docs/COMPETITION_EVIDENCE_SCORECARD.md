# EraSeMap competition evidence scorecard

Snapshot: 2026-08-22. This is a fixed evidence map, not an official RKNP or ISEF score and not a
probability of winning. A number may move only after the named evidence event occurs.

## Thirty-second explanation

Deleting the main biometric row does not guarantee deletion: a template, vector index, cache,
backup, model influence, or stale service can still use the person. EraSeMap registers these
derivatives in one typed graph and returns one of three verdicts:

- `COMPLETE`: every represented residual path is closed and every mandatory verifier passed;
- `INCOMPLETE`: a usable residual remains, with the shortest counterexample path;
- `UNVERIFIED`: the available evidence is insufficient, stale, or inconsistent.

It then computes the minimum-cost permitted set of actions needed to reach verified completion.

## Evidence-anchored assessment

| Dimension | Current | Observable evidence | Next score-changing event |
|---|---:|---|---|
| Problem clarity | 9.5/10 | `examples/five_branch_system.json` gives a two-node counterexample: `source -> template` | Usability test with judges or operators who can explain the result unaided |
| Practical relevance | 9.6/10 | Contracts cover source, template, cache, vector store, backup, and model influence | Authorized organization pilot on actual deletion workflow |
| Narrow scientific novelty | 9.5/10 | Fail-closed composition plus PCUG/CDC; formal and stress evidence; prior-art exclusions are explicit | Untouched external interaction cases outperform a strong typed-node/replay baseline |
| Experimental methodology | 9.5/10 | Frozen protocols, one-shot holdouts, paired bootstrap, negative MUFAC result retained | Independently authored preregistered holdout |
| Scientific claim completion | 9.3/10 | Formal conditional soundness, finite optimality, local measured systems result | External hidden challenge plus materially different system replication |
| Real inputs and transfer | 9.0/10 | Open face datasets, official source structures, real PostgreSQL/Redis/Qdrant processes | Authorized real records or redacted production instrumentation |
| Independence of evidence | 7.8/10 | Executable signed challenge exists, but `external_results/` has no accepted external result | One verified evaluator passes all 9.5 rubric gates |
| Formal justification | 9.6/10 | Lean proof, axiom audit, 3,072/3,072 production/oracle conformance runs | Independent proof review or stronger implementation-refinement theorem |
| Engineering | 9.8/10 | Strict typing, tests, coverage gate, reproducible CI, signed evidence and drift checks | Reproducible external deployment or release audit |
| Reproducibility | 9.8/10 | One-command gates, committed protocols, raw hashes, deterministic showcase | Independent clean-machine reproduction |
| FaceID/eGov/KYC applicability | 9.4/10 | System-neutral typed contract and display adapters | Authorized domain-specific instrumentation and evaluation |
| Competition presentation readiness | 9.7/10 | Jury showcase, Russian defense script, Q&A, evidence-led slide deck | Timed rehearsal with an unfamiliar reviewer |
| RKNP competitiveness | 9.8/10 | Formal result plus measured multi-service result satisfy the frozen 9.8 trigger | External PASS or organization confirmation for a defensible 9.9 |
| ISEF-level readiness | 9.5/10 | Strong contribution, honest limitations, reproducible artifacts, formal and measured results | External PASS raises evidence readiness toward 9.7–9.8 |

The independence row is deliberately not averaged away. More project-authored code cannot move it
above 7.8.

## Strongest results, without scope inflation

1. **Mechanism:** on 75 project-authored non-complete interaction cases, PCUG made 0 false-complete
   decisions while node-only typed audit made 75. This explains why channels and replay matter; it
   is not external superiority evidence.
2. **Formal:** Lean checks conditional replay soundness and finite CDC optimality. Production
   `exact_cdc` matched exhaustive selection in 3,072/3,072 preregistered runs.
3. **Measured systems:** across 20 paired local holdout seeds using real PostgreSQL, Redis, Qdrant,
   encrypted backups, and a ridge model, exact CDC maintained 100% completion and retained data,
   achieved 17.64x geometric-mean speedup with 95% CI [16.39x, 18.98x], and wrote 94.62% fewer
   declared application/filesystem bytes than rebuild-all.
4. **Model layer:** adaptive MUFAC v3.2 passed the unchanged bounded utility/privacy gates at 1.59x
   speedup, but it is a post-exposure improvement rather than fresh confirmation.
5. **External boundary:** the independent score remains 7.8 until an identifiable evaluator authors,
   freezes, reveals, signs, and submits the challenge.

## Reproduce the jury artifact

```bash
erasemap showcase --repo-root . --output outputs/jury-showcase-v1
open outputs/jury-showcase-v1/index.html
```

The command recomputes the live audit, validates frozen result invariants, includes SHA-256 hashes
of every source artifact, and fails closed if a headline result is changed.
