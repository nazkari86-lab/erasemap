#!/usr/bin/env python3
"""Download all pages of a Kaggle kernel output.

The Kaggle CLI currently returns the first page and a continuation token but
does not follow that token. This helper keeps the collection step complete and
can restrict downloads to the experiment artifact directory.
"""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
from typing import Any


def _safe_target(root: Path, remote_name: str) -> Path:
    relative = PurePosixPath(remote_name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe Kaggle output path: {remote_name!r}")
    return root.joinpath(*relative.parts)


def _selected(remote_name: str, prefixes: tuple[str, ...]) -> bool:
    return not prefixes or any(
        remote_name == prefix.rstrip("/") or remote_name.startswith(prefix)
        for prefix in prefixes
    )


def download_all_pages(
    *,
    kernel: str,
    destination: Path,
    prefixes: tuple[str, ...],
) -> tuple[int, int]:
    import requests  # type: ignore[import-untyped]
    from kaggle.api.kaggle_api_extended import (  # type: ignore[import-not-found]
        ApiListKernelSessionOutputRequest,
        KaggleApi,
    )

    owner, slug = kernel.split("/", maxsplit=1)
    destination.mkdir(parents=True, exist_ok=True)
    api = KaggleApi()
    api.authenticate()
    page_token = ""
    seen_tokens: set[str] = set()
    page_count = 0
    file_count = 0

    with api.build_kaggle_client() as client:
        while True:
            request = ApiListKernelSessionOutputRequest()
            request.user_name = owner
            request.kernel_slug = slug
            request.page_size = 100
            if page_token:
                request.page_token = page_token
            response: Any = client.kernels.kernels_api_client.list_kernel_session_output(
                request
            )
            page_count += 1
            for item in response.files:
                remote_name = str(item.file_name)
                if not _selected(remote_name, prefixes):
                    continue
                target = _safe_target(destination, remote_name)
                target.parent.mkdir(parents=True, exist_ok=True)
                with requests.get(item.url, stream=True, timeout=120) as download:
                    download.raise_for_status()
                    with target.open("wb") as output:
                        for chunk in download.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                output.write(chunk)
                file_count += 1

            log = str(response.log or "")
            if log:
                (destination / f"{slug}.log").write_text(log, encoding="utf-8")

            next_token = str(response.next_page_token or "")
            if not next_token:
                break
            if next_token in seen_tokens:
                raise RuntimeError("Kaggle output pagination repeated a page token")
            seen_tokens.add(next_token)
            page_token = next_token

    return page_count, file_count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kernel")
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--prefix", action="append", default=[])
    args = parser.parse_args()
    if args.kernel.count("/") != 1:
        raise SystemExit("kernel must have the form owner/slug")
    pages, files = download_all_pages(
        kernel=args.kernel,
        destination=args.destination,
        prefixes=tuple(args.prefix),
    )
    print(f"Downloaded {files} selected files across {pages} Kaggle output pages")


if __name__ == "__main__":
    main()
