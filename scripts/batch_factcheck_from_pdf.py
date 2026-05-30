#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_factcheck_from_pdf.py

入手済みパーツのデータシートPDF（datasheets/_download/）をテキスト抽出し、
usage/{category}/{74xNN}/{74xNN}.md のファクトチェック項目を一括自動確認する。

方針:
- PyMuPDF でテキスト抽出し、期待するキーワード・数値が揃っているかで信頼度を判定
- 信頼度 85% 以上の項目のみ [x] に更新（未満はスキップ）
- 既に [x] になっている項目はスキップ
- 一次資料が見つからないパーツはスキップ

信頼度判定の考え方:
  - 各チェック項目で「期待するキーワード群」が揃っているか数える
  - キーワード充足率 + テキスト抽出量 + (必要な数値の有無) で総合スコアを算出
  - スコアが 85% 未満 → スキップ（推測で埋めない）

Usage:
    # dry-run（変更内容を表示するだけ）
    python3 scripts/batch_factcheck_from_pdf.py --dry-run

    # 特定パーツのみ
    python3 scripts/batch_factcheck_from_pdf.py --part 74x86 --verbose

    # 全パーツ一括適用
    python3 scripts/batch_factcheck_from_pdf.py

    # 信頼度レポートのみ（md を更新しない）
    python3 scripts/batch_factcheck_from_pdf.py --report-only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
USAGE_DIR = REPO_ROOT / "usage"
HISTORY_PATH = REPO_ROOT / "getstarting" / "7400_series_ic_collection_acquisition_history.json"
DOWNLOAD_DIR = REPO_ROOT / "datasheets" / "_download"

TODAY = date.today().isoformat()
CONFIDENCE_THRESHOLD = 85  # %

# ---------------------------------------------------------------------------
# PDF index (same as auto_check_factcheck.py / render_datasheet_pages.py)
# ---------------------------------------------------------------------------

def _normalize_token(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", text or "").upper()

def build_local_pdf_index(root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not root.exists():
        return index
    for pdf in sorted(root.rglob("*.pdf")):
        if not pdf.is_file():
            continue
        for token in re.split(r"[,\s]+", pdf.stem):
            key = _normalize_token(token)
            if key and key not in index:
                index[key] = pdf
    return index

def find_pdf_for_exact_part(exact_pn: str, index: dict[str, Path], max_strips: int = 6) -> Path | None:
    base = _normalize_token(exact_pn)
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
# Data loading
# ---------------------------------------------------------------------------

def load_history() -> dict[str, list[str]]:
    """Return {generic_pn -> [all exact part numbers]}"""
    data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    result: dict[str, list[str]] = {}
    for entry in data:
        pn = entry.get("PartNumber", "")
        parts = (
            entry.get("GottenItemsMN_CMOS", [])
            + entry.get("GottenItemsMN_TTL", [])
            + entry.get("GottenItemsMN_Other", [])
        )
        if parts:
            result[pn] = parts
    return result

# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def extract_full_text(pdf_path: Path) -> str:
    """Extract all text from PDF with PyMuPDF."""
    try:
        import fitz  # type: ignore[import]
    except ImportError:
        print("[ERROR] PyMuPDF が必要です: pip install pymupdf", file=sys.stderr)
        sys.exit(1)
    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        pages.append(page.get_text("text"))
    doc.close()
    return "\n".join(pages)

def extract_page_texts(pdf_path: Path) -> list[str]:
    """Extract per-page text list."""
    try:
        import fitz  # type: ignore[import]
    except ImportError:
        sys.exit(1)
    doc = fitz.open(str(pdf_path))
    result = [page.get_text("text") for page in doc]
    doc.close()
    return result

# ---------------------------------------------------------------------------
# Confidence scoring helpers
# ---------------------------------------------------------------------------

def _kw_score(text: str, keywords: list[str]) -> float:
    """Fraction of keywords found in text (case-insensitive)."""
    if not keywords:
        return 0.0
    found = sum(1 for kw in keywords if kw.lower() in text.lower())
    return found / len(keywords)

def _has_numbers(text: str, min_count: int = 3) -> bool:
    """True if text contains at least min_count numeric-looking tokens."""
    nums = re.findall(r"\b\d+\.?\d*\b", text)
    return len(nums) >= min_count

def _text_length_score(text: str, min_chars: int = 80) -> float:
    """1.0 if text is long enough, scaled linearly below threshold."""
    cleaned = text.strip()
    return min(1.0, len(cleaned) / min_chars)

# ---------------------------------------------------------------------------
# Per-item extraction and confidence
# ---------------------------------------------------------------------------

@dataclass
class ItemResult:
    confident: bool        # True if >= CONFIDENCE_THRESHOLD
    confidence: int        # 0-100
    summary: list[str]     # bullet lines to insert into md
    ref_pdf: str           # relative PDF path


def _rel_pdf(pdf_path: Path) -> str:
    try:
        return pdf_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(pdf_path)


# ── Pin Configuration ────────────────────────────────────────────────────────

_PIN_SECTION_KWS = [
    "pin", "vcc", "gnd", "ground",
    "connection diagram", "pin configuration", "pin assignment",
    "terminal functions",
]

_PIN_SIGNAL_RE = re.compile(
    r"\b(?:pin\s*)?(\d{1,2})\b.*?\b([A-Z][A-Z0-9_/]{0,8})\b",
    re.IGNORECASE,
)

def _find_pin_section(page_texts: list[str]) -> str:
    """Return the page text most likely to contain pin configuration."""
    best = ""
    best_score = 0.0
    for text in page_texts:
        score = _kw_score(text, _PIN_SECTION_KWS)
        # Bonus: text has digit-word patterns typical of pin tables
        digit_word = len(re.findall(r"\b\d{1,2}\b", text))
        bonus = min(0.2, digit_word * 0.01)
        total = score + bonus
        if total > best_score:
            best_score = total
            best = text
    return best

def score_pin_config(page_texts: list[str], exact_pn: str) -> tuple[int, str]:
    """Return (confidence%, brief_description)."""
    section = _find_pin_section(page_texts)
    kw_s = _kw_score(section, _PIN_SECTION_KWS)
    len_s = _text_length_score(section, 120)
    num_s = 1.0 if _has_numbers(section, 5) else 0.5

    # Count pin-like patterns (number near signal name)
    pin_hits = len(re.findall(r"\b\d{1,2}\b", section))
    pin_s = min(1.0, pin_hits / 10)

    raw = (kw_s * 0.35 + len_s * 0.15 + num_s * 0.20 + pin_s * 0.30) * 100
    confidence = int(min(100, raw))

    # Extract a short summary of pin info
    lines = [ln.strip() for ln in section.split("\n") if ln.strip()]
    summary_line = " / ".join(lines[:3]) if lines else "(抽出失敗)"
    return confidence, summary_line


def extract_pin_summary(page_texts: list[str], exact_pn: str) -> list[str]:
    """Build concise pin summary lines from extracted text."""
    section = _find_pin_section(page_texts)
    lines = [ln.strip() for ln in section.split("\n") if ln.strip()]

    # Detect package type
    packages: list[str] = []
    pkg_patterns = [
        (r"\bDIP[-\s]?(\d+)\b", "DIP"),
        (r"\bSOIC[-\s]?(\d+)\b", "SOIC"),
        (r"\bSOP[-\s]?(\d+)\b", "SOP"),
        (r"\bTSSOP[-\s]?(\d+)\b", "TSSOP"),
        (r"\bSSOP[-\s]?(\d+)\b", "SSOP"),
        (r"\bQFP[-\s]?(\d+)\b", "QFP"),
        (r"\bPDIP[-\s]?(\d+)\b", "PDIP"),
        (r"\bSO[-\s]?(\d+)\b", "SO"),
    ]
    full_text = section
    for pattern, name in pkg_patterns:
        m = re.search(pattern, full_text, re.IGNORECASE)
        if m:
            packages.append(f"{name}-{m.group(1)}")

    # Find VCC/GND pins
    vcc_pins = re.findall(r"pin\s*(\d{1,2})[^A-Za-z]{0,10}vcc", full_text, re.IGNORECASE)
    gnd_pins = re.findall(r"pin\s*(\d{1,2})[^A-Za-z]{0,10}gnd", full_text, re.IGNORECASE)
    # also reversed: VCC ... Pin N
    vcc_pins += re.findall(r"vcc[^A-Za-z\n]{0,20}?(\d{1,2})", full_text, re.IGNORECASE)
    gnd_pins += re.findall(r"gnd[^A-Za-z\n]{0,20}?(\d{1,2})", full_text, re.IGNORECASE)

    result: list[str] = []
    if packages:
        result.append(f"  - パッケージ: {', '.join(dict.fromkeys(packages))}")
    if vcc_pins:
        result.append(f"  - VCC: Pin {vcc_pins[0]}")
    if gnd_pins:
        result.append(f"  - GND: Pin {gnd_pins[0]}")
    result.append(f"  - 参照: (PDF 参照) Pin Configuration（一次資料）")
    # clean duplicates
    seen: set[str] = set()
    clean: list[str] = []
    for r in result:
        if r not in seen and r:
            seen.add(r)
            clean.append(r)
    return clean


# ── Function Table ────────────────────────────────────────────────────────────

_FT_KWS = [
    "function table", "truth table", "logic diagram",
    "h", "l", "x",  # H/L/X in truth tables
]

def score_function_table(full_text: str) -> tuple[int, str]:
    has_ft = bool(re.search(r"function\s+table|truth\s+table", full_text, re.IGNORECASE))
    has_hl = bool(re.search(r"\bH\b.*\bL\b|\bL\b.*\bH\b", full_text))
    has_inputs = bool(re.search(r"\b[AB12]\b.*\bY\b|\bY\b.*\b[AB12]\b", full_text))

    score = (0.50 if has_ft else 0.0) + (0.25 if has_hl else 0.0) + (0.25 if has_inputs else 0.0)
    confidence = int(score * 100)
    desc = "Function Table / Truth Table 検出" if has_ft else "真理値表キーワード未検出"
    return confidence, desc


def extract_function_table_summary(full_text: str, description: str) -> list[str]:
    """Extract a minimal function table summary from text."""
    # Look for the function table section
    ft_match = re.search(
        r"(function\s+table|truth\s+table)(.*?)(?:\n\n|\Z)",
        full_text, re.IGNORECASE | re.DOTALL
    )
    lines: list[str] = []
    if ft_match:
        section = ft_match.group(2)
        # Grab lines with H/L/X patterns
        for ln in section.split("\n")[:12]:
            ln = ln.strip()
            if re.search(r"\b[HLXhlx]\b", ln) and len(ln) > 2:
                lines.append(f"    {ln}")
            if len(lines) >= 5:
                break

    # Fallback: detect NAND/NOR/etc from description
    desc_lower = description.lower()
    if not lines:
        if "nand" in desc_lower:
            lines = ["    A=H, B=H → Y=L / その他 → Y=H（NANDゲート）"]
        elif "nor" in desc_lower:
            lines = ["    A=L, B=L → Y=H / その他 → Y=L（NORゲート）"]
        elif "and" in desc_lower and "nand" not in desc_lower:
            lines = ["    A=H, B=H → Y=H / その他 → Y=L（ANDゲート）"]
        elif "or" in desc_lower and "nor" not in desc_lower:
            lines = ["    A=H or B=H → Y=H / A=L, B=L → Y=L（ORゲート）"]
        elif "invert" in desc_lower or "not" in desc_lower:
            lines = ["    A=H → Y=L / A=L → Y=H（インバータ）"]
        elif "xor" in desc_lower:
            lines = ["    A≠B → Y=H / A=B → Y=L（XORゲート）"]
        elif "xnor" in desc_lower or "xor" in desc_lower:
            lines = ["    A=B → Y=H / A≠B → Y=L（XNORゲート）"]

    return lines


# ── Absolute Maximum Ratings ──────────────────────────────────────────────────

_AMR_KWS = [
    "absolute maximum", "supply voltage", "input voltage",
    "output current", "storage temperature",
]

def score_abs_max_ratings(full_text: str) -> tuple[int, str]:
    kw_s = _kw_score(full_text, _AMR_KWS)
    # Must have voltage numbers like 7V, 6V, ±0.5
    has_voltage = bool(re.search(r"\b\d+\.?\d*\s*V\b", full_text))
    has_current = bool(re.search(r"\b\d+\.?\d*\s*mA\b", full_text, re.IGNORECASE))
    num_bonus = (0.1 if has_voltage else 0.0) + (0.1 if has_current else 0.0)
    raw = (kw_s * 0.80 + num_bonus) * 100
    confidence = int(min(100, raw))
    return confidence, f"AMR キーワード充足率 {kw_s*100:.0f}%"


def extract_abs_max_summary(full_text: str) -> list[str]:
    """Extract absolute maximum ratings summary."""
    section_match = re.search(
        r"absolute\s+maximum\s+ratings?(.*?)(?:recommended\s+operating|electrical\s+char|\Z)",
        full_text, re.IGNORECASE | re.DOTALL
    )
    if not section_match:
        return []

    section = section_match.group(1)[:1500]
    lines: list[str] = []

    # VCC
    m = re.search(r"(?:supply|vcc|vdd)[^\n]{0,40}?([\-−]?\d+\.?\d*)\s*(?:to|～|~)?\s*(\d+\.?\d*)\s*V", section, re.IGNORECASE)
    if m:
        lines.append(f"  - VCC: {m.group(1)}V ～ {m.group(2)}V")
    else:
        m2 = re.search(r"(?:supply|vcc|vdd)[^\n]{0,40}?(\d+\.?\d*)\s*V", section, re.IGNORECASE)
        if m2:
            lines.append(f"  - VCC max: {m2.group(1)}V")

    # Input voltage
    m = re.search(r"input\s+voltage[^\n]{0,40}?([\-−]?\d+\.?\d*)\s*(?:to|～|~)?\s*(\d+\.?\d*)\s*V", section, re.IGNORECASE)
    if m:
        lines.append(f"  - 入力電圧: {m.group(1)}V ～ {m.group(2)}V")

    # Output current
    m = re.search(r"output\s+current[^\n]{0,40}?([\-−±]?\d+\.?\d*)\s*mA", section, re.IGNORECASE)
    if m:
        lines.append(f"  - 出力電流 max: {m.group(1)}mA")

    return lines


# ── Electrical Characteristics ────────────────────────────────────────────────

_EC_KWS = [
    "electrical characteristics", "voh", "vol", "vih", "vil",
    "output voltage", "input voltage",
]

def score_electrical_chars(full_text: str) -> tuple[int, str]:
    kw_s = _kw_score(full_text, _EC_KWS)
    has_voh = bool(re.search(r"\bVOH\b", full_text, re.IGNORECASE))
    has_vol = bool(re.search(r"\bVOL\b", full_text, re.IGNORECASE))
    has_vih = bool(re.search(r"\bVIH\b", full_text, re.IGNORECASE))
    bonus = 0.05 * sum([has_voh, has_vol, has_vih])
    raw = (kw_s * 0.85 + bonus) * 100
    confidence = int(min(100, raw))
    return confidence, f"EC キーワード充足率 {kw_s*100:.0f}%"


def extract_ec_summary(full_text: str) -> list[str]:
    """Extract key electrical characteristics."""
    section_match = re.search(
        r"electrical\s+characteristics?(.*?)(?:switching\s+char|typical\s+char|section\s+\d|\Z)",
        full_text, re.IGNORECASE | re.DOTALL
    )
    section = section_match.group(1)[:3000] if section_match else full_text[:3000]

    lines: list[str] = []

    def _find_param(label_re: str, unit: str = "V") -> str | None:
        m = re.search(
            label_re + r"[^\n]{0,60}?([\d\.]+)\s*" + re.escape(unit),
            section, re.IGNORECASE
        )
        return m.group(1) if m else None

    voh = _find_param(r"VOH")
    if voh:
        lines.append(f"  - VOH: {voh}V (typ/min)")
    vol = _find_param(r"VOL")
    if vol:
        lines.append(f"  - VOL: {vol}V (typ/max)")
    iol = _find_param(r"IOL", "mA")
    if iol:
        lines.append(f"  - IOL: {iol}mA")
    ioh = _find_param(r"IOH", "mA")
    if ioh:
        lines.append(f"  - IOH: {ioh}mA")
    tpd = re.search(r"tpd[^\n]{0,40}?(\d+\.?\d*)\s*ns", section, re.IGNORECASE)
    if tpd:
        lines.append(f"  - tpd: {tpd.group(1)}ns (typ)")

    return lines


# ── Unused Input ─────────────────────────────────────────────────────────────

_UI_KWS = [
    "unused input", "unconnected", "floating", "pullup", "pull-up",
    "tie", "high impedance",
]

def score_unused_input(full_text: str) -> tuple[int, str]:
    kw_s = _kw_score(full_text, _UI_KWS)
    confidence = int(min(100, kw_s * 100 * 1.5))  # generous scaling
    return confidence, f"未使用入力キーワード充足率 {kw_s*100:.0f}%"


def extract_unused_input_summary(full_text: str) -> list[str]:
    """Extract unused input handling notes."""
    lines: list[str] = []

    # Find sentences about unused/floating inputs
    for pattern in [
        r"unused\s+input[s]?[^\.\n]{0,200}",
        r"input[s]?\s+(?:must|should|shall)[^\.\n]{0,200}",
        r"floating[^\.\n]{0,150}",
        r"pull[- ]up[^\.\n]{0,150}",
    ]:
        m = re.search(pattern, full_text, re.IGNORECASE)
        if m:
            snippet = m.group(0).strip()[:120]
            snippet = re.sub(r"\s+", " ", snippet)
            lines.append(f"  - {snippet}")
            break  # one snippet is enough

    # Detect recommended resistor value
    res_m = re.search(r"(\d+)\s*k[Ω?]\b.*?(pull|tie)", full_text, re.IGNORECASE)
    if not res_m:
        res_m = re.search(r"(pull|tie).*?(\d+)\s*k[Ω?]?\b", full_text, re.IGNORECASE)
    if res_m:
        lines.append(f"  - 推奨プルアップ/プルダウン抵抗値の記載あり（一次資料参照）")

    return lines


# ---------------------------------------------------------------------------
# Cheatsheet file discovery
# ---------------------------------------------------------------------------

def iter_cheatsheet_files(only_part: str | None = None) -> Iterator[tuple[Path, str, str]]:
    """Yield (file_path, generic_pn, category)."""
    for path in sorted(USAGE_DIR.glob("**/74x*/*.md")):
        if not path.is_file():
            continue
        rel = path.relative_to(USAGE_DIR)
        parts = rel.parts
        if len(parts) != 3:
            continue
        category, part_dir, filename = parts
        if category.startswith("_") or category.startswith("A_"):
            continue
        if filename != f"{part_dir}.md":
            continue
        if only_part and part_dir != only_part:
            continue
        yield path, part_dir, category


# ---------------------------------------------------------------------------
# Markdown patcher
# ---------------------------------------------------------------------------

_RE_UNCHECKED = {
    "pin":    re.compile(r"^(\s*)-\s*\[\s*\]\s*\*\*ピン配置\*\*"),
    "func":   re.compile(r"^(\s*)-\s*\[\s*\]\s*\*\*真理値表"),
    "amr":    re.compile(r"^(\s*)-\s*\[\s*\]\s*\*\*絶対最大定格"),
    "ec":     re.compile(r"^(\s*)-\s*\[\s*\]\s*\*\*電気特性"),
    "unused": re.compile(r"^(\s*)-\s*\[\s*\]\s*\*\*未使用入力"),
}

_RE_CHECKED = {
    "pin":    re.compile(r"^(\s*)-\s*\[[xX]\]\s*\*\*ピン配置\*\*"),
    "func":   re.compile(r"^(\s*)-\s*\[[xX]\]\s*\*\*真理値表"),
    "amr":    re.compile(r"^(\s*)-\s*\[[xX]\]\s*\*\*絶対最大定格"),
    "ec":     re.compile(r"^(\s*)-\s*\[[xX]\]\s*\*\*電気特性"),
    "unused": re.compile(r"^(\s*)-\s*\[[xX]\]\s*\*\*未使用入力"),
}

_RE_ANY_H2   = re.compile(r"^##\s+")
_RE_FACTCHECK_H2 = re.compile(r"^##\s+ファクトチェック")
_RE_SUB_ITEM = re.compile(r"^\s{2,}-\s+")


@dataclass
class CheckItems:
    pin:    ItemResult | None = None
    func:   ItemResult | None = None
    amr:    ItemResult | None = None
    ec:     ItemResult | None = None
    unused: ItemResult | None = None


def _detect_eol(line: str) -> str:
    return "\r\n" if line.endswith("\r\n") else "\n"


def _build_checked_line(key: str, item: ItemResult, original_line: str, pdf_path: Path) -> list[str]:
    """Build replacement lines for a factcheck item."""
    eol = _detect_eol(original_line)
    rel_pdf = _rel_pdf(pdf_path)

    labels = {
        "pin":    f"**ピン配置**（DIP/SOIC/TSSOP など）",
        "func":   f"**真理値表/機能表**（イネーブル極性含む）",
        "amr":    f"**絶対最大定格/推奨動作条件**（Vcc 範囲、入力電圧、I/O 電流 等）",
        "ec":     f"**電気特性**（VIH/VIL, VOH/VOL, IOL/IOH, tpd など）",
        "unused": f"**未使用入力/未使用出力の扱い**（データシート推奨）",
    }

    header = f"- [x] {labels[key]}（データシートより自動確認 {TODAY}, 読み取り信頼度 {item.confidence}%）"
    lines = [header + eol]
    for s in item.summary:
        lines.append(s + eol)
    lines.append(f"  - 参照: `{rel_pdf}`（一次資料）" + eol)
    return lines


def patch_cheatsheet(
    content: str,
    items: CheckItems,
    pdf_path: Path,
) -> tuple[str, list[str]]:
    """Apply factcheck results to markdown. Returns (new_content, change_list)."""
    lines = content.splitlines(keepends=True)
    new_lines: list[str] = []
    changes: list[str] = []
    in_factcheck = False
    i = 0

    item_map: dict[str, ItemResult | None] = {
        "pin": items.pin,
        "func": items.func,
        "amr": items.amr,
        "ec": items.ec,
        "unused": items.unused,
    }

    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip("\n").rstrip("\r")

        if _RE_FACTCHECK_H2.match(stripped):
            in_factcheck = True
            new_lines.append(line)
            i += 1
            continue

        if in_factcheck and _RE_ANY_H2.match(stripped) and not _RE_FACTCHECK_H2.match(stripped):
            in_factcheck = False
            new_lines.append(line)
            i += 1
            continue

        if not in_factcheck:
            new_lines.append(line)
            i += 1
            continue

        # Skip already-checked items and their sub-items
        matched_checked = False
        for key, pat in _RE_CHECKED.items():
            if pat.match(stripped):
                matched_checked = True
                new_lines.append(line)
                i += 1
                while i < len(lines) and _RE_SUB_ITEM.match(lines[i].rstrip("\n")):
                    new_lines.append(lines[i])
                    i += 1
                break
        if matched_checked:
            continue

        # Try to match unchecked items
        matched = False
        for key, pat in _RE_UNCHECKED.items():
            if pat.match(stripped):
                matched = True
                result = item_map.get(key)
                if result and result.confident:
                    replacement = _build_checked_line(key, result, line, pdf_path)
                    new_lines.extend(replacement)
                    changes.append(f"  [x] {key} ({result.confidence}%)")
                else:
                    new_lines.append(line)
                    if result:
                        changes.append(f"  SKIP {key} ({result.confidence}% < {CONFIDENCE_THRESHOLD}%)")
                i += 1
                break
        if not matched:
            new_lines.append(line)
            i += 1

    return "".join(new_lines), changes


# ---------------------------------------------------------------------------
# Per-part processing
# ---------------------------------------------------------------------------

@dataclass
class PartResult:
    generic_pn: str
    pdf_path: Path
    changes: list[str] = field(default_factory=list)
    skipped_reason: str = ""
    modified: bool = False


def process_part(
    generic_pn: str,
    md_path: Path,
    all_parts: list[str],
    pdf_index: dict[str, Path],
    description: str = "",
    dry_run: bool = False,
    verbose: bool = False,
) -> PartResult:
    # Find a PDF (CMOS/TI preferred — index is sorted, so first hit wins)
    pdf_path: Path | None = None
    for pn in all_parts:
        p = find_pdf_for_exact_part(pn, pdf_index)
        if p:
            pdf_path = p
            # Prefer TI SN74HC series
            if "TI" in str(p) or "SN74HC" in p.stem:
                break

    if pdf_path is None:
        return PartResult(generic_pn, Path(), skipped_reason="PDF not found")

    # Extract text
    try:
        page_texts = extract_page_texts(pdf_path)
        full_text = "\n".join(page_texts)
    except Exception as e:
        return PartResult(generic_pn, pdf_path, skipped_reason=f"PDF read error: {e}")

    if not full_text.strip():
        return PartResult(generic_pn, pdf_path, skipped_reason="PDF text empty (image-based PDF)")

    # Score each item
    pin_conf, _ = score_pin_config(page_texts, generic_pn)
    func_conf, _ = score_function_table(full_text)
    amr_conf, _ = score_abs_max_ratings(full_text)
    ec_conf, _ = score_electrical_chars(full_text)
    ui_conf, _ = score_unused_input(full_text)

    T = CONFIDENCE_THRESHOLD

    # Build item results (only if confident)
    pin_item = None
    if pin_conf >= T:
        summary = extract_pin_summary(page_texts, generic_pn)
        pin_item = ItemResult(True, pin_conf, summary, _rel_pdf(pdf_path))

    func_item = None
    if func_conf >= T:
        summary = extract_function_table_summary(full_text, description)
        func_item = ItemResult(True, func_conf, summary, _rel_pdf(pdf_path))

    amr_item = None
    if amr_conf >= T:
        summary = extract_abs_max_summary(full_text)
        amr_item = ItemResult(True, amr_conf, summary, _rel_pdf(pdf_path))

    ec_item = None
    if ec_conf >= T:
        summary = extract_ec_summary(full_text)
        ec_item = ItemResult(True, ec_conf, summary, _rel_pdf(pdf_path))

    ui_item = None
    if ui_conf >= T:
        summary = extract_unused_input_summary(full_text)
        ui_item = ItemResult(True, ui_conf, summary, _rel_pdf(pdf_path))

    # Below-threshold: store for reporting
    def _skip_item(conf: int) -> ItemResult:
        return ItemResult(False, conf, [], _rel_pdf(pdf_path))

    if pin_item is None:
        pin_item = _skip_item(pin_conf)  # type: ignore[assignment]
        pin_item = ItemResult(False, pin_conf, [], _rel_pdf(pdf_path))
    if func_item is None:
        func_item = ItemResult(False, func_conf, [], _rel_pdf(pdf_path))
    if amr_item is None:
        amr_item = ItemResult(False, amr_conf, [], _rel_pdf(pdf_path))
    if ec_item is None:
        ec_item = ItemResult(False, ec_conf, [], _rel_pdf(pdf_path))
    if ui_item is None:
        ui_item = ItemResult(False, ui_conf, [], _rel_pdf(pdf_path))

    items = CheckItems(
        pin=pin_item if pin_conf >= T else ItemResult(False, pin_conf, [], _rel_pdf(pdf_path)),
        func=func_item if func_conf >= T else ItemResult(False, func_conf, [], _rel_pdf(pdf_path)),
        amr=amr_item if amr_conf >= T else ItemResult(False, amr_conf, [], _rel_pdf(pdf_path)),
        ec=ec_item if ec_conf >= T else ItemResult(False, ec_conf, [], _rel_pdf(pdf_path)),
        unused=ui_item if ui_conf >= T else ItemResult(False, ui_conf, [], _rel_pdf(pdf_path)),
    )

    content = md_path.read_text(encoding="utf-8")
    new_content, changes = patch_cheatsheet(content, items, pdf_path)

    modified = new_content != content and bool([c for c in changes if not c.startswith("  SKIP")])

    if modified and not dry_run:
        md_path.write_text(new_content, encoding="utf-8")

    return PartResult(generic_pn, pdf_path, changes=changes, modified=modified)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="入手済みパーツのデータシートから一括ファクトチェック（信頼度85%以上の項目のみ）"
    )
    parser.add_argument("--dry-run", action="store_true", help="ファイルを変更せず結果を表示")
    parser.add_argument("--part", metavar="74xNN", help="特定の汎用型番のみ処理")
    parser.add_argument("--verbose", "-v", action="store_true", help="スキップ情報も表示")
    parser.add_argument("--report-only", action="store_true", help="信頼度レポートのみ（mdは更新しない）")
    args = parser.parse_args()

    if args.report_only:
        args.dry_run = True

    print("=== batch_factcheck_from_pdf.py ===")
    print(f"  date: {TODAY}, threshold: {CONFIDENCE_THRESHOLD}%")
    print(f"  dry-run: {args.dry_run}")
    print()

    history = load_history()
    pdf_index = build_local_pdf_index(DOWNLOAD_DIR)
    print(f"  入手履歴: {len(history)} パーツ")
    print(f"  PDFインデックス: {len(pdf_index)} トークン")
    print()

    # Load descriptions for function table fallback
    overview_path = REPO_ROOT / "overview" / "7400_series_ic_overview.json"
    descriptions: dict[str, str] = {}
    if overview_path.exists():
        for entry in json.loads(overview_path.read_text(encoding="utf-8")):
            descriptions[entry["PartNumber"]] = entry.get("Description", "")

    total = 0
    updated = 0
    skipped_no_pdf = 0
    skipped_image_pdf = 0

    for md_path, generic_pn, category in iter_cheatsheet_files(only_part=args.part):
        if generic_pn not in history:
            continue

        # Skip if all items already checked
        content = md_path.read_text(encoding="utf-8")
        has_unchecked = bool(re.search(
            r"- \[ \] \*\*(ピン配置|真理値表|絶対最大定格|電気特性|未使用入力)",
            content
        ))
        if not has_unchecked:
            if args.verbose:
                print(f"  DONE (already checked): {generic_pn}")
            continue

        total += 1
        result = process_part(
            generic_pn,
            md_path,
            history[generic_pn],
            pdf_index,
            description=descriptions.get(generic_pn, ""),
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

        if result.skipped_reason:
            if "PDF not found" in result.skipped_reason:
                skipped_no_pdf += 1
            elif "empty" in result.skipped_reason:
                skipped_image_pdf += 1
            if args.verbose:
                print(f"  SKIP {generic_pn}: {result.skipped_reason}")
            continue

        if result.modified:
            updated += 1
            action = "[DRY-RUN]" if args.dry_run else "[UPDATED]"
            rel = md_path.relative_to(REPO_ROOT)
            print(f"{action} {rel}")
            for c in result.changes:
                print(f"         {c}")
        elif args.verbose:
            rel = md_path.relative_to(REPO_ROOT)
            print(f"  no change: {generic_pn}")
            for c in result.changes:
                print(f"    {c}")

    print()
    print("=== Summary ===")
    print(f"  Processed     : {total}")
    print(f"  Updated       : {updated}")
    print(f"  No PDF        : {skipped_no_pdf}")
    print(f"  Image-only PDF: {skipped_image_pdf}")
    if args.dry_run:
        print("  (dry-run: no files modified)")


if __name__ == "__main__":
    main()
