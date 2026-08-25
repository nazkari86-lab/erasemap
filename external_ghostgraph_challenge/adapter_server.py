from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from erasemap.ghostgraph import predict_trace
from experiments.run_ghostgraph_v1 import _objects, _truth_graph
from external_ghostgraph_challenge.schema import canonical, load_object, validate_suite_v2


def build_handler(suite: dict[str, Any], core: dict[str, Any]) -> type[BaseHTTPRequestHandler]:
    validate_suite_v2(suite)
    hypotheses, experiments = _objects(core)
    case_by_id = {str(item["case_id"]): item for item in suite["cases"]}
    experiment_by_id = {item.experiment_id: item for item in experiments}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                case = case_by_id[str(payload["case_id"])]
                experiment = experiment_by_id[str(payload["experiment_id"])]
                truth = _truth_graph(case, hypotheses, core)
                body = canonical({"trace_bits": predict_trace(truth, experiment).bits})
                self.send_response(200)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                body = canonical({"error": str(exc)})
                self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--core-protocol", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("reference adapter server must remain loopback-only")
    server = ThreadingHTTPServer(
        (args.host, args.port),
        build_handler(load_object(args.suite), load_object(args.core_protocol)),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
