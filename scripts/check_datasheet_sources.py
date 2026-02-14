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
_TI_GPN_PREFIX = "https://www.ti.com/lit/gpn/"
_TI_PRODUCT_PREFIX = "https://www.ti.com/product/"


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


def _normalize_token(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", text or "").upper()


def _local_exact_variants(exact_part_number: str, *, max_strips: int = 6) -> list[str]:
    """Generate conservative variants for matching local PDFs.

    This mirrors the TI symlink idea, but for filenames:
    - Normalize to alnum-only upper.
    - Strip trailing alpha suffixes (package/temperature) a few times.
    """
    base = _normalize_token(exact_part_number)
    if not base:
        return []

    variants: list[str] = []
    cur = base
    variants.append(cur)

    strips = 0
    while strips < max_strips and cur and cur[-1].isalpha():
        cur = cur[:-1]
        strips += 1
        if cur and cur not in variants:
            variants.append(cur)

    return variants


def _build_local_pdf_index(root: Path) -> dict[str, Path]:
    """Index local PDFs by tokens found in the filename.

    - Recursively scans for *.pdf under root.
    - Splits filename stem by commas/whitespace.
    - Stores the first occurrence for each token.
    """
    index: dict[str, Path] = {}

    if not root.exists():
        return index

    for pdf in root.rglob("*.pdf"):
        if not pdf.is_file():
            continue

        stem = pdf.stem
        for raw_token in re.split(r"[\s,]+", stem):
            token = _normalize_token(raw_token)
            if not token:
                continue
            index.setdefault(token, pdf)

    return index


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


def _looks_like_pdf_mime(content_type: str) -> bool:
    if not content_type:
        return True
    ct = content_type.lower()
    return ("pdf" in ct) or ("octet-stream" in ct)


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


def _probe_prefer_pdf(url: str, *, timeout_s: float) -> urllib.response.addinfourl:
    """Probe URL and try to avoid false negatives for PDF detection.

    Some hosts return HTML-ish headers for HEAD but serve PDFs for GET.
    This performs HEAD first, then retries a tiny ranged GET if Content-Type is not PDF-ish.
    """
    resp = _probe(url, timeout_s=timeout_s)
    content_type = resp.headers.get("Content-Type", "")
    if content_type and (not _looks_like_pdf_mime(content_type)):
        # Re-probe with GET (1 byte) to confirm actual content type.
        resp2 = _request_range_probe(url, timeout_s=timeout_s)
        ct2 = resp2.headers.get("Content-Type", "")
        if ct2 and _looks_like_pdf_mime(ct2):
            return resp2
    return resp


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


def _ti_gpn_candidates_from_ti_url(url: str) -> list[str]:
    """Derive TI /lit/gpn/ candidates from a TI symlink URL."""
    if not _is_ti_symlink_url(url):
        return []

    stem = url.rsplit("/", 1)[-1]
    if stem.lower().endswith(".pdf"):
        stem = stem[:-4]

    stem = stem.strip()
    if not stem:
        return []

    return [f"{_TI_GPN_PREFIX}{stem}"]


def _ti_symlink_candidates_from_exact_part_number(exact_part_number: str) -> list[str]:
    """Generate extra TI symlink candidates from an orderable part number.

    Some TI datasheets include a variant letter in the filename (e.g. ...109a.pdf, ...04b.pdf).
    This function conservatively adds those variants when they look plausible.
    """

    epn = re.sub(r"[^0-9A-Za-z]", "", exact_part_number).lower()
    if not epn.startswith("sn"):
        return []

    # Extract a conservative "base" stem (package/temperature suffix removed).
    # Examples:
    # - sn74hc573n  -> base=sn74hc573
    # - sn74als1000an -> base=sn74als1000
    # - sn74s181nc -> base=sn74s181
    m = re.match(r"^(sn\d{2}[a-z]+)(\d{2,4})([a-z].*)?$", epn)
    if not m:
        return []

    prefix, digits, tail = m.group(1), m.group(2), m.group(3) or ""
    base = f"{prefix}{digits}"

    candidates: list[str] = [f"{_TI_SYMLINK_PREFIX}{base}.pdf"]

    # If the first suffix letter is a/b/c, it sometimes appears in the PDF filename.
    letter = tail[:1] if tail else ""
    if letter in {"a", "b", "c"}:
        candidates.append(f"{_TI_SYMLINK_PREFIX}{base}{letter}.pdf")

    # Some families commonly use an 'a' variant in the datasheet filename even when the
    # orderable part suffix is a package letter (e.g. ...N). This stays conservative:
    # it only adds a nearby variant of the same base stem.
    if prefix in {"sn74als", "sn54als", "sn74as", "sn54as", "sn74hc", "sn54hc"}:
        candidates.append(f"{_TI_SYMLINK_PREFIX}{base}a.pdf")

    return candidates


def _ti_symlink_alias_candidates(url: str) -> list[str]:
    """Generate conservative alias candidates for TI symlink URLs.

    This is intentionally small-scope (nearby names only):
    - SN74* and SN54* often share datasheets (try sn54... when sn74... fails).
    - Some legacy stems exist without the family letter (e.g. sn7404.pdf).
      We conservatively try dropping a single 'h' after 'sn74' when present.
    """
    if (not _is_ti_symlink_url(url)) or (not url.lower().endswith(".pdf")):
        return []

    stem = url.rsplit("/", 1)[-1]
    if not stem.lower().endswith(".pdf"):
        return []

    base = stem[:-4].strip().lower()
    if not base:
        return []

    aliases: list[str] = []

    def add(st: str) -> None:
        u = f"{_TI_SYMLINK_PREFIX}{st}.pdf"
        if u not in aliases:
            aliases.append(u)

    # sn74xxxx -> sn54xxxx
    if base.startswith("sn74") and len(base) > 4:
        add("sn54" + base[4:])

    # sn74hNN... -> sn74NN...  (e.g. sn74h04 -> sn7404)
    # Only apply when 'h' is immediately followed by a digit to avoid misfiring on sn74hc/sn74hs/etc.
    if base.startswith("sn74h") and len(base) > 5 and base[5].isdigit():
        add("sn74" + base[5:])

    return aliases


def _request_get_text(url: str, *, timeout_s: float) -> str:
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "7400SeriesCollection/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = resp.read()
    try:
        return data.decode("utf-8")
    except Exception:
        return data.decode("utf-8", errors="ignore")


def _ti_pdf_urls_from_product_page_html(html: str) -> list[str]:
    """Extract TI PDF URLs from product page HTML.

    Note: This is a narrow, best-effort extractor to avoid broad scraping.
    We only look for obvious /lit/...*.pdf links and return unique candidates.
    """
    if not html:
        return []

    candidates: list[str] = []
    seen: set[str] = set()

    patterns = [
        r"https?://www\\.ti\\.com(/lit/(?:ds/symlink|ds)/[^\"\'\s>]+?\\.pdf)",
        r"(/lit/(?:ds/symlink|ds)/[^\"\'\s>]+?\\.pdf)",
        r"https?://www\\.ti\\.com(/lit/pdf/[^\"\'\s>]+?\\.pdf)",
        r"(/lit/pdf/[^\"\'\s>]+?\\.pdf)",
    ]

    for pat in patterns:
        for m in re.finditer(pat, html, flags=re.IGNORECASE):
            path = m.group(1)
            if not path:
                continue
            url = path
            if url.startswith("/"):
                url = "https://www.ti.com" + url
            if url not in seen:
                seen.add(url)
                candidates.append(url)

    return candidates


def _ti_product_page_url_from_exact_part_number(exact_part_number: str) -> str | None:
    """Derive a TI product page URL from an orderable part number.

    Example: SN74HC573NSR -> https://www.ti.com/product/SN74HC573
    """
    epn = re.sub(r"[^0-9A-Za-z]", "", exact_part_number).upper()
    if not epn.startswith("SN"):
        return None

    m = re.match(r"^(SN\d{2}[A-Z]+)(\d{2,4})", epn)
    if not m:
        return None

    base = f"{m.group(1)}{m.group(2)}"
    return f"https://www.ti.com/product/{base}"


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
        "--only-fails-from-report",
        type=Path,
        default=None,
        help=(
            "Limit checks to sources whose ExactPartNumber appears as Result=FAIL in the given report JSON. "
            "Useful to iterate on fallback rules without re-checking everything."
        ),
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
        "--ti-fallback-gpn",
        action="store_true",
        help=(
            "When checking TI symlink URLs, also try https://www.ti.com/lit/gpn/<stem> as a conservative fallback "
            "(validated by Content-Type and optional PDF signature when downloading)."
        ),
    )
    parser.add_argument(
        "--ti-check-product-page",
        action="store_true",
        help=(
            "For TI sources, also check whether https://www.ti.com/product/<base> exists and include the HTTP status "
            "in FAIL report items. This helps decide next manual/semiauto steps."
        ),
    )
    parser.add_argument(
        "--ti-product-page-datasheet",
        action="store_true",
        help=(
            "If a TI source fails and https://www.ti.com/product/<base> exists, fetch the product page HTML and "
            "try any obvious /lit/...*.pdf links found there as additional conservative candidates."
        ),
    )
    parser.add_argument(
        "--write-report-every",
        type=int,
        default=25,
        help="Write intermediate report JSON every N processed records (0 = only write at end).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce console output (do not print each OK item). Useful for long runs.",
    )
    parser.add_argument(
        "--local-pdf-root",
        type=Path,
        default=None,
        help=(
            "Optional: root folder to search for already-downloaded PDFs (e.g. datasheets/_download). "
            "When enabled together with --allow-local-as-ok, a matching local PDF can satisfy a source even if Url is empty or fails."
        ),
    )
    parser.add_argument(
        "--allow-local-as-ok",
        action="store_true",
        help=(
            "If enabled and --local-pdf-root is set, treat a matching local PDF as OK when Url is empty or URL probing fails. "
            "This is intended for non-TI makers where official URL patterns are not safely auto-derivable."
        ),
    )

    args = parser.parse_args()

    if not args.sources.exists():
        print(f"ERROR: sources file not found: {args.sources}")
        print("Hint: create datasheets/datasheet_sources.json (see datasheets/datasheet_sources.example.json)")
        return 2

    raw = _read_json(args.sources)
    sources = list(_iter_sources(raw))

    local_pdf_index: dict[str, Path] = {}
    if args.local_pdf_root is not None:
        # Build once; index keys are normalized tokens.
        local_pdf_index = _build_local_pdf_index(args.local_pdf_root)
        if not args.quiet:
            print(f"localPdfRoot: {args.local_pdf_root}")
            print(f"localPdfIndexSize: {len(local_pdf_index)}")

    # Reduce work early when caller is intentionally narrowing scope.
    if args.skip_empty:
        sources = [s for s in sources if s.url]
    if args.only_ti_symlink:
        sources = [s for s in sources if _is_ti_symlink_url(s.url)]

    if args.only_fails_from_report is not None:
        if not args.only_fails_from_report.exists():
            print(f"ERROR: --only-fails-from-report not found: {args.only_fails_from_report}")
            return 2
        try:
            report_raw = _read_json(args.only_fails_from_report)
            items = report_raw.get("Items", []) if isinstance(report_raw, dict) else []
            fail_epns = {
                str(it.get("ExactPartNumber", "")).strip()
                for it in items
                if isinstance(it, dict) and str(it.get("Result", "")).strip().upper() == "FAIL"
            }
            fail_epns.discard("")
        except Exception as e:  # noqa: BLE001
            print(f"ERROR: failed to read --only-fails-from-report: {args.only_fails_from_report}: {e}")
            return 2

        if fail_epns:
            sources = [s for s in sources if s.exact_part_number in fail_epns]

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
        ok_count = sum(1 for it in report_items if it.get("Result") == "OK")
        fail_count = sum(1 for it in report_items if it.get("Result") == "FAIL")
        skip_count = sum(1 for it in report_items if it.get("Result") == "SKIP")
        report_obj = {
            "CheckedAt": now_iso,
            "SourcesFile": str(args.sources.relative_to(REPO_ROOT) if args.sources.is_absolute() else args.sources),
            "Count": len(report_items),
            "OkCount": ok_count,
            "FailCount": fail_count,
            "SkipCount": skip_count,
            "Processed": processed,
            "Total": len(sources),
            "Download": args.download,
            "Items": report_items,
            "Warnings": warnings,
            "Failures": failures,
        }
        _write_json(args.report, report_obj)

    processed = 0

    # Write an initial report so callers can see progress even if interrupted.
    write_report(processed=processed)

    for src in sources:
        if args.max_items and processed >= args.max_items:
            break

        label = f"{src.part_number} / {src.exact_part_number}"

        base_item: dict[str, Any] = {
            "PartNumber": src.part_number,
            "ExactPartNumber": src.exact_part_number,
            "Manufacturer": src.manufacturer,
            "DocumentId": src.document_id,
            "Revision": src.revision,
            "Url": src.url,
            "CheckedAt": now_iso,
            "Downloaded": False,
        }

        # Best-effort local PDF lookup (used only when enabled).
        local_pdf: Path | None = None
        if local_pdf_index and src.exact_part_number:
            for v in _local_exact_variants(src.exact_part_number):
                hit = local_pdf_index.get(v)
                if hit is not None:
                    local_pdf = hit
                    break

        if not src.url:
            if args.allow_local_as_ok and local_pdf is not None:
                size = local_pdf.stat().st_size
                sha256 = hashlib.sha256(local_pdf.read_bytes()).hexdigest()
                report_items.append(
                    {
                        **base_item,
                        "Result": "OK",
                        "LocalPdfUsed": True,
                        "LocalPdfPath": str(local_pdf.relative_to(REPO_ROOT) if local_pdf.is_absolute() else local_pdf),
                        "Bytes": size,
                        "Sha256": sha256,
                        "ContentType": "application/pdf",
                        "ContentLength": str(size),
                        "FinalUrl": "(local)",
                    }
                )
                processed += 1
                if args.write_report_every and processed % args.write_report_every == 0:
                    write_report(processed=processed)
                if args.update and raw_for_update is not None:
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
                            s["LocalPath"] = str(
                                local_pdf.relative_to(REPO_ROOT) if local_pdf.is_absolute() else local_pdf
                            )
                            s["LocalBytes"] = size
                            s["LocalSha256"] = sha256
                            s["LocalCheckedAt"] = now_iso
                            if not str(s.get("LastAccessed", "")).strip():
                                s["LastAccessed"] = datetime.now().date().isoformat()
                            break
                        break
                continue

            if args.skip_empty:
                warnings.append(f"{label}: skipped (empty Url)")
                report_items.append({**base_item, "Result": "SKIP", "SkipReason": "empty Url"})
                processed += 1
                if args.write_report_every and processed % args.write_report_every == 0:
                    write_report(processed=processed)
                continue

            failures.append(f"{label}: invalid Url ''")
            report_items.append({**base_item, "Result": "FAIL", "ErrorType": "ValueError", "Error": "invalid Url ''"})
            processed += 1
            if args.write_report_every and processed % args.write_report_every == 0:
                write_report(processed=processed)
            continue

        if not src.url.startswith("http"):
            failures.append(f"{label}: invalid Url '{src.url}'")
            report_items.append(
                {
                    **base_item,
                    "Result": "FAIL",
                    "ErrorType": "ValueError",
                    "Error": f"invalid Url '{src.url}'",
                }
            )
            processed += 1
            if args.write_report_every and processed % args.write_report_every == 0:
                write_report(processed=processed)
            continue

        if args.only_ti_symlink and (not _is_ti_symlink_url(src.url)):
            warnings.append(f"{label}: skipped (only-ti-symlink)")
            report_items.append({**base_item, "Result": "SKIP", "SkipReason": "only-ti-symlink"})
            processed += 1
            if args.write_report_every and processed % args.write_report_every == 0:
                write_report(processed=processed)
            continue

        try:
            attempted_urls: list[str] = []
            probed_url = src.url

            candidates: list[str] = [src.url]

            # Best-effort healing for TI symlink URLs seeded from orderable part numbers.
            if _is_ti_symlink_url(src.url):
                candidates.extend(_ti_symlink_fallback_urls(src.url)[1:])
                candidates.extend(_ti_symlink_candidates_from_exact_part_number(src.exact_part_number))
                for u in list(candidates):
                    candidates.extend(_ti_symlink_alias_candidates(u))
                if args.ti_fallback_gpn:
                    for u in list(candidates):
                        candidates.extend(_ti_gpn_candidates_from_ti_url(u))

            # De-duplicate while preserving order.
            seen: set[str] = set()
            candidates = [u for u in candidates if not (u in seen or seen.add(u))]

            last_error: Exception | None = None
            resp: urllib.response.addinfourl | None = None

            for cand in candidates:
                attempted_urls.append(cand)
                try:
                    if args.strict_mime:
                        resp = _probe_prefer_pdf(cand, timeout_s=args.timeout)
                    else:
                        resp = _probe(cand, timeout_s=args.timeout)

                    final_url = getattr(resp, "url", cand)
                    content_type = resp.headers.get("Content-Type", "")
                    content_length = resp.headers.get("Content-Length", "")

                    if args.strict_mime and content_type and (not _looks_like_pdf_mime(content_type)):
                        raise ValueError(f"{label}: Content-Type not PDF-ish: '{content_type}'")

                    probed_url = cand
                    break
                except Exception as e:  # noqa: BLE001
                    last_error = e
                    resp = None
                    continue

            if resp is None and args.ti_product_page_datasheet and _is_ti_symlink_url(src.url):
                product_url = _ti_product_page_url_from_exact_part_number(src.exact_part_number)
                if product_url:
                    try:
                        _probe(product_url, timeout_s=args.timeout)
                        html = _request_get_text(product_url, timeout_s=args.timeout)
                        pdf_urls = _ti_pdf_urls_from_product_page_html(html)
                        for pdf_url in pdf_urls:
                            attempted_urls.append(pdf_url)
                            try:
                                if args.strict_mime:
                                    resp = _probe_prefer_pdf(pdf_url, timeout_s=args.timeout)
                                else:
                                    resp = _probe(pdf_url, timeout_s=args.timeout)
                                probed_url = pdf_url
                                break
                            except Exception as e:  # noqa: BLE001
                                last_error = e
                                resp = None
                                continue
                    except Exception as e:  # noqa: BLE001
                        last_error = e
                        resp = None

            if resp is None:
                assert last_error is not None
                raise last_error

            final_url = getattr(resp, "url", probed_url)
            content_type = resp.headers.get("Content-Type", "")
            content_length = resp.headers.get("Content-Length", "")

            if content_type and (not _looks_like_pdf_mime(content_type)):
                msg = f"{label}: Content-Type not PDF-ish: '{content_type}'"
                if args.strict_mime:
                    raise ValueError(msg)
                warnings.append(msg)

            if not args.quiet:
                print(f"OK  {label}")
                print(f"    url:  {final_url}")
                if content_type:
                    print(f"    type: {content_type}")
                if content_length:
                    print(f"    size: {content_length}")

            item: dict[str, Any] = {
                **base_item,
                "Result": "OK",
                "AttemptedUrls": attempted_urls,
                "ProbedUrl": probed_url,
                "FinalUrl": final_url,
                "ContentType": content_type,
                "ContentLength": content_length,
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

                if not args.quiet:
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
                            # Rewrite the seed TI URL to the working variant (symlink stem fix or gpn).
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
            # If URL probing failed, allow local PDF fallback when configured.
            if args.allow_local_as_ok and local_pdf is not None:
                size = local_pdf.stat().st_size
                sha256 = hashlib.sha256(local_pdf.read_bytes()).hexdigest()
                item = {
                    **base_item,
                    "Result": "OK",
                    "LocalPdfUsed": True,
                    "LocalPdfPath": str(local_pdf.relative_to(REPO_ROOT) if local_pdf.is_absolute() else local_pdf),
                    "Bytes": size,
                    "Sha256": sha256,
                    "ContentType": "application/pdf",
                    "ContentLength": str(size),
                    "FinalUrl": "(local)",
                    "UrlProbeFailed": True,
                    "UrlProbeErrorType": type(e).__name__,
                    "UrlProbeError": str(e),
                }
                report_items.append(item)
                processed += 1
                if args.write_report_every and processed % args.write_report_every == 0:
                    write_report(processed=processed)
                if args.update and raw_for_update is not None:
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
                            s["LocalPath"] = str(
                                local_pdf.relative_to(REPO_ROOT) if local_pdf.is_absolute() else local_pdf
                            )
                            s["LocalBytes"] = size
                            s["LocalSha256"] = sha256
                            s["LocalCheckedAt"] = now_iso
                            if not str(s.get("LastAccessed", "")).strip():
                                s["LastAccessed"] = datetime.now().date().isoformat()
                            break
                        break
                continue

            failure_msg = f"{label}: {type(e).__name__}: {e}"
            failures.append(failure_msg)

            failure_item: dict[str, Any] = {
                **base_item,
                "Result": "FAIL",
                "AttemptedUrls": attempted_urls,
                "ErrorType": type(e).__name__,
                "Error": str(e),
            }

            if args.ti_check_product_page and _is_ti_symlink_url(src.url):
                product_url = _ti_product_page_url_from_exact_part_number(src.exact_part_number)
                if product_url:
                    failure_item["TiProductUrl"] = product_url
                    try:
                        _probe(product_url, timeout_s=args.timeout)
                        failure_item["TiProductHttpStatus"] = 200
                    except urllib.error.HTTPError as pe:
                        failure_item["TiProductHttpStatus"] = pe.code
                    except Exception:
                        failure_item["TiProductHttpStatus"] = "(error)"

            if isinstance(e, urllib.error.HTTPError):
                failure_item["HttpStatus"] = e.code
                ct = e.headers.get("Content-Type", "") if e.headers else ""
                if ct:
                    failure_item["ContentType"] = ct

            report_items.append(failure_item)
            processed += 1

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
