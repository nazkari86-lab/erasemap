from __future__ import annotations

import argparse
import importlib.metadata
from pathlib import Path


def normalized(name: str) -> str:
    return name.lower().replace("_", "-")


def verify(path: Path) -> list[str]:
    mismatches = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise ValueError(f"constraint must use an exact version: {line}")
        name, expected = line.split("==", 1)
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            mismatches.append(f"{normalized(name)} missing; expected {expected}")
            continue
        if actual != expected:
            mismatches.append(
                f"{normalized(name)}=={actual}; expected {normalized(name)}=={expected}"
            )
    return mismatches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--constraints", type=Path, required=True)
    args = parser.parse_args()
    mismatches = verify(args.constraints)
    if mismatches:
        print("\n".join(mismatches))
        return 1
    print(f"verified exact environment: {args.constraints}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
