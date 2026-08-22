from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

from erasemap.cdc import evaluate_actions
from erasemap.pcug_domain import (
    CDCProtocol,
    ChannelDecision,
    ChannelResult,
    EdgeKind,
    EdgeState,
    PCUGEdge,
    PCUGGraph,
    PCUGNode,
)


def command(*parts: str, capture: bool = False) -> str:
    completed = subprocess.run(parts, check=True, capture_output=capture, text=True)
    return completed.stdout.strip() if capture else ""


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def audit_graph(derived_active: bool, backup_active: bool) -> tuple[str, list[str] | None]:
    subject = "pilot-subject-001"
    source = PCUGNode(
        "postgres-source", "postgres_row", subject, EdgeState.CLOSED, evidence_id="sql-delete"
    )
    derived = PCUGNode(
        "postgres-derived",
        "materialized_projection",
        subject,
        EdgeState.ACTIVE if derived_active else EdgeState.CLOSED,
        active_sink=derived_active,
        evidence_id="" if derived_active else "sql-delete-derived",
    )
    backup = PCUGNode(
        "postgres-dump",
        "physical_backup",
        subject,
        EdgeState.ACTIVE if backup_active else EdgeState.CLOSED,
        active_sink=backup_active,
        evidence_id="" if backup_active else "filesystem-absence",
    )
    graph = PCUGGraph(
        (source, derived, backup),
        (
            PCUGEdge(
                "postgres-source",
                "postgres-derived",
                EdgeKind.MATERIAL,
                EdgeState.ACTIVE if derived_active else EdgeState.CLOSED,
                True,
                subject,
            ),
            PCUGEdge(
                "postgres-source",
                "postgres-dump",
                EdgeKind.MATERIAL,
                EdgeState.ACTIVE if backup_active else EdgeState.CLOSED,
                True,
                subject,
            ),
        ),
        (
            ChannelResult(
                "physical_absence",
                0.0,
                0.0,
                0.0,
                ChannelDecision.PASS,
                True,
                "postgres-query-and-file-check",
                "postgres_pilot",
            ),
        ),
    )
    protocol = CDCProtocol(
        "postgres-physical-pilot-v1",
        subject,
        frozenset({"postgres-source"}),
        frozenset({"postgres-derived", "postgres-dump"}),
        frozenset({"physical_absence"}),
    )
    report = evaluate_actions(graph, protocol, ())
    return report.verdict.value, list(
        report.shortest_counterexample
    ) if report.shortest_counterexample else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="benchmark/results/postgres-physical-pilot-v1.json")
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    required = ("initdb", "pg_ctl", "psql", "createdb", "pg_dump")
    binaries = {name: shutil.which(name) for name in required}
    if any(value is None for value in binaries.values()):
        raise RuntimeError(f"missing PostgreSQL binary: {binaries}")
    with tempfile.TemporaryDirectory(prefix="erasemap-postgres-pilot-") as temporary:
        root = Path(temporary)
        cluster, socket_dir, dump = root / "cluster", root / "socket", root / "subject.sql"
        socket_dir.mkdir()
        port = free_port()
        command(str(binaries["initdb"]), "-D", str(cluster), "--auth=trust", "--no-locale")
        command(
            str(binaries["pg_ctl"]),
            "-D",
            str(cluster),
            "-o",
            f"-p {port} -k {socket_dir} -h ''",
            "-w",
            "start",
        )
        try:
            base = ("-h", str(socket_dir), "-p", str(port))
            command(str(binaries["createdb"]), *base, "erasemap_pilot")
            sql = (
                "CREATE TABLE source_records(subject text primary key, payload text);"
                "CREATE TABLE derived_index(subject text primary key, embedding text);"
                "INSERT INTO source_records VALUES ('pilot-subject-001','biometric-sample');"
                "INSERT INTO derived_index VALUES ('pilot-subject-001','vector-001');"
            )
            command(
                str(binaries["psql"]),
                *base,
                "-d",
                "erasemap_pilot",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                sql,
            )
            command(str(binaries["pg_dump"]), *base, "-d", "erasemap_pilot", "-f", str(dump))
            dump_before = file_hash(dump)
            command(
                str(binaries["psql"]),
                *base,
                "-d",
                "erasemap_pilot",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "DELETE FROM source_records WHERE subject='pilot-subject-001';",
            )
            derived_count = int(
                command(
                    str(binaries["psql"]),
                    *base,
                    "-d",
                    "erasemap_pilot",
                    "-Atc",
                    "SELECT count(*) FROM derived_index WHERE subject='pilot-subject-001';",
                    capture=True,
                )
            )
            before_verdict, before_path = audit_graph(derived_count == 1, dump.exists())
            command(
                str(binaries["psql"]),
                *base,
                "-d",
                "erasemap_pilot",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "DELETE FROM derived_index WHERE subject='pilot-subject-001';",
            )
            dump.unlink()
            after_verdict, after_path = audit_graph(False, dump.exists())
        finally:
            command(str(binaries["pg_ctl"]), "-D", str(cluster), "-m", "fast", "-w", "stop")
    payload = {
        "after": {"shortest_path": after_path, "verdict": after_verdict},
        "before": {
            "backup_hash": dump_before,
            "derived_rows": derived_count,
            "shortest_path": before_path,
            "verdict": before_verdict,
        },
        "claim_boundary": (
            "Real isolated PostgreSQL process; synthetic records; no organization infrastructure."
        ),
        "database": "temporary PostgreSQL cluster",
        "schema_version": "erasemap-postgres-physical-pilot-v1",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
