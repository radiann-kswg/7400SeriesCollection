#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_datasheet_pages.py

データシートPDFを画像（PNG）としてレンダリングする。
factcheck-interactive.prompt.md と組み合わせて、
Copilot Agent によるファクトチェック対話フローで使用する。

出力先: .temp/pdf_render/{part_stem}/page_001.png

Usage:
    # 汎用型番で自動検索（入手履歴と _download/ を照合）
    python3 scripts/render_datasheet_pages.py --part 74x00

    # PDFパスを直接指定
    python3 scripts/render_datasheet_pages.py --pdf datasheets/_download/TI(TexasInstruments)/SN74HC/SN74HC00.PDF

    # ページ範囲を指定（省略時=全ページ）
    python3 scripts/render_datasheet_pages.py --part 74x00 --pages 1-6
    python3 scripts/render_datasheet_pages.py --part 74x00 --pages 1,3,5

    # 解像度を指定（省略時=150dpi）
    python3 scripts/render_datasheet_pages.py --part 74x00 --dpi 200

    # 出力先ディレクトリを指定（省略時=.temp/pdf_render/{stem}）
    python3 scripts/render_datasheet_pages.py --part 74x00 --outdir .temp/pdf_render/74x00_SN74HC00

    # データブック（_databooks/）のページ探し（OCR テキスト層を品番で検索。レンダリングはしない）
    python3 scripts/render_datasheet_pages.py --pdf "datasheets/_download/TI(TexasInstruments)/_databooks/1986_TI_The_TTL_Data_Book_Vol_4.pdf" --find SN7489

    # データブック（_databooks/）は PDF ページを指定して該当ページだけ出力する（100 ページ超は --pages 必須）
    python3 scripts/render_datasheet_pages.py --pdf "datasheets/_download/NSC(NationalSemiconductor)/_databooks/1987_ALS_AS_Logic_Databook.pdf" --pages 638-639 --outdir datasheets/.cache/pdf_render/74x1804_databook

Requires: PyMuPDF (pip install pymupdf)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = REPO_ROOT / "getstarting" / "7400_series_ic_collection_acquisition_history.json"
DOWNLOAD_DIR = REPO_ROOT / "datasheets" / "_download"
CACHE_DIR = REPO_ROOT / "datasheets" / ".cache" / "pdf_render"
# これを超えるページ数の PDF（＝データブック）は --pages 必須。個別データシートは多くても数十ページ
MAX_PAGES_WITHOUT_RANGE = 100


# ---------------------------------------------------------------------------
# PDF index helpers (same logic as auto_check_factcheck.py)
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
    # "K155ID1/К155ИД1" のようにラテン表記とキリル表記を "/" で併記した型番は別名ごとに探す
    if "/" in exact_pn:
        for alias in exact_pn.split("/"):
            hit = find_pdf_for_exact_part(alias.strip(), index, max_strips)
            if hit is not None:
                return hit
        return None
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


def find_pdfs_for_generic_pn(generic_pn: str) -> list[Path]:
    """入手履歴から実型番を取得し、対応するPDFを探す。"""
    data: list[dict] = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    all_parts: list[str] = []
    for entry in data:
        if entry.get("PartNumber") == generic_pn:
            all_parts.extend(entry.get("GottenItemsMN_CMOS", []))
            all_parts.extend(entry.get("GottenItemsMN_TTL", []))
            all_parts.extend(entry.get("GottenItemsMN_Other", []))
            break

    if not all_parts:
        print(f"[WARN] {generic_pn} は入手履歴にありません", file=sys.stderr)
        return []

    index = build_local_pdf_index(DOWNLOAD_DIR)
    seen: set[Path] = set()
    results: list[Path] = []
    for pn in all_parts:
        p = find_pdf_for_exact_part(pn, index)
        if p and p not in seen:
            results.append(p)
            seen.add(p)
    return results


# ---------------------------------------------------------------------------
# Page range parser
# ---------------------------------------------------------------------------

def parse_pages(spec: str, total_pages: int) -> list[int]:
    """'1,3,5-8' -> [0,2,4,5,6,7] (0-indexed)"""
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            s = int(start_s.strip()) - 1
            e = int(end_s.strip()) - 1
            pages.extend(range(max(0, s), min(total_pages - 1, e) + 1))
        else:
            p = int(part) - 1
            if 0 <= p < total_pages:
                pages.append(p)
    # deduplicate preserving order
    seen: set[int] = set()
    result: list[int] = []
    for p in pages:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


# ---------------------------------------------------------------------------
# Page search (databooks)
# ---------------------------------------------------------------------------

def find_pages(pdf_path: Path, text: str) -> list[int]:
    """OCR テキスト層から text を含む PDF ページ（1 始まり）を探す。空白と大文字小文字は無視。"""
    import fitz  # type: ignore[import]

    needle = re.sub(r"\s+", "", text).upper()
    with fitz.open(str(pdf_path)) as doc:
        return [i + 1 for i, page in enumerate(doc) if needle in re.sub(r"\s+", "", page.get_text()).upper()]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_pdf(
    pdf_path: Path,
    outdir: Path,
    pages: list[int] | None = None,
    dpi: int = 150,
) -> list[Path]:
    """Render specified pages of a PDF to PNG files.

    Returns list of output PNG paths.
    """
    try:
        import fitz  # type: ignore[import]
    except ImportError:
        print(
            "[ERROR] PyMuPDF が見つかりません。\n"
            "  pip install pymupdf でインストールしてください。",
            file=sys.stderr,
        )
        sys.exit(1)

    doc = fitz.open(str(pdf_path))
    total = len(doc)
    target_pages = pages if pages is not None else list(range(total))

    outdir.mkdir(parents=True, exist_ok=True)
    mat = fitz.Matrix(dpi / 72, dpi / 72)

    rendered: list[Path] = []
    for page_idx in target_pages:
        if page_idx < 0 or page_idx >= total:
            print(f"[WARN] ページ {page_idx + 1} は範囲外です（総ページ: {total}）", file=sys.stderr)
            continue
        page = doc.load_page(page_idx)
        pix = page.get_pixmap(matrix=mat)
        out_path = outdir / f"page_{page_idx + 1:03d}.png"
        pix.save(str(out_path))
        rendered.append(out_path)
        print(f"  Rendered: {out_path.relative_to(REPO_ROOT)}")

    doc.close()
    return rendered


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="データシートPDFをPNG画像としてレンダリングする"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--part", metavar="74xNN",
        help="汎用型番（入手履歴から自動でPDFを特定）"
    )
    group.add_argument(
        "--pdf", metavar="PATH",
        help="PDFファイルパス（リポジトリルートからの相対パスまたは絶対パス）"
    )
    parser.add_argument(
        "--pages", metavar="RANGE",
        help="レンダリングするページ番号（例: 1-6 / 1,3,5 / 省略時=全ページ）"
    )
    parser.add_argument(
        "--dpi", type=int, default=150,
        help="解像度（dpi、省略時=150）"
    )
    parser.add_argument(
        "--outdir", metavar="DIR",
        help="出力先ディレクトリ（省略時は .temp/pdf_render/{stem}）"
    )
    parser.add_argument(
        "--find", metavar="TEXT",
        help="レンダリングせず、TEXT（品番など）を含む PDF ページ番号を OCR テキスト層から探して表示する（データブックのページ探し用）"
    )
    args = parser.parse_args()

    # Resolve PDF path(s)
    if args.pdf:
        pdf_path = Path(args.pdf)
        if not pdf_path.is_absolute():
            pdf_path = REPO_ROOT / pdf_path
        if not pdf_path.exists():
            print(f"[ERROR] PDF が見つかりません: {pdf_path}", file=sys.stderr)
            sys.exit(1)
        pdfs = [pdf_path]
    else:
        pdfs = find_pdfs_for_generic_pn(args.part)
        if not pdfs:
            print(f"[ERROR] {args.part} に対応するPDFが見つかりません", file=sys.stderr)
            sys.exit(1)

    if args.find:
        for pdf_path in pdfs:
            hits = find_pages(pdf_path, args.find)
            try:
                rel = pdf_path.relative_to(REPO_ROOT)
            except ValueError:
                rel = pdf_path
            print(f"{rel}: '{args.find}' を含む PDF ページ = {hits or 'なし'}")
        print("（OCR 由来のため取りこぼし・誤検出がある。該当ページは必ずレンダリングして目視する）")
        return

    all_rendered: list[Path] = []

    for pdf_path in pdfs:
        print(f"\n--- PDF: {pdf_path.relative_to(REPO_ROOT)} ---")

        # Determine output directory
        if args.outdir:
            outdir = Path(args.outdir)
            if not outdir.is_absolute():
                outdir = REPO_ROOT / outdir
        else:
            stem = pdf_path.stem
            if args.part:
                outdir = CACHE_DIR / f"{args.part}_{stem}"
            else:
                outdir = CACHE_DIR / stem

        # Determine page range
        import fitz  # type: ignore[import]
        doc = fitz.open(str(pdf_path))
        total = len(doc)
        doc.close()
        print(f"    総ページ数: {total}")

        if args.pages:
            page_indices = parse_pages(args.pages, total)
        elif total > MAX_PAGES_WITHOUT_RANGE:
            # データブック（数百〜千ページ超）を全ページ PNG 化しないための安全弁
            print(
                f"[ERROR] {total} ページあります。データブック等の大きい PDF は --pages でページを指定してください"
                f"（ページ索引: datasheets/_download/{{メーカー}}/_databooks/README.md）",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            page_indices = list(range(total))

        rendered = render_pdf(pdf_path, outdir, page_indices, dpi=args.dpi)
        all_rendered.extend(rendered)

    print(f"\n=== レンダリング完了 ===")
    print(f"  合計 {len(all_rendered)} ページを出力しました")
    for p in all_rendered:
        try:
            rel = p.relative_to(REPO_ROOT)
        except ValueError:
            rel = p
        print(f"    {rel}")


if __name__ == "__main__":
    main()
