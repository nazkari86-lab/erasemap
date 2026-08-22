# PCUG Mechanism Stress Test and PostgreSQL Pilot

## Typed-audit blind-spot stress test

The project-authored mechanism test contains 100 cases: 25 complete and 75 non-complete. In the 75
non-complete cases all subject-scoped physical nodes appear closed, but a mandatory model evidence,
unknown verifier, or action-replay channel prevents completion.

PCUG produced 0/75 false-complete verdicts. A node-state-only typed audit produced 75/75
false-complete verdicts. This establishes the mechanism by which PCUG adds value beyond typed node
coverage, but it is development evidence and cannot replace an independently authored holdout.

## Real PostgreSQL process pilot

The pilot launched PostgreSQL 15.18 in a new temporary cluster, created a source table, a separately
materialized derived table, and a physical `pg_dump` artifact. It then deleted the source row.
PostgreSQL still returned one subject row from the derived table and the dump remained present with
a recorded SHA-256 hash. PCUG returned `INCOMPLETE` and the shortest residual path
`postgres-derived`.

After the derived row and dump were physically removed, PCUG returned `COMPLETE`. The temporary
server was stopped and its cluster directory was deleted. This is a real database-process pilot
with synthetic records, not an organization production deployment.

Evidence:

- `benchmark/results/pcug-mechanism-stress-v1.json`
- `benchmark/results/postgres-physical-pilot-v1.json`

