#!/usr/bin/env python3
"""Check datasheet source records for reachability and basic metadata.

Why this exists
- PDFs may be gitignored for public MIT release.
- We still want reproducible fact-checking: keep URL/DocID/Rev/AccessDate in JSON.
- This script validates the links and (optionally) downloads PDFs into .temp/.

Inputs
- datasheets/datasheet_sources.json (recommended, git-tracked)
- datasheets/datasheet_sources.example.json (template)

Output
- Console summary.
- Non-zero exit code when any required check fails.

Notes
- This does NOT extract pinouts or electrical specs from PDFs.
  Automated extraction can be added later, but must remain conservative.

"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES_PATH = REPO_ROOT / "datasheets" / "datasheet_sources.json"


@dataclass(frozen=True)
class Source:
    part_number: str
    exact_part_number: str
    manufacturer: str
    document_id: str
    revision: str
    url: str
    last_accessed: str


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _sanitize_filename(text: str) -> str:
    text = text.strip()
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    text = re.sub(r"\s+", " ", text)
    return text[:160] if len(text) > 160 else text


def _iter_sources(raw: Any) -> Iterable[Source]:
    if not isinstance(raw, list):
        raise ValueError("datasheet_sources.json must be a list")

    for entry in raw:
        if not isinstance(entry, dict):
            continue

        part_number = str(entry.get("PartNumber", "")).strip()
        sources = entry.get("Sources", [])
        if not part_number or not isinstance(sources, list):
            continue

        for s in sources:
            if not isinstance(s, dict):
                continue
            yield Source(
                part_number=part_number,
                exact_part_number=str(s.get("ExactPartNumber", "")).strip(),
                manufacturer=str(s.get("Manufacturer", "")).strip(),
                document_id=str(s.get("DocumentId", "")).strip(),
                revision=str(s.get("Revision", "")).strip(),
                url=str(s.get("Url", "")).strip(),
                last_accessed=str(s.get("LastAccessed", "")).strip(),
            )


def _request_head(url: str, *, timeout_s: float) -> urllib.response.addinfourl:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "7400SeriesCollection/1.0"})
    return urllib.request.urlopen(req, timeout=timeout_s)


def _request_range_probe(url: str, *, timeout_s: float) -> urllib.response.addinfourl:
    # Some hosts reject HEAD; probe with a tiny ranged GET.
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "7400SeriesCollection/1.0",
            "Range": "bytes=0-0",
        },
    )
    return urllib.request.urlopen(req, timeout=timeout_s)


def _download(url: str, dest: Path, *, timeout_s: float, sleep_s: float = 0.0) -> tuple[int, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(url, headers={"User-Agent": "7400SeriesCollection/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = resp.read()
        dest.write_bytes(data)

    if sleep_s > 0:
        time.sleep(sleep_s)

    sha256 = hashlib.sha256(dest.read_bytes()).hexdigest()
    return dest.stat().st_size, sha256


def main() -> int:
    parser = argparse.ArgumentParser(description="Check datasheet source links and optional downloads")
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES_PATH)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--download", action="store_true", help="Download PDFs to .temp/datasheet_fetch/")
    parser.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between downloads")

    args = parser.parse_args()

    if not args.sources.exists():
        print(f"ERROR: sources file not found: {args.sources}")
        print("Hint: create datasheets/datasheet_sources.json (see datasheets/datasheet_sources.example.json)")
        return 2

    raw = _read_json(args.sources)
    sources = list(_iter_sources(raw))

    if not sources:
        print(f"No sources found in {args.sources}")
        return 0

    failures: list[str] = []
    print("=== check_datasheet_sources ===")
    print(f"sources:  {args.sources}")
    print(f"count:    {len(sources)}")
    print(f"download: {args.download}")

    download_root = REPO_ROOT / ".temp" / "datasheet_fetch"

    for src in sources:
        label = f"{src.part_number} / {src.exact_part_number}"
        if not src.url.startswith("http"):
            failures.append(f"{label}: invalid Url '{src.url}'")
            continue

        try:
            try:
                resp = _request_head(src.url, timeout_s=args.timeout)
            except urllib.error.HTTPError as e:
                # Some servers respond with 405 for HEAD.
                if e.code in (403, 405):
                    resp = _request_range_probe(src.url, timeout_s=args.timeout)
                else:
                    raise

            final_url = getattr(resp, "url", src.url)
            content_type = resp.headers.get("Content-Type", "")
            content_length = resp.headers.get("Content-Length", "")

            print(f"OK  {label}")
            print(f"    url:  {final_url}")
            if content_type:
                print(f"    type: {content_type}")
            if content_length:
                print(f"    size: {content_length}")

            if args.download:
                fn = _sanitize_filename(
                    f"{src.exact_part_number}__{src.manufacturer}__{src.document_id}__{src.revision}.pdf"
                )
                dest = download_root / _sanitize_filename(src.manufacturer or "UNKNOWN") / fn
                size, sha256 = _download(final_url, dest, timeout_s=args.timeout, sleep_s=args.sleep)
                print(f"    saved: {dest}")
                print(f"    bytes: {size}")
                print(f"    sha256:{sha256}")

        except Exception as e:  # noqa: BLE001
            failures.append(f"{label}: {type(e).__name__}: {e}")

    if failures:
        print("=== FAILURES ===")
        for f in failures:
            print(f"- {f}")
        return 1

    print("All sources OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
