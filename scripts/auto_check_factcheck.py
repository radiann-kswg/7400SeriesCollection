#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_check_factcheck.py

usage/{category}/{74xNN}/{74xNN}.md のファクトチェックチェックリストを
入手済みデータシート情報から自動確認し、チェックボックスを更新する。

自動確認できる項目 (このスクリプトが更新):
  [x] 対象の実型番を決める  ... 入手履歴 (acquisition_history.json) に実型番があれば
  [x] データシート参照先    ... _download/ に PDF、または datasheet_sources.json に
                               FinalUrl / Url が存在すれば（新規チェックボックスとして追加）

自動確認できない項目 (ユーザーが手動で確認):
  [ ] ピン配置
  [ ] 真理値表/機能表
  [ ] 絶対最大定格/推奨動作条件
  [ ] 電気特性
  [ ] 未使用入力/未使用出力の扱い

Usage:
    # dry-run（変更内容を表示するだけ）
    python3 scripts/auto_check_factcheck.py --dry-run

    # 実際に適用
    python3 scripts/auto_check_factcheck.py

    # 特定の汎用型番のみ
    python3 scripts/auto_check_factcheck.py --part 74x06

    # 詳細ログ
    python3 scripts/auto_check_factcheck.py --verbose
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterator

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
USAGE_DIR = REPO_ROOT / "usage"
HISTORY_PATH = REPO_ROOT / "getstarting" / "7400_series_ic_collection_acquisition_history.json"
SOURCES_PATH = REPO_ROOT / "datasheets" / "datasheet_sources.json"
DOWNLOAD_DIR = REPO_ROOT / "datasheets" / "_download"

TODAY = date.today().isoformat()

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PartInfo:
    cmos: list[str] = field(default_factory=list)
    ttl: list[str] = field(default_factory=list)
    other: list[str] = field(default_factory=list)

    @property
    def all_parts(self) -> list[str]:
        return self.cmos + self.ttl + self.other


@dataclass
class DatasheetRef:
    """A confirmed datasheet reference (local PDF or URL)."""
    label: str       # 表示ラベル
    path_or_url: str # 相対パスまたはURL


# ---------------------------------------------------------------------------
# Local PDF index
# ---------------------------------------------------------------------------

def _normalize_token(text: str) -> str:
    """Remove all non-alphanumeric chars and uppercase."""
    return re.sub(r"[^0-9A-Za-z]", "", text or "").upper()


def build_local_pdf_index(root: Path) -> dict[str, Path]:
    """Recursively index PDF files under root.

    Keys: normalized token strings from filename stems (split by comma/space).
    Values: first PDF path that has that token.
    """
    index: dict[str, Path] = {}
    if not root.exists():
        return index
    for pdf in sorted(root.rglob("*.pdf")):
        if not pdf.is_file():
            continue
        # filenames like "SN74HC06.PDF" or "SN74LS90,SN74LS92,SN74LS93.PDF"
        for token in re.split(r"[,\s]+", pdf.stem):
            key = _normalize_token(token)
            if key and key not in index:
                index[key] = pdf
    return index


def find_pdf_for_exact_part(exact_pn: str, index: dict[str, Path], max_strips: int = 6) -> Path | None:
    """Try exact match first; then progressively strip trailing alpha chars (package suffix)."""
    base = _normalize_token(exact_pn)
    if not base:
        return None
    cur = base
    for _ in range(max_strips + 1):
        if cur in index:
            return index[cur]
        if cur and cur[-1].isalpha():
            cur = cur[:-1]
        else:
            break
    return None


# ---------------------------------------------------------------------------
# JSON loaders
# ---------------------------------------------------------------------------

def load_acquisition_history() -> dict[str, PartInfo]:
    """Return {generic_pn -> PartInfo}."""
    data: list[dict] = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    result: dict[str, PartInfo] = {}
    for entry in data:
        pn = entry.get("PartNumber", "")
        if not pn:
            continue
        result[pn] = PartInfo(
            cmos=entry.get("GottenItemsMN_CMOS", []),
            ttl=entry.get("GottenItemsMN_TTL", []),
            other=entry.get("GottenItemsMN_Other", []),
        )
    return result


def load_confirmed_sources() -> dict[str, list[DatasheetRef]]:
    """Return {generic_pn -> [DatasheetRef]} from datasheet_sources.json.

    Only includes sources with a non-empty URL (FinalUrl preferred).
    """
    data: list[dict] = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    result: dict[str, list[DatasheetRef]] = {}
    for entry in data:
        pn = entry.get("PartNumber", "")
        if not pn:
            continue
        refs: list[DatasheetRef] = []
        for src in entry.get("Sources", []):
            url = (src.get("FinalUrl") or src.get("Url") or "").strip()
            if not url:
                continue
            exact = src.get("ExactPartNumber", "?")
            maker = src.get("Manufacturer", "")
            label = f"{exact} ({maker})" if maker else exact
            refs.append(DatasheetRef(label=label, path_or_url=url))
        if refs:
            result[pn] = refs
    return result


# ---------------------------------------------------------------------------
# Cheatsheet file discovery
# ---------------------------------------------------------------------------

def iter_cheatsheet_files(only_part: str | None = None) -> Iterator[tuple[Path, str]]:
    """Yield (file_path, generic_pn) for each {74xNN}/{74xNN}.md in usage/."""
    for path in sorted(USAGE_DIR.glob("**/74x*/*.md")):
        if not path.is_file():
            continue
        rel = path.relative_to(USAGE_DIR)
        parts = rel.parts
        # Expect: {category}/{74xNN}/{74xNN}.md
        if len(parts) != 3:
            continue
        category, part_dir, filename = parts
        # Skip templates and 'A_combinated_samples'
        if category.startswith("_") or category.startswith("A_"):
            continue
        # Only the "cheatsheet" file: the file named after its parent directory
        if filename != f"{part_dir}.md":
            continue
        generic_pn = part_dir  # e.g. "74x06"
        if only_part and generic_pn != only_part:
            continue
        yield path, generic_pn


# ---------------------------------------------------------------------------
# Markdown patch logic (line-by-line)
# ---------------------------------------------------------------------------

# Matches the FACTCHECK section heading
_RE_SECTION_HEADING = re.compile(r"^##\s+ファクトチェック（一次資料）")

# Matches ANY level-2 heading (end of the factcheck section)
_RE_ANY_H2 = re.compile(r"^##\s+")

# Matches the unchecked "対象の実型番を決める" checkbox (various wording variants)
_RE_UNCHECKED_PARTNUMBER = re.compile(
    r"^(\s*)-\s*\[\s*\]\s*\*\*対象の実型番[^*]*\*\*"
)

# Matches the already-checked version (from a previous auto-check run)
_RE_CHECKED_PARTNUMBER = re.compile(
    r"^(\s*)-\s*\[[xX]\]\s*\*\*対象の実型番[^*]*\*\*"
)

# Matches the auto-inserted "データシート参照先" checkbox (checked)
_RE_DATASHEET_REF = re.compile(
    r"^(\s*)-\s*\[[xX]\]\s*\*\*データシート参照先\*\*"
)

# Sub-item lines (continuation of a previous checked item)
_RE_SUB_ITEM = re.compile(r"^\s{2,}-\s+")


def _build_checked_partnumber_block(part_info: PartInfo) -> list[str]:
    """Build the replacement lines for 対象の実型番を決める (checked)."""
    lines = [f"- [x] **対象の実型番を決める**（入手履歴より自動確認 {TODAY}）"]
    if part_info.cmos:
        cmos_str = ", ".join(f"`{p}`" for p in part_info.cmos)
        lines.append(f"  - CMOS系: {cmos_str}")
    else:
        lines.append("  - CMOS系: （なし）")
    if part_info.ttl:
        ttl_str = ", ".join(f"`{p}`" for p in part_info.ttl)
        lines.append(f"  - TTL系: {ttl_str}")
    else:
        lines.append("  - TTL系: （なし）")
    if part_info.other:
        other_str = ", ".join(f"`{p}`" for p in part_info.other)
        lines.append(f"  - その他: {other_str}")
    return lines


def _build_datasheet_ref_block(pdf_paths: list[Path], url_refs: list[DatasheetRef]) -> list[str]:
    """Build lines for the データシート参照先 (checked) item."""
    lines = [f"- [x] **データシート参照先**（自動確認 {TODAY}）"]
    # Local PDFs (relative to repo root)
    shown_pdfs = 0
    for p in pdf_paths:
        try:
            rel = p.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            rel = str(p)
        lines.append(f"  - PDF: `{rel}`")
        shown_pdfs += 1
        if shown_pdfs >= 3:
            break
    # Confirmed URLs
    shown_urls = 0
    for ref in url_refs:
        lines.append(f"  - URL ({ref.label}): {ref.path_or_url}")
        shown_urls += 1
        if shown_urls >= 3:
            break
    return lines


@dataclass
class PatchResult:
    modified: bool = False
    changes: list[str] = field(default_factory=list)


def patch_markdown_content(
    content: str,
    generic_pn: str,
    part_info: PartInfo | None,
    pdf_paths: list[Path],
    url_refs: list[DatasheetRef],
) -> tuple[str, PatchResult]:
    """Apply factcheck auto-checks to markdown content.

    Returns (new_content, PatchResult).
    """
    result = PatchResult()
    lines = content.splitlines(keepends=True)
    new_lines: list[str] = []

    in_factcheck_section = False
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip("\n").rstrip("\r")

        # Detect section start
        if _RE_SECTION_HEADING.match(stripped):
            in_factcheck_section = True
            new_lines.append(line)
            i += 1
            continue

        # Detect section end (next ## heading)
        if in_factcheck_section and _RE_ANY_H2.match(stripped) and not _RE_SECTION_HEADING.match(stripped):
            in_factcheck_section = False
            new_lines.append(line)
            i += 1
            continue

        if not in_factcheck_section:
            new_lines.append(line)
            i += 1
            continue

        # --- Inside factcheck section ---

        # Already-checked 対象の実型番: skip sub-items and move on
        if _RE_CHECKED_PARTNUMBER.match(stripped):
            new_lines.append(line)
            i += 1
            # Consume existing sub-items
            while i < len(lines) and _RE_SUB_ITEM.match(lines[i].rstrip("\n")):
                new_lines.append(lines[i])
                i += 1

            # Insert データシート参照先 if needed and we have something
            if (pdf_paths or url_refs) and not _datasheet_ref_already_present(lines, i):
                ref_block = _build_datasheet_ref_block(pdf_paths, url_refs)
                eol = _detect_eol(line)
                for ref_line in ref_block:
                    new_lines.append(ref_line + eol)
                result.modified = True
                result.changes.append(
                    f"  [x] データシート参照先追加 "
                    f"({len(pdf_paths)} PDF, {len(url_refs)} URL)"
                )
            continue

        # Unchecked 対象の実型番
        if _RE_UNCHECKED_PARTNUMBER.match(stripped):
            eol = _detect_eol(line)

            if part_info and part_info.all_parts:
                # Replace with checked version + sub-items
                checked_block = _build_checked_partnumber_block(part_info)
                for bl in checked_block:
                    new_lines.append(bl + eol)
                result.modified = True
                pns = part_info.all_parts
                result.changes.append(
                    f"  [x] 対象の実型番を決める → "
                    + ", ".join(pns[:3])
                    + ("..." if len(pns) > 3 else "")
                )
            else:
                # No history data: leave as-is
                new_lines.append(line)

            i += 1

            # Insert データシート参照先 if we have references
            if (pdf_paths or url_refs) and not _datasheet_ref_already_present(lines, i):
                ref_block = _build_datasheet_ref_block(pdf_paths, url_refs)
                for ref_line in ref_block:
                    new_lines.append(ref_line + eol)
                result.modified = True
                result.changes.append(
                    f"  [x] データシート参照先追加 "
                    f"({len(pdf_paths)} PDF, {len(url_refs)} URL)"
                )
            continue

        # Already-present データシート参照先: consume existing sub-items
        if _RE_DATASHEET_REF.match(stripped):
            new_lines.append(line)
            i += 1
            while i < len(lines) and _RE_SUB_ITEM.match(lines[i].rstrip("\n")):
                new_lines.append(lines[i])
                i += 1
            continue

        # Any other line: pass through
        new_lines.append(line)
        i += 1

    new_content = "".join(new_lines)
    if new_content == content:
        result.modified = False
    return new_content, result


def _datasheet_ref_already_present(lines: list[str], from_index: int) -> bool:
    """Check if データシート参照先 already appears after from_index (up to next blank or list-end)."""
    for ln in lines[from_index:]:
        stripped = ln.rstrip("\n").rstrip("\r")
        if _RE_DATASHEET_REF.match(stripped):
            return True
        # Stop looking once we leave the list block (blank line or non-list non-sub-item)
        if stripped == "":
            break
        if not stripped.startswith("-") and not stripped.startswith(" "):
            break
    return False


def _detect_eol(line: str) -> str:
    """Return the line ending (CRLF or LF) of a given line."""
    if line.endswith("\r\n"):
        return "\r\n"
    return "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="usage/ チートシートのファクトチェックを入手済みデータシートから自動確認"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="ファイルを変更せず、変更内容を表示するだけ"
    )
    parser.add_argument(
        "--part", metavar="74xNN",
        help="特定の汎用型番のみを処理（例: 74x06）"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="変更のないファイルも含めて全処理結果を表示"
    )
    args = parser.parse_args()

    print("=== auto_check_factcheck.py ===")
    print(f"  date: {TODAY}")
    print(f"  dry-run: {args.dry_run}")
    if args.part:
        print(f"  target: {args.part}")
    print()

    # Load data
    print("Loading acquisition history ...")
    history = load_acquisition_history()
    print(f"  {len(history)} entries")

    print("Loading confirmed datasheet sources ...")
    confirmed_sources = load_confirmed_sources()
    print(f"  {len(confirmed_sources)} entries with confirmed URL")

    print("Indexing local PDF files ...")
    pdf_index = build_local_pdf_index(DOWNLOAD_DIR)
    print(f"  {len(pdf_index)} PDF tokens indexed")
    print()

    # Process files
    total = 0
    updated = 0
    skipped_no_data = 0

    for path, generic_pn in iter_cheatsheet_files(only_part=args.part):
        total += 1
        part_info = history.get(generic_pn)

        # Collect available PDF paths for this part
        pdf_paths: list[Path] = []
        if part_info:
            seen_pdfs: set[Path] = set()
            for epn in part_info.all_parts:
                found = find_pdf_for_exact_part(epn, pdf_index)
                if found and found not in seen_pdfs:
                    pdf_paths.append(found)
                    seen_pdfs.add(found)

        # Collect confirmed URL references
        url_refs: list[DatasheetRef] = confirmed_sources.get(generic_pn, [])

        has_data = bool(part_info and part_info.all_parts) or bool(pdf_paths) or bool(url_refs)

        if not has_data:
            skipped_no_data += 1
            if args.verbose:
                print(f"  SKIP (no data): {path.relative_to(REPO_ROOT)}")
            continue

        content = path.read_text(encoding="utf-8")
        new_content, patch_result = patch_markdown_content(
            content, generic_pn, part_info, pdf_paths, url_refs
        )

        if patch_result.modified:
            updated += 1
            action = "[DRY-RUN]" if args.dry_run else "[UPDATED]"
            print(f"{action} {path.relative_to(REPO_ROOT)}")
            for change in patch_result.changes:
                print(f"         {change}")
            if not args.dry_run:
                path.write_text(new_content, encoding="utf-8")
        elif args.verbose:
            print(f"  OK (no change): {path.relative_to(REPO_ROOT)}")

    print()
    print("=== Summary ===")
    print(f"  Processed  : {total}")
    print(f"  Updated    : {updated}")
    print(f"  No data    : {skipped_no_data}")
    if args.dry_run:
        print("  (dry-run: no files were modified)")


if __name__ == "__main__":
    main()
