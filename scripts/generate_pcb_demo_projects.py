#!/usr/bin/env python3
"""
generate_pcb_demo_projects.py

入手済み 7400 シリーズ IC について、KiCAD デモ PCB プロジェクトのスタブを生成します。

使用方法:
  python3 scripts/generate_pcb_demo_projects.py                   # dry-run（変更なし・一覧表示）
  python3 scripts/generate_pcb_demo_projects.py --apply           # 実際に生成
  python3 scripts/generate_pcb_demo_projects.py --apply --overwrite  # 既存も上書き
  python3 scripts/generate_pcb_demo_projects.py --category 01_buffers_inverters  # カテゴリ絞り込み
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# ============================================================
# パス設定
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = BASE_DIR / "pcb-demo" / "_templates"
PCB_DEMO_DIR = BASE_DIR / "pcb-demo"
OVERVIEW_JSON = BASE_DIR / "overview" / "7400_series_ic_overview.json"
HISTORY_JSON = BASE_DIR / "getstarting" / "7400_series_ic_collection_acquisition_history.json"

TEMPLATE_FILES = [
    "template.kicad_pro",
    "template.kicad_sch",
    "template.kicad_pcb",
    "template.kicad_sym",
    "README_template.md",
]

TODAY = date.today().strftime("%Y-%m-%d")


# ============================================================
# ユーティリティ
# ============================================================

def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt_parts(parts: list) -> str:
    if not parts:
        return "(なし)"
    return ", ".join(parts)


def make_replacements(
    part_number: str,
    description: str,
    description_jp: str,
    category: str,
    cmos_parts: list,
    ttl_parts: list,
    other_parts: list,
) -> dict:
    all_owned = cmos_parts + ttl_parts + other_parts
    return {
        "{{PART_NUMBER}}": part_number,
        "{{DESCRIPTION}}": description,
        "{{DESCRIPTION_JP}}": description_jp,
        "{{CATEGORY}}": category,
        "{{CMOS_PARTS}}": fmt_parts(cmos_parts),
        "{{TTL_PARTS}}": fmt_parts(ttl_parts),
        "{{OTHER_PARTS}}": fmt_parts(other_parts),
        "{{ALL_OWNED_PARTS}}": fmt_parts(all_owned),
        "{{DATE}}": TODAY,
    }


def apply_replacements(text: str, replacements: dict) -> str:
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text


def template_to_output_name(template_filename: str, part_number: str) -> str:
    """
    template.kicad_pro  -> {part_number}.kicad_pro
    README_template.md  -> README.md
    """
    if template_filename == "README_template.md":
        return "README.md"
    # "template." プレフィックスを part_number に置換
    suffix = template_filename[len("template."):]
    return f"{part_number}.{suffix}"


# ============================================================
# プロジェクト生成
# ============================================================

def generate_project(
    entry: dict,
    overview_map: dict,
    dry_run: bool,
    overwrite: bool,
    stats: dict,
) -> None:
    part_number = entry["PartNumber"]
    cmos_parts = entry.get("GottenItemsMN_CMOS", [])
    ttl_parts = entry.get("GottenItemsMN_TTL", [])
    other_parts = entry.get("GottenItemsMN_Other", [])

    # 未入手はスキップ
    if not cmos_parts and not ttl_parts and not other_parts:
        stats["skipped_not_owned"] += 1
        return

    ov = overview_map.get(part_number, {})
    description = ov.get("Description", "(No description)")
    description_jp = ov.get("Description_JP", "(説明なし)")
    category = ov.get("Category", "99_other")

    project_dir = PCB_DEMO_DIR / category / part_number
    replacements = make_replacements(
        part_number, description, description_jp, category,
        cmos_parts, ttl_parts, other_parts,
    )

    for tmpl_name in TEMPLATE_FILES:
        tmpl_path = TEMPLATES_DIR / tmpl_name
        if not tmpl_path.exists():
            print(f"  [WARN] テンプレート不在: {tmpl_path}")
            continue

        out_name = template_to_output_name(tmpl_name, part_number)
        out_path = project_dir / out_name

        if out_path.exists() and not overwrite:
            stats["skipped_existing"] += 1
            continue

        action = "上書き" if out_path.exists() else "新規"
        if dry_run:
            rel = out_path.relative_to(BASE_DIR)
            print(f"  [DRY-RUN] {action}: {rel}")
            stats["would_create"] += 1
        else:
            project_dir.mkdir(parents=True, exist_ok=True)
            content = tmpl_path.read_text(encoding="utf-8")
            content = apply_replacements(content, replacements)
            out_path.write_text(content, encoding="utf-8")
            rel = out_path.relative_to(BASE_DIR)
            print(f"  [{action}] {rel}")
            stats["created"] += 1


# ============================================================
# インデックス生成
# ============================================================

def generate_category_index(
    category: str,
    parts_in_category: list,
    dry_run: bool,
) -> None:
    index_path = PCB_DEMO_DIR / category / "index.md"
    lines = [
        f"# {category} — PCB Demo Index\n",
        "\n",
        "| 汎用型番 | 機能 (EN) | 機能 (JP) |\n",
        "|---------|-----------|----------|\n",
    ]
    for p in sorted(parts_in_category, key=lambda x: x["PartNumber"]):
        pn = p["PartNumber"]
        desc = p.get("Description", "")
        desc_jp = p.get("Description_JP", "")
        lines.append(f"| [{pn}]({pn}/README.md) | {desc} | {desc_jp} |\n")

    content = "".join(lines)
    if dry_run:
        rel = index_path.relative_to(BASE_DIR)
        print(f"  [DRY-RUN] カテゴリindex: {rel}")
    else:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(content, encoding="utf-8")
        rel = index_path.relative_to(BASE_DIR)
        print(f"  [index] {rel}")


def generate_top_index(
    history: list,
    overview_map: dict,
    dry_run: bool,
) -> None:
    index_path = PCB_DEMO_DIR / "index.md"

    # カテゴリ別に集計
    by_cat: dict = {}
    for entry in history:
        pn = entry["PartNumber"]
        if not (
            entry.get("GottenItemsMN_CMOS")
            or entry.get("GottenItemsMN_TTL")
            or entry.get("GottenItemsMN_Other")
        ):
            continue
        ov = overview_map.get(pn, {})
        cat = ov.get("Category", "99_other")
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append({"PartNumber": pn, **ov})

    total = sum(len(v) for v in by_cat.values())
    lines = [
        "# PCB Demo Projects — Index\n\n",
        "入手済み 7400 シリーズ IC のデモ PCB プロジェクト一覧。\n\n",
        f"- 生成日: {TODAY}\n",
        f"- 対象 IC 数: {total}\n",
        f"- カテゴリ数: {len(by_cat)}\n\n",
        "## カテゴリ一覧\n\n",
        "| カテゴリ | 件数 |\n",
        "|---------|------|\n",
    ]
    for cat in sorted(by_cat.keys()):
        lines.append(f"| [{cat}]({cat}/index.md) | {len(by_cat[cat])} |\n")

    lines.append("\n")
    for cat in sorted(by_cat.keys()):
        parts = by_cat[cat]
        lines.append(f"## [{cat}]({cat}/index.md)  ({len(parts)} 件)\n\n")
        lines.append("| 汎用型番 | 機能 (EN) |\n")
        lines.append("|---------|----------|\n")
        for p in sorted(parts, key=lambda x: x["PartNumber"]):
            pn = p["PartNumber"]
            desc = p.get("Description", "")
            lines.append(f"| [{pn}]({cat}/{pn}/README.md) | {desc} |\n")
        lines.append("\n")

    content = "".join(lines)
    if dry_run:
        rel = index_path.relative_to(BASE_DIR)
        print(f"  [DRY-RUN] トップindex: {rel}")
    else:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(content, encoding="utf-8")
        rel = index_path.relative_to(BASE_DIR)
        print(f"  [index] {rel}")


# ============================================================
# main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="KiCAD PCB デモプロジェクトスタブを生成します",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="実際にファイルを生成（デフォルトは dry-run）",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="既存ファイルを上書き（デフォルトはスキップ）",
    )
    parser.add_argument(
        "--category",
        metavar="CATEGORY",
        help="特定カテゴリのみ処理（例: 01_buffers_inverters）",
    )
    args = parser.parse_args()

    dry_run = not args.apply

    sep = "=" * 60
    if dry_run:
        print(sep)
        print("DRY-RUN モード（実際には何も変更しません）")
        print("  --apply を付けると実際に生成されます")
        print(sep)
    else:
        print(sep)
        print("生成モード")
        if args.overwrite:
            print("  --overwrite: 既存ファイルも上書きします")
        print(sep)

    # テンプレート存在確認
    missing = [t for t in TEMPLATE_FILES if not (TEMPLATES_DIR / t).exists()]
    if missing:
        print(f"[ERROR] テンプレートファイルが見つかりません:")
        for m in missing:
            print(f"  {TEMPLATES_DIR / m}")
        sys.exit(1)

    # データ読み込み
    overview = load_json(OVERVIEW_JSON)
    history = load_json(HISTORY_JSON)
    overview_map = {o["PartNumber"]: o for o in overview}

    stats = {
        "created": 0,
        "skipped_existing": 0,
        "skipped_not_owned": 0,
        "would_create": 0,
    }

    # カテゴリ別集計（index 生成用）
    by_cat: dict = {}
    for entry in history:
        pn = entry["PartNumber"]
        if not (
            entry.get("GottenItemsMN_CMOS")
            or entry.get("GottenItemsMN_TTL")
            or entry.get("GottenItemsMN_Other")
        ):
            continue
        ov = overview_map.get(pn, {})
        cat = ov.get("Category", "99_other")
        if args.category and cat != args.category:
            continue
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append({"PartNumber": pn, **ov})

    # --- プロジェクトファイル生成 ---
    for entry in history:
        pn = entry["PartNumber"]
        ov = overview_map.get(pn, {})
        cat = ov.get("Category", "99_other")
        if args.category and cat != args.category:
            continue
        generate_project(entry, overview_map, dry_run, args.overwrite, stats)

    # --- カテゴリ index 生成 ---
    for cat, parts in sorted(by_cat.items()):
        generate_category_index(cat, parts, dry_run)

    # --- トップ index 生成（カテゴリ絞り込みなし時のみ） ---
    if not args.category:
        generate_top_index(history, overview_map, dry_run)

    # --- サマリ ---
    print()
    print(sep)
    if dry_run:
        print(f"[DRY-RUN 完了]")
        print(f"  生成予定ファイル : {stats['would_create']}")
        print(f"  スキップ（未入手）: {stats['skipped_not_owned']}")
        print()
        print("  → --apply を付けて再実行すると実際に生成されます")
    else:
        print(f"[完了]")
        print(f"  生成              : {stats['created']} ファイル")
        print(f"  スキップ（既存）  : {stats['skipped_existing']} ファイル")
        print(f"  スキップ（未入手）: {stats['skipped_not_owned']} エントリ")
    print(sep)


if __name__ == "__main__":
    main()
