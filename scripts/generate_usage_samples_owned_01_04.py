#!/usr/bin/env python3
"""Generate sample-circuit explanation docs for owned parts in categories 01-04.

This script is intentionally conservative:
- It only writes new files by default (no overwrite).
- It only emits datasheet-derived facts that are safe to treat as such (pin names/numbers).
- For anything that cannot be extracted with confidence, it generates a stub with explicit TODOs.

Outputs (per part):
- usage/{category}/{part}/01_basic_function_demo.md

PDF strategy:
- Prefer TI symlink datasheets for owned SN74* parts and download them into .temp/datasheet_fetch/.
- If TI PDF cannot be found, fall back to local PDFs under datasheets/_download (best-effort).

"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Optional

from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parents[1]
OVERVIEW_JSON_PATH = REPO_ROOT / "overview" / "7400_series_ic_overview.json"
HISTORY_JSON_PATH = REPO_ROOT / "getstarting" / "7400_series_ic_collection_acquisition_history.json"
DATASHEET_SOURCES_JSON_PATH = REPO_ROOT / "datasheets" / "datasheet_sources.json"
USAGE_DIR = REPO_ROOT / "usage"
LOCAL_PDF_ROOT = REPO_ROOT / "datasheets" / "_download"
DOWNLOAD_ROOT = REPO_ROOT / ".temp" / "datasheet_fetch" / "generated_samples"

TARGET_CATEGORIES = {
    "01_buffers_inverters",
    "02_nand_and_gates",
    "03_nor_or_gates",
    "04_xor_xnor_gates",
}

TI_SYMLINK_PREFIX = "https://www.ti.com/lit/ds/symlink/"


@dataclass(frozen=True)
class Part:
    part_number: str
    category: str
    description: str
    description_jp: str
    rarity: str


@dataclass(frozen=True)
class OwnedRecord:
    part_number: str
    exact_items: list[str]


@dataclass(frozen=True)
class DatasheetSource:
    part_number: str
    exact_part_number: str
    manufacturer: str
    url: str


@dataclass(frozen=True)
class Pinout:
    pin_count: int
    pin_to_name: dict[int, str]
    extracted_from: str  # path or url label


def _safe_path_label(path: Path) -> str:
    """Return a stable display label for a path.

    Prefer a repo-root-relative path when possible.
    """

    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except Exception:
        try:
            return path.resolve().as_posix()
        except Exception:
            return str(path)


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_text(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def _normalize_token(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", text or "").upper()


def _local_exact_variants(exact_part_number: str, *, max_strips: int = 6) -> list[str]:
    base = _normalize_token(exact_part_number)
    if not base:
        return []

    variants: list[str] = [base]
    cur = base
    strips = 0
    while strips < max_strips and cur and cur[-1].isalpha():
        cur = cur[:-1]
        strips += 1
        if cur and cur not in variants:
            variants.append(cur)

    return variants


def _build_local_pdf_index(root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not root.exists():
        return index

    for pdf in root.rglob("*.pdf"):
        if not pdf.is_file():
            continue

        stem = pdf.stem
        for raw_token in re.split(r"[\s,]+", stem):
            token = _normalize_token(raw_token)
            if token:
                index.setdefault(token, pdf)

    for pdf in root.rglob("*.PDF"):
        if not pdf.is_file():
            continue

        stem = pdf.stem
        for raw_token in re.split(r"[\s,]+", stem):
            token = _normalize_token(raw_token)
            if token:
                index.setdefault(token, pdf)

    return index


def _iter_parts(overview_raw: Any) -> Iterable[Part]:
    if not isinstance(overview_raw, list):
        raise ValueError("overview JSON must be a list")

    for item in overview_raw:
        if not isinstance(item, dict):
            continue

        pn = str(item.get("PartNumber", "")).strip()
        if not pn:
            continue

        category = str(item.get("Category", "99_other")).strip() or "99_other"
        yield Part(
            part_number=pn,
            category=category,
            description=str(item.get("Description", "")).strip(),
            description_jp=str(item.get("Description_JP", "")).strip(),
            rarity=str(item.get("Rarity", "")).strip(),
        )


def _load_owned_records(history_raw: Any) -> dict[str, OwnedRecord]:
    if not isinstance(history_raw, list):
        raise ValueError("history JSON must be a list")

    owned: dict[str, OwnedRecord] = {}
    for item in history_raw:
        if not isinstance(item, dict):
            continue

        pn = str(item.get("PartNumber", "")).strip()
        if not pn:
            continue

        exact_items: list[str] = []
        for key in ("GottenItemsMN_CMOS", "GottenItemsMN_TTL", "GottenItemsMN_Other"):
            value = item.get(key, [])
            if isinstance(value, list):
                exact_items += [str(x).strip() for x in value if str(x).strip()]

        if exact_items:
            owned[pn] = OwnedRecord(part_number=pn, exact_items=exact_items)

    return owned


def _iter_datasheet_sources(raw: Any) -> Iterable[DatasheetSource]:
    if not isinstance(raw, list):
        return

    for entry in raw:
        if not isinstance(entry, dict):
            continue

        pn = str(entry.get("PartNumber", "")).strip()
        sources = entry.get("Sources", [])
        if not pn or not isinstance(sources, list):
            continue

        for s in sources:
            if not isinstance(s, dict):
                continue
            yield DatasheetSource(
                part_number=pn,
                exact_part_number=str(s.get("ExactPartNumber", "")).strip(),
                manufacturer=str(s.get("Manufacturer", "")).strip(),
                url=str(s.get("Url", "")).strip(),
            )


def _is_open_collector(part: Part) -> bool:
    text = f"{part.description} {part.description_jp}".lower()
    return "open-collector" in text or "オープンコレクタ" in text


def _is_tristate(part: Part) -> bool:
    text = f"{part.description} {part.description_jp}".lower()
    return "3-state" in text or "three-state" in text or "トライステート" in text


def _pick_preferred_exact_item(owned: OwnedRecord) -> str:
    """Pick one exact item to anchor a sample.

    Preference:
    - TI SN74* (best for parsable pinouts)
    - Otherwise first item
    """

    for x in owned.exact_items:
        if _normalize_token(x).startswith("SN74"):
            return x
    return owned.exact_items[0]


def _ti_symlink_candidates_from_exact(exact_part_number: str, *, max_strips: int = 6) -> list[str]:
    token = _normalize_token(exact_part_number)
    if not token.startswith("SN"):
        return []

    stem = token.lower()
    candidates: list[str] = []

    def add(st: str) -> None:
        url = f"{TI_SYMLINK_PREFIX}{st}.pdf"
        if url not in candidates:
            candidates.append(url)

    add(stem)

    cur = stem
    strips = 0
    while strips < max_strips and cur and cur[-1].isalpha():
        cur = cur[:-1]
        strips += 1
        add(cur)

    return candidates


def _probe_url_pdf(url: str, *, timeout_s: float) -> bool:
    try:
        req = urllib.request.Request(
            url,
            method="GET",
            headers={"User-Agent": "7400SeriesCollection/1.0", "Range": "bytes=0-4"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            ct = (resp.headers.get("Content-Type", "") or "").lower()
            data = resp.read(5)
            # Accept when server omits content-type; verify signature when possible.
            if ct and ("pdf" not in ct) and ("octet-stream" not in ct):
                return False
            return data.startswith(b"%PDF")
    except Exception:
        return False


def _download_pdf(url: str, dest: Path, *, timeout_s: float, sleep_s: float) -> tuple[int, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        sha256 = hashlib.sha256(dest.read_bytes()).hexdigest()
        return dest.stat().st_size, sha256
    req = urllib.request.Request(url, headers={"User-Agent": "7400SeriesCollection/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = resp.read()
        dest.write_bytes(data)

    if sleep_s > 0:
        time.sleep(sleep_s)

    sha256 = hashlib.sha256(dest.read_bytes()).hexdigest()
    return dest.stat().st_size, sha256


def _find_or_fetch_pdf_for_exact(
    exact_part_number: str,
    local_pdf_index: dict[str, Path],
    *,
    download: bool,
    timeout_s: float,
    sleep_s: float,
) -> tuple[Optional[Path], str, Optional[str], Optional[str]]:
    """Return (pdf_path, source_label, url_used, sha256).

    - Uses local datasheets/_download when available.
    - Otherwise, tries TI symlink candidates for SN*.
    - Downloads into .temp for reproducibility.
    """

    token = _normalize_token(exact_part_number)

    def try_local() -> tuple[Optional[Path], str, Optional[str], Optional[str]]:
        for v in _local_exact_variants(exact_part_number):
            hit = local_pdf_index.get(v)
            if hit is not None and hit.exists():
                sha256_local = hashlib.sha256(hit.read_bytes()).hexdigest()
                return hit, f"local:{_safe_path_label(hit)}", None, sha256_local
        return None, "no-local", None, None

    def try_ti_download() -> tuple[Optional[Path], str, Optional[str], Optional[str]]:
        dest = DOWNLOAD_ROOT / "TI" / f"{token}.pdf"
        sidecar_url = dest.with_suffix(dest.suffix + ".url.txt")

        # If already downloaded, avoid repeated URL probing (network + time).
        # If URL sidecar is missing, optionally probe once to reconstruct it.
        if dest.exists():
            sha256_dl = hashlib.sha256(dest.read_bytes()).hexdigest()

            if sidecar_url.exists():
                url_used = sidecar_url.read_text(encoding="utf-8").strip() or None
                return dest, f"downloaded:{_safe_path_label(dest)}", url_used, sha256_dl

            url_used: Optional[str] = None
            if download:
                candidates = _ti_symlink_candidates_from_exact(exact_part_number)
                for url in candidates:
                    if _probe_url_pdf(url, timeout_s=timeout_s):
                        url_used = url
                        sidecar_url.write_text(url_used, encoding="utf-8", newline="\n")
                        break

            return dest, f"downloaded:{_safe_path_label(dest)}", url_used, sha256_dl

        candidates = _ti_symlink_candidates_from_exact(exact_part_number)
        url_used: Optional[str] = None
        for url in candidates:
            if _probe_url_pdf(url, timeout_s=timeout_s):
                url_used = url
                break
        if not url_used:
            return None, "no-ti-url", None, None
        if not download:
            return None, "url-only", url_used, None
        size, sha256_dl = _download_pdf(url_used, dest, timeout_s=timeout_s, sleep_s=sleep_s)
        _ = size
        sidecar_url.write_text(url_used, encoding="utf-8", newline="\n")
        return dest, f"downloaded:{_safe_path_label(dest)}", url_used, sha256_dl

    # Prefer TI symlink PDFs for SN74* when downloading, because the pin-function tables
    # are reliably extractable compared to some locally archived PDFs.
    if token.startswith("SN"):
        pdf_path, label, url_used, sha256_val = try_ti_download()
        if pdf_path is not None or url_used is not None:
            return pdf_path, label, url_used, sha256_val
        return try_local()

    # Non-TI: prefer local archive.
    local_path, local_label, local_url, local_sha = try_local()
    if local_path is not None:
        return local_path, local_label, local_url, local_sha

    # Non-TI and no local: last resort, try TI rules (usually none).
    pdf_path, label, url_used, sha256_val = try_ti_download()
    if pdf_path is not None or url_used is not None:
        return pdf_path, label, url_used, sha256_val
    return None, "no-pdf", None, None


def _extract_pinout_from_pdf(pdf_path: Path) -> Optional[Pinout]:
    """Best-effort extraction of a pin-to-name map from PDFs.

    Strategy (more conservative than diagram scraping):
    - Prefer parsing "Table ... Pin Functions" style tables when present.
      These list pin numbers explicitly and are far less error-prone than
      parsing the "Functional Pinout" diagram layout.
    """

    try:
        reader = PdfReader(str(pdf_path))
    except Exception:
        return None

    def parse_pin_functions_table(text: str) -> Optional[dict[int, str]]:
        # Tokenize; keep it simple and conservative.
        tokens = text.split()
        # We support multiple TI styles:
        # - "Pin Functions" heading + table
        # - tables that only show headers like "NO. NAME" without the "Pin Functions" heading

        # Find a likely start near "Pin Functions".
        start_idx = None
        for i in range(len(tokens) - 2):
            if tokens[i].lower() == "pin" and tokens[i + 1].lower().startswith("function"):
                start_idx = i
                break
            if tokens[i].lower() == "pin" and tokens[i + 1].lower() == "functions":
                start_idx = i
                break

        if start_idx is None:
            # Some PDFs include "Table x-y. Pin Functions".
            for i in range(len(tokens) - 4):
                if tokens[i].lower().startswith("table") and tokens[i + 1].lower().startswith("pin"):
                    start_idx = i
                    break

        if start_idx is None:
            # Fallback: look for the common header "NO. NAME".
            for i in range(len(tokens) - 1):
                if tokens[i].lower() in {"no.", "no"} and tokens[i + 1].lower() == "name":
                    start_idx = i
                    break

        if start_idx is None:
            return None

        mapping: dict[int, str] = {}

        def normalize_name(raw: str) -> str:
            # Remove common trailing punctuation and footnote markers like "(1)".
            s = (raw or "").strip().strip(",;:.")
            s = re.sub(r"\(\d+\)$", "", s)
            return s

        stop_words = {
            "pin",
            "pins",
            "pin(s)",
            "no.",
            "no",
            "name",
            "i/o",
            "io",
            "description",
        }

        def is_pin_name(tok: str) -> bool:
            name = normalize_name(tok)
            if not name:
                return False
            lower = name.lower()
            if lower in stop_words:
                return False
            upper = name.upper()
            if upper in {"NC", "GND", "VCC", "VDD", "VSS"}:
                return True
            # Reject common prose words to prevent false positives in descriptions.
            # (Most pin names are short and/or all-caps; prose tends to be lowercase.)
            if name.isalpha() and name.islower():
                return False

            # Allow typical formats like 1A, 2Y, /OE, 2G/2G, RESET, CLK, etc.
            if not re.fullmatch(r"[0-9A-Za-z/_-]+", name):
                return False

            # Require at least one letter to avoid confusing with pure numbers.
            if not re.search(r"[A-Za-z]", name):
                return False

            # If alphabetic-only (no digits), require ALL-CAPS (e.g., OE, CLK, RESET).
            # This helps reject tokens like "Channel" that may appear near the table.
            if name.isalpha() and not name.isupper():
                return False

            return True

        # Detect table style.
        # Some TI PDFs (notably LS era) use "NO. NAME" (pin number first),
        # while newer tables often use "NAME ... <pin columns>" (name first).
        table_style_pin_first = False
        for i in range(start_idx, min(start_idx + 60, len(tokens) - 1)):
            if tokens[i].lower() in {"no.", "no"} and tokens[i + 1].lower() == "name":
                table_style_pin_first = True
                break

        for i in range(start_idx, len(tokens) - 1):
            t0 = tokens[i]
            t1 = tokens[i + 1]

            if table_style_pin_first:
                # Prefer <PIN> <NAME>
                if t0.isdigit():
                    pin = int(t0)
                    if 0 < pin <= 64:
                        # Typical: "10 GND" or "2 1A1"
                        if is_pin_name(t1):
                            mapping.setdefault(pin, normalize_name(t1))
                            continue

                        # Some PDFs split digit-prefixed names like "1 OE" -> "1OE".
                        if i + 2 < len(tokens):
                            t2 = tokens[i + 2]
                            if t1.isdigit() and is_pin_name(t2):
                                mapping.setdefault(pin, normalize_name(t1 + normalize_name(t2)))
                continue

            # Prefer <NAME> <PIN>
            if is_pin_name(t0) and t1.isdigit():
                pin = int(t1)
                if 0 < pin <= 64:
                    mapping.setdefault(pin, normalize_name(t0))
                continue

            # Fallback: accept <PIN> <NAME> when not ambiguous.
            if t0.isdigit() and is_pin_name(t1):
                pin = int(t0)
                if 0 < pin <= 64:
                    mapping.setdefault(pin, normalize_name(t1))
                continue

        # Sanity
        if len(mapping) < 8:
            return None

        values = {v.upper() for v in mapping.values()}
        if not ("GND" in values or "VSS" in values):
            return None
        if not ("VCC" in values or "VDD" in values):
            return None

        return mapping

    # Scan first ~12 pages; pin table is usually near the front.
    max_pages = min(12, len(reader.pages))

    for page_index in range(max_pages):
        text = reader.pages[page_index].extract_text() or ""
        if not text:
            continue
        if "Pin" not in text or "Function" not in text:
            continue

        pin_to_name = parse_pin_functions_table(text)
        if pin_to_name is None:
            continue

        pin_count = max(pin_to_name.keys())
        return Pinout(
            pin_count=pin_count,
            pin_to_name=dict(sorted(pin_to_name.items(), key=lambda kv: kv[0])),
            extracted_from=_safe_path_label(pdf_path),
        )

    return None


def _format_pin_table(pinout: Pinout) -> str:
    lines: list[str] = []
    lines.append("| Pin | Name |")
    lines.append("|---:|---|")
    for pin in sorted(pinout.pin_to_name.keys()):
        lines.append(f"| {pin} | {pinout.pin_to_name[pin]} |")
    return "\n".join(lines)


def _render_sample_md(part: Part, *, exact: str, pinout: Optional[Pinout], url_used: Optional[str], sha256: Optional[str]) -> str:
    oc = _is_open_collector(part)
    ts = _is_tristate(part)

    today = date.today().isoformat()

    pin_section = ""
    if pinout is None:
        pin_section = (
            "## ピン配置（要一次資料）\n\n"
            "このパーツは現時点で **自動抽出によるピン配置確定ができませんでした**。\n"
            "実配線に入る前に、対象の実型番・パッケージを確定し、データシートの Pin configuration / Pin functions を参照して追記してください。\n"
        )
    else:
        pin_section = (
            "## ピン配置（抽出）\n\n"
            f"対象の実型番 `{exact}` のデータシートPDFから、ピン名/番号を機械抽出しました（抽出元: `{pinout.extracted_from}`）。\n\n"
            + _format_pin_table(pinout)
            + "\n"
        )

    notes: list[str] = []
    if oc:
        notes.append("- **オープンコレクタ出力**の場合、出力はプルアップ抵抗が必要です（抵抗値・許容電流は一次資料で確認）。")
    if ts:
        notes.append("- **3-state出力**の場合、/OE等の制御ピンを必ず定義してバス衝突を避けてください。")

    notes_md = "\n".join(notes) if notes else "- 特記事項なし（要一次資料で再確認）"

    src_lines: list[str] = []
    src_lines.append(f"- **実型番**: `{exact}`")
    if url_used:
        src_lines.append(f"- **データシートURL**: {url_used}")
    if sha256:
        src_lines.append(f"- **PDF sha256（ローカル）**: `{sha256}`")

    src_md = "\n".join(src_lines)

    return f"""# {part.part_number} 基本動作デモ（1回路）\n\n> この資料はサンプル回路の解説です。**電気特性・最大定格・入力閾値などは必ず一次資料で確認**してください。\n\n## 回路概要\n\n所持している `{part.part_number}` 系ICのうち、`{exact}`（DIP想定）を使って、最小構成で基本動作を確認する回路です。\n\n- スイッチ入力（またはジャンパ）で入力を切り替え\n- LEDで出力を観測\n\n## 回路の仕様\n\n- **電源**: +5V（ロジックファミリにより範囲が異なるため一次資料で確認）\n- **入力**: 手動（DIPスイッチ/タクト）\n- **出力**: LED表示（抵抗を必ず直列に）\n\n## 必要部品リスト\n\n### 汎用ロジックIC\n\n| 汎用型番 | 個数 | 所持品型番（例） |\n|---|---:|---|\n| {part.part_number} | 1 | `{exact}` |\n\n### 受動部品\n\n| 部品 | 目安 | 個数 |\n|---|---:|---:|\n| LED | 任意 | 1 |\n| LED直列抵抗 | 330Ω〜1kΩ | 1 |\n| 入力プルアップ/プルダウン | 10kΩ | 入力数分 |\n| デカップリング | 0.1µF | 1 |\n\n{pin_section}\n\n## 配線の要点\n\n- **VCC/GND**: ピン表で確認した電源ピンに接続。0.1µFをIC直近に配置。\n- **入力**: スイッチでH/Lを切り替え（フローティング禁止）。\n- **出力**: LED＋抵抗で観測（出力ドライブ能力は一次資料で確認）。\n\n### 注意点\n\n{notes_md}\n\n## 一次資料（データシート）\n\n{src_md}\n\n---\n\n生成日時: {today}\n"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate owned sample-circuit docs for categories 01-04")
    parser.add_argument("--force", action="store_true", help="Overwrite existing sample markdown files")
    parser.add_argument("--download", action="store_true", help="Download missing PDFs into .temp for extraction")
    parser.add_argument(
        "--part",
        action="append",
        default=[],
        help="Limit to a specific generic PartNumber (repeatable), e.g. --part 74x240",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--sleep", type=float, default=0.0)

    args = parser.parse_args()

    overview_raw = _read_json(OVERVIEW_JSON_PATH)
    history_raw = _read_json(HISTORY_JSON_PATH)

    parts = {p.part_number: p for p in _iter_parts(overview_raw) if p.category in TARGET_CATEGORIES}
    owned = _load_owned_records(history_raw)

    # Intersect: owned + categories 01-04
    target_part_numbers = sorted([pn for pn in owned.keys() if pn in parts])

    if args.part:
        requested = {str(x).strip() for x in args.part if str(x).strip()}
        target_part_numbers = [pn for pn in target_part_numbers if pn in requested]

    local_pdf_index = _build_local_pdf_index(LOCAL_PDF_ROOT)

    written = 0
    skipped = 0
    stubbed = 0

    for pn in target_part_numbers:
        part = parts[pn]
        owned_rec = owned[pn]

        exact = _pick_preferred_exact_item(owned_rec)

        pdf_path, _src_label, url_used, sha256 = _find_or_fetch_pdf_for_exact(
            exact,
            local_pdf_index,
            download=args.download,
            timeout_s=args.timeout,
            sleep_s=args.sleep,
        )

        pinout: Optional[Pinout] = None
        if pdf_path is not None and pdf_path.exists():
            pinout = _extract_pinout_from_pdf(pdf_path)

        if pinout is None:
            stubbed += 1

        out_dir = USAGE_DIR / part.category / part.part_number
        out_path = out_dir / "01_basic_function_demo.md"

        if _write_text(out_path, _render_sample_md(part, exact=exact, pinout=pinout, url_used=url_used, sha256=sha256), force=args.force):
            written += 1
        else:
            skipped += 1

    print("=== generate_usage_samples_owned_01_04 ===")
    print("targets:", len(target_part_numbers))
    print("written:", written)
    print("skipped:", skipped)
    print("stubbed(pinout-missing):", stubbed)
    print("download:", args.download)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
