#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Seed/expand datasheets/datasheet_sources.json from usage docs and acquisition history.

目的:
- usage/ に書かれた「所持品型番」や、getstarting の入手履歴に出てくる「実型番」を収集し、
  datasheets/datasheet_sources.json に候補エントリを追加する。
- PDFをGit管理外にしても一次資料参照の再現性を保つため、URL/DocID/Rev/参照日を埋める導線を作る。

方針（推測の扱い）:
- メーカー推定は接頭辞ベースで保守的に行う（.github/copilot-instructions.md のルールに合わせる）。
- URLは、確度が高いもの（TIの /lit/ds/symlink/ パターン）だけ自動生成する。
  それ以外は空のまま残し、--skip-empty でのチェック運用を前提とする。
- 自動生成項目には Notes に "AUTO" を付け、後から手で一次資料に照合して修正できるようにする。

使い方:
- まず差分確認（dry-run）:
    python3 scripts/seed_datasheet_sources_from_usage_and_history.py
- 実際に更新:
    python3 scripts/seed_datasheet_sources_from_usage_and_history.py --apply

生成後の検証（URL未入力はスキップ）:
    python3 scripts/check_datasheet_sources.py --skip-empty --report .temp/datasheet_fetch/report.json
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = REPO_ROOT / "datasheets" / "datasheet_sources.json"
ACQ_HISTORY = REPO_ROOT / "getstarting" / "7400_series_ic_collection_acquisition_history.json"
USAGE_DIR = REPO_ROOT / "usage"


TI = "TI(TexasInstruments)"
NXP = "PHILIPS(NXPSemiconductors)"
RENESAS = "RENESAS"
TOSHIBA = "TOSHIBA"
UTC = "UTC(UnisonicTechnologies)"
FAIRCHILD = "FAIRCHILD(FairchildSemiconductor)"
UNKNOWN = "(unknown)"


# 例: SN74HC163N, CD74HC283E, 74HC08AP, SN74LS90N, TC74HC173AF
RE_74_LOGIC = re.compile(r"\b(?:SN|CD|HD|TC|MM|MC|U)?74[A-Z]{0,4}\d{2,3}[A-Z]{0,4}\b")
# 例: K155ID1
RE_K155 = re.compile(r"\bK155[0-9A-Z]+\b")
# 例: К155ИД1 (Cyrillic)
RE_K155_CYR = re.compile(r"\b[Кк]155[А-Яа-я0-9]+\b")


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _pn_sort_key(pn: str) -> Tuple[int, str]:
    # "74x" 以降の数値でソート（失敗時は文字列）
    digits: List[str] = []
    for ch in reversed(pn):
        if ch.isdigit():
            digits.append(ch)
        else:
            break
    if digits:
        try:
            return (int("".join(reversed(digits))), pn)
        except ValueError:
            pass
    return (10**9, pn)


def infer_manufacturer(exact: str) -> str:
    s = exact.strip()

    # 明示的プレフィクス
    if s.startswith("SN74") or s.startswith("CD74"):
        return TI
    if s.startswith("HD74"):
        return RENESAS
    if s.startswith("TC74"):
        return TOSHIBA
    if s.startswith("U74"):
        return UTC
    if s.startswith("MM74") or s.startswith("MC74"):
        return FAIRCHILD

    # プレフィクス無し 74HC*** は PHILIPS(NXP) として扱う（確度は低いので Notes に残す）
    if s.startswith("74HC") or s.startswith("74HCT") or s.startswith("74LS") or s.startswith("74S"):
        return NXP

    # K155 系は例外（ソビエト互換品等）
    if s.startswith("K155") or s.startswith("К155"):
        return UNKNOWN

    return UNKNOWN


def infer_generic_part_number(exact: str, *, context_part_numbers: Optional[List[str]] = None) -> Optional[str]:
    """Try to infer generic PartNumber (74xNN / 74xNNN) from an exact part number.

    Returns None if unknown.
    """

    # First: parse a 74-family number like "74HC163" => 163
    m = re.search(r"74[A-Z]{0,4}(\d{2,3})", exact)
    if m:
        num_str = m.group(1)
        try:
            num = int(num_str)
        except ValueError:
            num = None
        if num is not None:
            if num < 100:
                return f"74x{num:02d}"
            return f"74x{num}"

    # K155ID1 は 74x141 文書でのみ確実に使うなど、文脈から推定
    if context_part_numbers:
        # usage/{category}/74x141/ 配下なら、K155系は 74x141 に寄せる
        if (exact.startswith("K155") or exact.startswith("К155")) and any(pn == "74x141" for pn in context_part_numbers):
            return "74x141"

    return None


def ti_symlink_url(exact: str) -> Optional[str]:
    """Best-effort TI official PDF symlink.

    - Only for SN74*/CD74* prefixed parts.
    - Extract base like "74hc163" and build https://www.ti.com/lit/ds/symlink/sn74hc163.pdf

    Note: URL existence must be checked by scripts/check_datasheet_sources.py.
    """

    if not (exact.startswith("SN74") or exact.startswith("CD74")):
        return None

    lower = exact.lower()
    m = re.search(r"(74[a-z]{1,4}\d{2,3})", lower)
    if not m:
        return None

    base = m.group(1)
    # TI uses sn74* for most logic. For CD74*, symlink is often cd74*; but docs are sometimes under cd74*.
    # Keep the original prefix lowercased (sn74/cd74) to reduce risk.
    prefix = "sn74" if exact.startswith("SN74") else "cd74"

    # base already includes '74...' so join.
    return f"https://www.ti.com/lit/ds/symlink/{prefix}{base[2:]}.pdf"


def extract_exact_parts_from_text(text: str) -> Set[str]:
    parts: Set[str] = set()

    for pat in (RE_74_LOGIC, RE_K155, RE_K155_CYR):
        for m in pat.finditer(text):
            token = m.group(0).strip()
            if token:
                parts.add(token)

    return parts


def extract_from_usage() -> List[Tuple[str, List[str]]]:
    """Return list of (exact_part, context_part_numbers_from_path)."""

    out: List[Tuple[str, List[str]]] = []
    # New layout: usage/{category}/{74xNN}/**.md
    for md in sorted(USAGE_DIR.glob("**/*.md")):
        if not md.is_file():
            continue

        rel = md.relative_to(USAGE_DIR)
        if not rel.parts:
            continue

        # Skip templates and index pages
        if rel.parts[0].startswith("_"):
            continue
        if md.name.lower() == "index.md":
            continue
        if len(rel.parts) < 2:
            # e.g. usage/index.md
            continue

        part_dir = rel.parts[1]  # e.g. "74x141" or "74x181,182"
        if not part_dir.startswith("74x"):
            continue

        context_pns = [p.strip() for p in part_dir.split(",") if p.strip()]

        text = md.read_text(encoding="utf-8")
        for exact in extract_exact_parts_from_text(text):
            out.append((exact, context_pns))

    return out


def extract_from_acquisition_history() -> List[str]:
    raw = _read_json(ACQ_HISTORY)
    if not isinstance(raw, list):
        return []

    out: List[str] = []
    for obj in raw:
        if not isinstance(obj, dict):
            continue

        for key in ("GottenItemsMN_CMOS", "GottenItemsMN_TTL", "GottenItemsMN_Other"):
            arr = obj.get(key, [])
            if not isinstance(arr, list):
                continue
            for v in arr:
                if isinstance(v, str) and v.strip():
                    out.append(v.strip())

    return out


def load_sources(path: Path) -> List[Dict[str, Any]]:
    raw = _read_json(path)
    if not isinstance(raw, list):
        raise ValueError("datasheet_sources.json must be a JSON array")
    return [obj for obj in raw if isinstance(obj, dict)]


def index_existing_exact_parts(sources: List[Dict[str, Any]]) -> Set[str]:
    out: Set[str] = set()
    for entry in sources:
        srcs = entry.get("Sources", [])
        if not isinstance(srcs, list):
            continue
        for s in srcs:
            if not isinstance(s, dict):
                continue
            exact = str(s.get("ExactPartNumber", "")).strip()
            if exact:
                out.add(exact)
    return out


def ensure_part_entry(sources: List[Dict[str, Any]], part_number: str) -> Dict[str, Any]:
    for entry in sources:
        if str(entry.get("PartNumber", "")).strip() == part_number:
            if not isinstance(entry.get("Sources", None), list):
                entry["Sources"] = []
            return entry

    entry = {"PartNumber": part_number, "Sources": []}
    sources.append(entry)
    return entry


def add_source_entry(entry: Dict[str, Any], src_obj: Dict[str, Any]) -> None:
    srcs = entry.get("Sources", [])
    if not isinstance(srcs, list):
        srcs = []
        entry["Sources"] = srcs

    srcs.append(src_obj)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed datasheet_sources.json from usage and acquisition history")
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--apply", action="store_true", help="Write changes to datasheet_sources.json")
    parser.add_argument(
        "--report",
        type=Path,
        default=REPO_ROOT / ".temp" / "datasheet_sources_seed" / "report.json",
        help="Write a JSON report under .temp (default: .temp/datasheet_sources_seed/report.json)",
    )
    parser.add_argument(
        "--no-ti-url",
        action="store_true",
        help="Do not auto-fill TI symlink URL candidates",
    )
    args = parser.parse_args()

    sources = load_sources(args.sources)
    existing_exact = index_existing_exact_parts(sources)

    today = date.today().isoformat()

    usage_pairs = extract_from_usage()
    hist_parts = extract_from_acquisition_history()

    candidates: List[Dict[str, Any]] = []
    added = 0
    skipped_existing = 0
    skipped_unknown = 0

    # Use a stable order: history first, then usage
    work_items: List[Tuple[str, Optional[List[str]], str]] = []
    for exact in hist_parts:
        work_items.append((exact, None, "history"))
    for exact, ctx in usage_pairs:
        work_items.append((exact, ctx, "usage"))

    seen_in_run: Set[str] = set()

    for exact, ctx, origin in work_items:
        if exact in existing_exact:
            skipped_existing += 1
            continue
        if exact in seen_in_run:
            continue
        seen_in_run.add(exact)

        part_number = infer_generic_part_number(exact, context_part_numbers=ctx)
        if not part_number:
            skipped_unknown += 1
            continue

        manufacturer = infer_manufacturer(exact)

        url = ""
        notes_bits: List[str] = [f"AUTO: from {origin}"]
        if manufacturer == NXP and (exact.startswith("74") and not exact.startswith("SN") and not exact.startswith("CD")):
            notes_bits.append("manufacturer is a conservative guess (prefix-less 74**) ")

        if (not args.no_ti_url) and manufacturer == TI:
            url_candidate = ti_symlink_url(exact)
            if url_candidate:
                url = url_candidate
                notes_bits.append("TI symlink URL candidate; validate with check_datasheet_sources.py")

        src_obj: Dict[str, Any] = {
            "ExactPartNumber": exact,
            "Manufacturer": manufacturer,
            "DocumentId": "",
            "Revision": "",
            "Url": url,
            "LastAccessed": today,
            "Notes": "; ".join(notes_bits),
        }

        entry = ensure_part_entry(sources, part_number)
        add_source_entry(entry, src_obj)
        candidates.append({"PartNumber": part_number, **src_obj})
        added += 1

    # Sort for stable diffs
    sources.sort(key=lambda e: _pn_sort_key(str(e.get("PartNumber", ""))))
    for entry in sources:
        srcs = entry.get("Sources", [])
        if isinstance(srcs, list):
            srcs.sort(key=lambda s: str(s.get("ExactPartNumber", "")))

    report = {
        "SourcesFile": str(args.sources.relative_to(REPO_ROOT) if args.sources.is_absolute() else args.sources),
        "Added": added,
        "SkippedExisting": skipped_existing,
        "SkippedUnknown": skipped_unknown,
        "Candidates": candidates,
    }

    _write_json(args.report, report)

    if args.apply:
        _write_json(args.sources, sources)

    print("=== seed_datasheet_sources_from_usage_and_history ===")
    print(f"sources: {args.sources}")
    print(f"added:   {added}{'' if args.apply else ' (dry-run)'}")
    print(f"skipped (existing): {skipped_existing}")
    print(f"skipped (unknown):  {skipped_unknown}")
    print(f"report:  {args.report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
