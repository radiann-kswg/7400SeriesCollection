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
import time
from datetime import datetime, timezone
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES_PATH = REPO_ROOT / "datasheets" / "datasheet_sources.json"


_TI_SYMLINK_PREFIX = "https://www.ti.com/lit/ds/symlink/"


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class Source:
    part_number: str
    exact_part_number: str
    manufacturer: str
    document_id: str
    revision: str
    url: str
    last_accessed: str


def _is_pdf_signature(data: bytes) -> bool:
    return data.startswith(b"%PDF")


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


def _probe(url: str, *, timeout_s: float) -> urllib.response.addinfourl:
    """Return a response object for metadata probing.

    Prefer HEAD; fall back to a minimal GET when needed.
    """
    try:
        return _request_head(url, timeout_s=timeout_s)
    except urllib.error.HTTPError as e:
        # Some servers respond with 403/405 for HEAD.
        if e.code in (403, 405):
            return _request_range_probe(url, timeout_s=timeout_s)
        raise


def _is_ti_symlink_url(url: str) -> bool:
    return url.startswith(_TI_SYMLINK_PREFIX)


def _ti_symlink_fallback_urls(url: str, *, max_strips: int = 6) -> list[str]:
    """Generate fallback TI symlink URLs by stripping trailing alpha suffixes.

    TI's /lit/ds/symlink/ URLs often omit package/temperature suffixes that appear
    in orderable part numbers (e.g. SN74HC30N -> sn74hc30.pdf).

    This keeps the approach conservative: we only try nearby variants of the same
    stem without scraping or crawling.
    """
    if not _is_ti_symlink_url(url) or not url.lower().endswith(".pdf"):
        return [url]

    stem = url.rsplit("/", 1)[-1]
    if not stem.lower().endswith(".pdf"):
        return [url]

    base = stem[:-4]  # drop .pdf
    variants: list[str] = []

    def add(st: str) -> None:
        u = f"{_TI_SYMLINK_PREFIX}{st}.pdf"
        if u not in variants:
            variants.append(u)

    add(base)

    cur = base
    strips = 0
    while strips < max_strips and cur and cur[-1].isalpha():
        cur = cur[:-1]
        strips += 1
        if cur:
            add(cur)

    return variants


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check datasheet source links and optional downloads")
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES_PATH)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--download", action="store_true", help="Download PDFs to .temp/datasheet_fetch/")
    parser.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between downloads")
    parser.add_argument(
        "--skip-empty",
        action="store_true",
        help="Skip entries with empty Url (useful while bootstrapping datasheet_sources.json)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=REPO_ROOT / ".temp" / "datasheet_fetch" / "report.json",
        help="Write a machine-readable report JSON (default: .temp/datasheet_fetch/report.json)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update datasheet_sources.json with fetched metadata (FinalUrl/ContentType/Bytes/Sha256/CheckedAt)",
    )
    parser.add_argument(
        "--strict-mime",
        action="store_true",
        help="Fail if Content-Type is present and does not look like PDF",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=0,
        help="Process at most N source records (0 = no limit). Useful for batching.",
    )
    parser.add_argument(
        "--only-ti-symlink",
        action="store_true",
        help="Only check URLs under https://www.ti.com/lit/ds/symlink/ (safe default while bootstrapping).",
    )
    parser.add_argument(
        "--heal-ti-symlink-url",
        action="store_true",
        help=(
            "If a TI symlink Url returns 404 but a nearby variant works (e.g. strip trailing package suffix), "
            "and --update is enabled, rewrite Url to the working variant."
        ),
    )
    parser.add_argument(
        "--write-report-every",
        type=int,
        default=25,
        help="Write intermediate report JSON every N processed records (0 = only write at end).",
    )

    args = parser.parse_args()

    if not args.sources.exists():
        print(f"ERROR: sources file not found: {args.sources}")
        print("Hint: create datasheets/datasheet_sources.json (see datasheets/datasheet_sources.example.json)")
        return 2

    raw = _read_json(args.sources)
    sources = list(_iter_sources(raw))

    # Reduce work early when caller is intentionally narrowing scope.
    if args.skip_empty:
        sources = [s for s in sources if s.url]
    if args.only_ti_symlink:
        sources = [s for s in sources if _is_ti_symlink_url(s.url)]

    if not sources:
        print(f"No sources found in {args.sources}")
        return 0

    failures: list[str] = []
    warnings: list[str] = []
    print("=== check_datasheet_sources ===")
    print(f"sources:  {args.sources}")
    print(f"count:    {len(sources)}")
    print(f"download: {args.download}")
    print(f"skipEmpty:{args.skip_empty}")
    print(f"report:   {args.report}")
    print(f"update:   {args.update}")

    download_root = REPO_ROOT / ".temp" / "datasheet_fetch"

    report_items: list[dict[str, Any]] = []

    # Optional update requires working with the raw JSON structure.
    raw_for_update = raw if isinstance(raw, list) else None
    now_iso = _now_iso_utc()

    def write_report(*, processed: int) -> None:
        report_obj = {
            "CheckedAt": now_iso,
            "SourcesFile": str(args.sources.relative_to(REPO_ROOT) if args.sources.is_absolute() else args.sources),
            "Count": len(report_items),
            "Processed": processed,
            "Total": len(sources),
            "Download": args.download,
            "Items": report_items,
            "Warnings": warnings,
            "Failures": failures,
        }
        _write_json(args.report, report_obj)

    processed = 0
    checked = 0

    # Write an initial report so callers can see progress even if interrupted.
    write_report(processed=processed)

    for src in sources:
        if args.max_items and checked >= args.max_items:
            break

        label = f"{src.part_number} / {src.exact_part_number}"
        if not src.url:
            if args.skip_empty:
                warnings.append(f"{label}: skipped (empty Url)")
                processed += 1
                if args.write_report_every and processed % args.write_report_every == 0:
                    write_report(processed=processed)
                continue
            failures.append(f"{label}: invalid Url ''")
            processed += 1
            if args.write_report_every and processed % args.write_report_every == 0:
                write_report(processed=processed)
            continue

        if not src.url.startswith("http"):
            failures.append(f"{label}: invalid Url '{src.url}'")
            processed += 1
            if args.write_report_every and processed % args.write_report_every == 0:
                write_report(processed=processed)
            continue

        if args.only_ti_symlink and (not _is_ti_symlink_url(src.url)):
            warnings.append(f"{label}: skipped (only-ti-symlink)")
            processed += 1
            if args.write_report_every and processed % args.write_report_every == 0:
                write_report(processed=processed)
            continue

        try:
            probed_url = src.url

            try:
                resp = _probe(probed_url, timeout_s=args.timeout)
            except urllib.error.HTTPError as e:
                # Best-effort healing for TI symlink URLs seeded from orderable part numbers.
                if e.code == 404 and _is_ti_symlink_url(src.url):
                    healed = False
                    for alt in _ti_symlink_fallback_urls(src.url)[1:]:
                        try:
                            resp = _probe(alt, timeout_s=args.timeout)
                            probed_url = alt
                            healed = True
                            break
                        except urllib.error.HTTPError as e2:
                            if e2.code == 404:
                                continue
                            raise
                    if healed:
                        warnings.append(f"{label}: TI symlink healed (ProbedUrl={probed_url})")
                    else:
                        raise
                else:
                    raise

            final_url = getattr(resp, "url", probed_url)
            content_type = resp.headers.get("Content-Type", "")
            content_length = resp.headers.get("Content-Length", "")

            looks_like_pdf_mime = True
            if content_type:
                ct = content_type.lower()
                looks_like_pdf_mime = ("pdf" in ct) or ("octet-stream" in ct)
                if not looks_like_pdf_mime:
                    msg = f"{label}: Content-Type not PDF-ish: '{content_type}'"
                    if args.strict_mime:
                        raise ValueError(msg)
                    warnings.append(msg)

            print(f"OK  {label}")
            print(f"    url:  {final_url}")
            if content_type:
                print(f"    type: {content_type}")
            if content_length:
                print(f"    size: {content_length}")

            item: dict[str, Any] = {
                "PartNumber": src.part_number,
                "ExactPartNumber": src.exact_part_number,
                "Manufacturer": src.manufacturer,
                "DocumentId": src.document_id,
                "Revision": src.revision,
                "Url": src.url,
                "ProbedUrl": probed_url,
                "FinalUrl": final_url,
                "ContentType": content_type,
                "ContentLength": content_length,
                "CheckedAt": now_iso,
                "Downloaded": False,
            }

            if args.download:
                fn = _sanitize_filename(
                    f"{src.exact_part_number}__{src.manufacturer}__{src.document_id}__{src.revision}.pdf"
                )
                dest = download_root / _sanitize_filename(src.manufacturer or "UNKNOWN") / fn
                size, sha256 = _download(final_url, dest, timeout_s=args.timeout, sleep_s=args.sleep)

                # Verify PDF signature for safety/accuracy.
                head = dest.read_bytes()[:8]
                if not _is_pdf_signature(head):
                    raise ValueError(f"Downloaded file is not a PDF (signature={head!r})")

                print(f"    saved: {dest}")
                print(f"    bytes: {size}")
                print(f"    sha256:{sha256}")

                item.update(
                    {
                        "Downloaded": True,
                        "SavedPath": str(dest.relative_to(REPO_ROOT)),
                        "Bytes": size,
                        "Sha256": sha256,
                    }
                )

            report_items.append(item)
            processed += 1
            checked += 1

            if args.write_report_every and processed % args.write_report_every == 0:
                write_report(processed=processed)

            if args.update and raw_for_update is not None:
                # Patch the matching entry in-place.
                for entry in raw_for_update:
                    if not isinstance(entry, dict) or str(entry.get("PartNumber", "")).strip() != src.part_number:
                        continue
                    src_list = entry.get("Sources", [])
                    if not isinstance(src_list, list):
                        continue
                    for s in src_list:
                        if not isinstance(s, dict):
                            continue
                        if str(s.get("ExactPartNumber", "")).strip() != src.exact_part_number:
                            continue

                        if args.heal_ti_symlink_url and probed_url != src.url and _is_ti_symlink_url(src.url):
                            s["Url"] = probed_url

                        s["FinalUrl"] = final_url
                        if content_type:
                            s["ContentType"] = content_type
                        if content_length:
                            s["ContentLength"] = content_length
                        s["CheckedAt"] = now_iso

                        # Keep user's LastAccessed semantics intact; also set it if empty.
                        if not str(s.get("LastAccessed", "")).strip():
                            s["LastAccessed"] = datetime.now().date().isoformat()

                        if args.download:
                            s["Sha256"] = sha256
                            s["Bytes"] = size
                        break
                    break

        except Exception as e:  # noqa: BLE001
            failures.append(f"{label}: {type(e).__name__}: {e}")
            processed += 1
            checked += 1

            if args.write_report_every and processed % args.write_report_every == 0:
                write_report(processed=processed)

    write_report(processed=processed)

    if args.update and raw_for_update is not None:
        _write_json(args.sources, raw_for_update)

    if failures:
        print("=== FAILURES ===")
        for f in failures:
            print(f"- {f}")
        if warnings:
            print("=== WARNINGS ===")
            for w in warnings:
                print(f"- {w}")
        return 1

    if warnings:
        print("=== WARNINGS ===")
        for w in warnings:
            print(f"- {w}")

    print("All sources OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
