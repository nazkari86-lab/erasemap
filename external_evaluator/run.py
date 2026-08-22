from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from erasemap.external_cases import build_source_cases
from erasemap.external_evaluator import evaluate_public_cases
from erasemap.holdout_commitment import create_output_directory, public_cases
from erasemap.source_lock import load_source_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the public EraSeMap PCUG evaluator")
    parser.add_argument("--sources", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = create_output_directory(args.output)
    cases = build_source_cases(load_source_manifest(args.sources))
    records = evaluate_public_cases(public_cases(cases))
    (output / "evaluation-records.json").write_text(
        json.dumps([asdict(record) for record in records], sort_keys=True) + "\n"
    )
    print(f"wrote {len(records)} answer-blind records to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
