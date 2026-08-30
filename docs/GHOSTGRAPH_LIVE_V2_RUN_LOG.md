# GhostGraph live v2 confirmatory execution log

Date: 2026-08-25

The protocol and reveal were unchanged throughout. Two pre-output implementation attempts were
invalidated before an evidence directory was created:

1. the safe singleton was incorrectly sent to temporal planning even though it has no recurrence path;
   all containers were removed and no result bundle was written;
2. the offline scorer compared in-memory tuples with their JSON-list representation; all containers
   were removed and no result bundle was written.

Both defects were deterministic runner/verifier integration errors, not failed scientific gates.
They were committed as explicit fixes before the first output-producing execution. The next run
created the append-only `outputs/ghostgraph-live-v2` bundle and returned PASS. The offline verifier
recomputed the planner, version spaces, native trace agreement, verdicts, metrics, gates, and
artifact hashes. Docker reported no remaining `erasemap-ghostgraph-` containers.
