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
import re
import sys
from datetime import date
from pathlib import Path

# 実回路図生成モジュール（遅延インポートで ImportError を回避）
try:
    from scripts import kicad_sch_gen as _kicad_sch_gen  # type: ignore[import]
except ImportError:
    try:
        import importlib.util as _iutil, os as _os
        _spec = _iutil.spec_from_file_location(
            "kicad_sch_gen",
            Path(__file__).resolve().parent / "kicad_sch_gen.py",
        )
        _kicad_sch_gen = _iutil.module_from_spec(_spec)  # type: ignore[assignment]
        _spec.loader.exec_module(_kicad_sch_gen)  # type: ignore[union-attr]
    except Exception:
        _kicad_sch_gen = None  # type: ignore[assignment]

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
# demo MD 解析（usage/{category}/{part_number}/01_*.md）
# ============================================================

def _esc_sch(s: str) -> str:
    """KiCAD schematic (text ...) 内の文字列エスケープ。
    - ダブルクォート → \\"
    - バックスラッシュ → \\\\
    - Python 改行 → literal \\n（KiCAD がテキスト折り返しとして解釈）
    """
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    return s


def find_demo_md(category: str, part_number: str) -> "Path | None":
    """usage/{category}/{part_number}/ 配下の 01_*.md を探して返す。"""
    usage_dir = BASE_DIR / "usage" / category / part_number
    if not usage_dir.exists():
        return None
    for p in sorted(usage_dir.glob("01_*.md")):
        return p
    return None


def parse_demo_md(md_path: Path) -> dict:
    """demo MD から回路情報を抽出して辞書で返す。"""
    text = md_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    result: dict = {
        "title": "",
        "power_supply": "+5V",
        "datasheet_url": "",
        "pins": [],        # [{"pin": "1", "name": "1A"}, ...]
        "notes": [],       # ["VCC/GND: ...", ...]
        "components": "",  # 部品リストを平文テキスト化したもの
    }

    # H1 タイトル
    for line in lines:
        if line.startswith("# "):
            result["title"] = line[2:].strip()
            break

    # 電源情報
    m = re.search(r"\*\*電源\*\*[：:]\s*(.+?)(?:\n|$)", text)
    if m:
        result["power_supply"] = m.group(1).strip()

    # ピン配置テーブル（| Pin | Name | 形式）
    in_header = False
    past_sep = False
    for line in lines:
        s = line.strip()
        if re.match(r"\|\s*[Pp]in\s*\|", s):
            in_header = True
            past_sep = False
            continue
        if in_header and not past_sep and re.match(r"\|[-:\s|]+\|", s):
            past_sep = True
            continue
        if in_header and past_sep:
            if not s.startswith("|"):
                in_header = False
                past_sep = False
                continue
            cols = [c.strip() for c in s.strip("|").split("|")]
            if len(cols) >= 2 and cols[0].isdigit():
                result["pins"].append({"pin": cols[0], "name": cols[1]})

    # データシート URL
    m = re.search(r"\*\*データシートURL\*\*[：:]\s*(https?://\S+)", text)
    if m:
        result["datasheet_url"] = m.group(1).strip()

    # 配線要点セクション
    m = re.search(r"## 配線の要点(.*?)(?=\n##|\Z)", text, re.DOTALL)
    if m:
        for line in m.group(1).split("\n"):
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("|") or re.match(r"^-{3,}$", s):
                continue
            s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)  # **bold** 除去
            s = s.lstrip("-* ").strip()
            if s:
                result["notes"].append(s)

    # 必要部品リストセクション
    m = re.search(r"## 必要部品リスト(.*?)(?=\n##|\Z)", text, re.DOTALL)
    if m:
        comp_lines = []
        for line in m.group(1).split("\n"):
            s = line.strip()
            if not s or re.match(r"^-{3,}$", s) or re.match(r"\|[-:\s|]+\|", s):
                continue
            if s.startswith("###"):
                comp_lines.append("[" + s.lstrip("# ") + "]")
            elif s.startswith("|"):
                cols = [c.strip() for c in s.strip("|").split("|") if c.strip()]
                skip_heads = {"部品", "汎用型番", "汎用ロジックic", "個数", "目安"}
                if cols and cols[0].lower() not in skip_heads:
                    comp_lines.append("  " + " / ".join(cols))
        result["components"] = "\n".join(comp_lines)

    return result


def build_sch_from_demo(demo_info: dict, replacements: dict) -> str:
    """demo_info を元にリッチな .kicad_sch コンテンツを生成して返す。"""
    part_number = replacements["{{PART_NUMBER}}"]
    description  = replacements["{{DESCRIPTION}}"]
    description_jp = replacements["{{DESCRIPTION_JP}}"]
    category     = replacements["{{CATEGORY}}"]
    all_owned    = replacements["{{ALL_OWNED_PARTS}}"]
    today        = replacements["{{DATE}}"]

    def t(s: str) -> str:
        return _esc_sch(s)

    # ピン配置テキスト（7ピンごとに折り返し）
    pins = demo_info.get("pins", [])
    if pins:
        chunk = 7
        rows = [
            "  ".join(f"{p['pin']}={p['name']}" for p in pins[i:i + chunk])
            for i in range(0, len(pins), chunk)
        ]
        pin_text = t("\n".join(rows))
    else:
        pin_text = t(f"(ピン情報なし — usage/{category}/{part_number}/ を参照)")

    # 配線要点
    notes = demo_info.get("notes", [])
    notes_text = t("\n".join(f"\u30fb{n}" for n in notes)) if notes else t("(配線要点なし)")

    # データシート URL
    ds_url = t(demo_info.get("datasheet_url", ""))

    # 部品リスト
    comp_raw = demo_info.get("components", "")
    comp_block = (
        f'  (text "【部品リスト】\\n{t(comp_raw)}"\n'
        f'    (at 10 108 0)\n'
        f'    (effects (font (size 1.27 1.27)))\n'
        f'  )\n'
    ) if comp_raw else ""

    # TODO メッセージ
    todo_msg = t(
        f"TODO: 74xxライブラリから {part_number} シンボルを配置し\n"
        f"上記ピン配置・配線要点に従って回路を完成させてください。\n"
        f"usage/{category}/{part_number}/ の一次資料確認チェックリストも参照。"
    )

    circuit_title = t(demo_info.get("title", f"{part_number} Demo"))
    power = t(demo_info.get("power_supply", "+5V"))

    return (
        f'(kicad_sch\n'
        f'  (version 20231120)\n'
        f'  (generator "eeschema")\n'
        f'  (generator_version "8.0")\n'
        f'  (paper "A4")\n'
        f'  (title_block\n'
        f'    (title "{t(part_number)} Demo Circuit")\n'
        f'    (date "{today}")\n'
        f'    (rev "0.1")\n'
        f'    (company "7400 Series Collection")\n'
        f'    (comment 1 "{t(description)}")\n'
        f'    (comment 2 "{t(description_jp)}")\n'
        f'    (comment 3 "Category: {t(category)}")\n'
        f'    (comment 4 "IC: {t(all_owned)}")\n'
        f'  )\n'
        f'  (lib_symbols\n'
        f'  )\n'
        f'  (text "【回路概要】{circuit_title}\\n電源: {power}\\nIC: {t(all_owned)}"\n'
        f'    (at 10 15 0)\n'
        f'    (effects (font (size 1.5 1.5)))\n'
        f'  )\n'
        f'  (text "【ピン配置】\\n{pin_text}"\n'
        f'    (at 10 38 0)\n'
        f'    (effects (font (size 1.27 1.27)))\n'
        f'  )\n'
        f'  (text "【配線要点】\\n{notes_text}"\n'
        f'    (at 10 68 0)\n'
        f'    (effects (font (size 1.27 1.27)))\n'
        f'  )\n'
        f'  (text "【データシート】\\n{ds_url}"\n'
        f'    (at 10 95 0)\n'
        f'    (effects (font (size 1.27 1.27)))\n'
        f'  )\n'
        + comp_block +
        f'  (text "{todo_msg}"\n'
        f'    (at 10 140 0)\n'
        f'    (effects (font (size 1.5 1.5)) (justify left))\n'
        f'  )\n'
        f'  (sheet_instances\n'
        f'    (path "/"\n'
        f'      (page "1")\n'
        f'    )\n'
        f'  )\n'
        f')\n'
    )

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

    # usage/ 配下の demo MD を探す
    demo_md_path = find_demo_md(category, part_number)
    demo_info = parse_demo_md(demo_md_path) if demo_md_path else None
    demo_label = f" ← {demo_md_path.name}" if demo_md_path else ""

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

        # .kicad_sch: 実シンボル回路図 > テキスト注釈 > テンプレートスタブ
        if tmpl_name == "template.kicad_sch":
            real_sch = None
            if _kicad_sch_gen is not None:
                try:
                    real_sch = _kicad_sch_gen.build_real_kicad_sch(part_number, replacements)
                except Exception as exc:
                    print(f"  [WARN] 実回路図生成失敗 ({part_number}): {exc}")
            if real_sch is not None:
                content = real_sch
                src_note = " (実シンボル回路図)"
            elif demo_info is not None:
                content = build_sch_from_demo(demo_info, replacements)
                src_note = f" (テキスト注釈{demo_label})"
            else:
                content = tmpl_path.read_text(encoding="utf-8")
                content = apply_replacements(content, replacements)
                src_note = ""
        else:
            content = tmpl_path.read_text(encoding="utf-8")
            content = apply_replacements(content, replacements)
            src_note = ""

        if dry_run:
            rel = out_path.relative_to(BASE_DIR)
            print(f"  [DRY-RUN] {action}: {rel}{src_note}")
            stats["would_create"] += 1
        else:
            project_dir.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
            rel = out_path.relative_to(BASE_DIR)
            print(f"  [{action}] {rel}{src_note}")
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
    parser.add_argument(
        "--part",
        metavar="PART_NUMBER",
        help="特定汎用型番のみ処理（例: 74x00）",
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
        if args.part and pn != args.part:
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
        if args.part and pn != args.part:
            continue
        generate_project(entry, overview_map, dry_run, args.overwrite, stats)

    # --- カテゴリ index 生成 ---
    for cat, parts in sorted(by_cat.items()):
        generate_category_index(cat, parts, dry_run)

    # --- トップ index 生成（カテゴリ/パーツ絞り込みなし時のみ） ---
    if not args.category and not args.part:
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
