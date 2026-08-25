# GhostGraph-T v1 report

## Result

The protocol and core were committed as `6aaaf73` before the first result was generated. The first
locked run passed every frozen gate:

| Measure | Global action policy | One-step minimax | Greedy | Random | Exhaustive |
|---|---:|---:|---:|---:|---:|
| Correct action or OOD | 300/300 | 300/300 | 300/300 | 286/300 | 300/300 |
| False confident | 0 | 0 | 0 | 14 | 0 |
| Family OOD | 50/50 | 50/50 | 50/50 | 36/50 | 50/50 |
| Mean probes | 1.28 | 1.28 | 1.28 | 2.92 | 8.00 |
| Mean declared cost | 8.84 | 8.84 | 8.84 | 10.94 | 28.00 |

With zero false-confident events in 300 cases, the Wilson 95% upper bound is 0.01265. This is a
bounded uncertainty statement, not proof of zero risk.

The global policy matched the independently structured recursive oracle on every one of the three
catalogue problems. Their information lower bounds and observed global depths were:

- instance catalogue: lower bound 2, global worst case 2;
- composition catalogue: lower bound 2, global worst case 2;
- temporal-shift catalogue: lower bound 1, global worst case 1.

## Action-equivalence ablation

The exact-graph objective resolved only 130/300 cases and returned `UNVERIFIED` on 170 cases with
irrelevant topology twins. The action objective resolved all 300 because every surviving twin
prescribed the same complete minimum operation-cut family. It did not claim to know which twin was
real.

The sink-only ablation resolved 259/300 and left 41 temporal-shift cases unverified. Passive
declared lineage was correct on only 35/300 and emitted 265 false-confident actions. These are
project-authored controlled ablations, not estimates of organization failure rates.

## Negative result

Global optimization did not beat the strong one-step minimax or greedy separated-pairs baseline on
this catalogue. All three obtained identical correctness, probe count, and declared cost. The
result therefore does not support a claim that full-tree optimization is empirically superior. Its
current contribution is an exact oracle-checked policy value and a globally valid bounded optimum,
not a measured performance gap.

## Interpretation boundary

All 300 cases are deterministic instances from a project-authored grammar. The instance split tests
new structures inside known families; the composition split tests new combinations; the family
split tests only rejection of retry replay as outside the catalogue; and the temporal split remains
inside a declared delayed-transition model. The result does not establish arbitrary open-world
coverage, independent authorship, production FaceID/eGov behavior, legal compliance, world
priority, or patentability.

Reproduce the committed result without overwriting it by choosing a new output directory:

```bash
PYTHONPATH=src:. .venv/bin/python experiments/run_ghostgraph_t_v1.py \
  --output /tmp/ghostgraph-t-v1-replay
.venv/bin/python scripts/verify_ghostgraph_t_v1.py \
  --result /tmp/ghostgraph-t-v1-replay/result.json
```
