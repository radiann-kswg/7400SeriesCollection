#!/usr/bin/env python3
"""Generate per-part cheat sheets under usage/{category}/{part}/ from overview data.

Design goals:
- Idempotent by default: does not overwrite existing part pages.
- Keeps content conservative: only uses overview fields + generic guidance.
- Generates indexes (top + per-category) for navigation.

Usage:
  python3 scripts/generate_usage_cheatsheets.py
  python3 scripts/generate_usage_cheatsheets.py --force

"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
OVERVIEW_JSON_PATH = REPO_ROOT / "overview" / "7400_series_ic_overview.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "usage"
TEMPLATES_DIR = REPO_ROOT / "usage" / "_templates"


@dataclass(frozen=True)
class Part:
    part_number: str
    category: str
    description: str
    description_jp: str
    rarity: str


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_text(path: Path, content: str, *, force: bool) -> bool:
    """Write file. Returns True if written, False if skipped."""
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def _normalize_part_number(part_number: str) -> str:
    # Keep as-is but sanitize path separators just in case.
    return part_number.replace("/", "-").strip()


def _is_open_collector(part: Part) -> bool:
    text = f"{part.description} {part.description_jp}".lower()
    return "open-collector" in text or "オープンコレクタ" in text


def _is_tristate(part: Part) -> bool:
    text = f"{part.description} {part.description_jp}".lower()
    return "3-state" in text or "three-state" in text or "トライステート" in text


def _render_part_page(part: Part) -> str:
    oc = _is_open_collector(part)
    ts = _is_tristate(part)

    caveats: list[str] = [
        "**入力をフローティングさせない**: 未使用入力はプルアップ/プルダウンで固定する（CMOS系は特に重要）。",
        "**電源デカップリング**: IC 1個につき 0.1µF を VCC-GND 直近に配置（配線が長い場合は追加でバルクも検討）。",
        "**ロジックファミリ差に注意**: 74HC/74HCT/74LS/74S/74F 等で入力閾値・出力駆動・速度・消費電流が変わる。",
    ]

    if oc:
        caveats.insert(
            0,
            "**オープンコレクタ出力**: 外付けプルアップ抵抗が必要（ワイヤードOR等が可能だが、電流/電圧定格は必ず一次資料で確認）。",
        )

    if ts:
        caveats.insert(
            0,
            "**3-state出力**: イネーブル未定義でバス衝突し得るため、制御信号の既定状態を必ず設計する。",
        )

    caveats_md = "\n".join([f"- {c}" for c in caveats])

    today = date.today().isoformat()

    # Keep this page entirely free from datasheet-derived specifics.
    return f"""# {part.part_number} — {part.description}

> このページは自動生成テンプレートです。**ピン配置/真理値表/電気特性など、一次資料が必要な事項は意図的に書いていません**。

## 概要

- **汎用型番**: `{part.part_number}`
- **カテゴリ**: `{part.category}`
- **機能（EN）**: {part.description}
- **機能（JP）**: {part.description_jp}
- **レア度**: `{part.rarity}`

## 使いどころ（ざっくり）

- TODO: この IC を使う回路例（このリポ内の usage 実例）へのリンク
- TODO: よくある用途（ゲート構成、バス、デコード、タイミング等）を1〜3点

## 配線・運用の注意（一般論）

{caveats_md}

## ファクトチェック（一次資料）

この IC の「実配線に直結する事項」は、**必ずメーカー/型番/パッケージを特定した一次資料**で確認してから追記してください。

- [ ] **対象の実型番を決める**（例: `SN74HCxxN`, `74HCxxN`, `HD74HCxx` など）
- [ ] **ピン配置**（DIP/SOIC/TSSOP など）
- [ ] **真理値表/機能表**（イネーブル極性含む）
- [ ] **絶対最大定格/推奨動作条件**（Vcc 範囲、入力電圧、I/O 電流 等）
- [ ] **電気特性**（VIH/VIL, VOH/VOL, IOL/IOH, tpd など）
- [ ] **未使用入力/未使用出力の扱い**（データシート推奨）

### 参照候補（このリポ内）

- overview: [overview/7400_series_ic_overview.json](../../../overview/7400_series_ic_overview.json)
- datasheet収集状況: [datasheets/7400_series_ic_datasheet_collection_status.json](../../../datasheets/7400_series_ic_datasheet_collection_status.json)
- 入手履歴: [getstarting/7400_series_ic_collection_acquisition_history.json](../../../getstarting/7400_series_ic_collection_acquisition_history.json)

## 参考リンク（外部）

- TODO: メーカー公式データシートURL（可能ならdoc番号/Revも併記）
- TODO: Wikipedia など概要ソース（*一次資料の代替にはしない*）

---

生成日時: {today}
"""


def _render_cheatsheets_index(parts: Iterable[Part]) -> str:
    category_to_parts: dict[str, list[Part]] = {}
    for part in parts:
        category_to_parts.setdefault(part.category, []).append(part)

    lines: list[str] = []
    lines.append("# 7400シリーズ 汎用型番チートシート (Index)")
    lines.append("")
    lines.append("このディレクトリ（`usage/`）配下に `usage/{カテゴリ}/{74xNN}/{74xNN}.md` として自動生成する **汎用型番（74xNN）単位**のチートシート集です。")
    lines.append("")
    lines.append("- 1パーツ = 1ファイル")
    lines.append("- 仕様断定（ピン配置/電気特性/真理値表など）は一次資料が必要なので、未検証のまま書かない方針")
    lines.append("")

    for category in sorted(category_to_parts.keys()):
        part_count = len(category_to_parts[category])
        lines.append(f"- [{category}](./{category}/index.md) ({part_count})")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"生成日時: {date.today().isoformat()}")
    lines.append("")
    return "\n".join(lines)


def _render_category_index(category: str, parts: list[Part]) -> str:
    lines: list[str] = []
    lines.append(f"# {category}")
    lines.append("")
    lines.append("このカテゴリ配下の汎用型番チートシート一覧です。")
    lines.append("")

    for part in sorted(parts, key=lambda p: p.part_number):
        pn = _normalize_part_number(part.part_number)
        lines.append(f"- [{pn}](./{pn}/{pn}.md) — {part.description}")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"生成日時: {date.today().isoformat()}")
    lines.append("")
    return "\n".join(lines)


def load_parts(overview_path: Path) -> list[Part]:
    raw = _read_json(overview_path)
    if not isinstance(raw, list):
        raise ValueError("overview JSON must be a list")

    parts: list[Part] = []
    for item in raw:
        if not isinstance(item, dict):
            continue

        part_number = str(item.get("PartNumber", "")).strip()
        category = str(item.get("Category", "99_other")).strip() or "99_other"
        description = str(item.get("Description", "")).strip()
        description_jp = str(item.get("Description_JP", "")).strip()
        rarity = str(item.get("Rarity", "")).strip()

        if not part_number:
            continue

        parts.append(
            Part(
                part_number=part_number,
                category=category,
                description=description,
                description_jp=description_jp,
                rarity=rarity,
            )
        )

    return parts


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate usage cheat sheets from overview JSON")
    parser.add_argument("--overview", type=Path, default=OVERVIEW_JSON_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--force", action="store_true", help="Overwrite existing markdown files")
    parser.add_argument(
        "--write-root-index",
        action="store_true",
        help="Also (re)generate usage/index.md. Off by default to avoid overwriting manual navigation.",
    )

    args = parser.parse_args()

    parts = load_parts(args.overview)

    written_part_pages = 0
    skipped_part_pages = 0

    # Part pages
    for part in parts:
        pn = _normalize_part_number(part.part_number)
        category_dir = args.output / part.category / pn
        filename = f"{pn}.md"
        out_path = category_dir / filename
        if _write_text(out_path, _render_part_page(part), force=args.force):
            written_part_pages += 1
        else:
            skipped_part_pages += 1

    # Indexes
    if args.write_root_index:
        _write_text(args.output / "index.md", _render_cheatsheets_index(parts), force=True)

    category_to_parts: dict[str, list[Part]] = {}
    for part in parts:
        category_to_parts.setdefault(part.category, []).append(part)

    for category, category_parts in category_to_parts.items():
        _write_text(args.output / category / "index.md", _render_category_index(category, category_parts), force=True)

    # Templates (copy minimal, not strictly required but useful)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    _write_text(
        TEMPLATES_DIR / "logic-ic-cheatsheet.md",
        """# {PartNumber} — {Description}

> TODO: このICの要点を1行で（一次資料が必要な断定は避ける）。

## 概要

- **汎用型番**: `{PartNumber}`
- **カテゴリ**: `{Category}`
- **機能（EN）**: {Description}
- **機能（JP）**: {Description_JP}
- **レア度**: `{Rarity}`

## 使いどころ（ざっくり）

- TODO

## 配線・運用の注意（一般論）

- TODO

## ファクトチェック（一次資料）

- [ ] 対象の実型番/メーカー/パッケージを決める
- [ ] ピン配置
- [ ] 真理値表/機能表
- [ ] 絶対最大定格/推奨動作条件
- [ ] 電気特性

## 参考

- overview: [overview/7400_series_ic_overview.json](../../overview/7400_series_ic_overview.json)
- datasheets収集状況: [datasheets/7400_series_ic_datasheet_collection_status.json](../../datasheets/7400_series_ic_datasheet_collection_status.json)
""",
        force=True,
    )

    print("=== generate_usage_cheatsheets ===")
    print(f"overview: {args.overview}")
    print(f"output:   {args.output}")
    print(f"parts:    {len(parts)}")
    print(f"written:  {written_part_pages}")
    print(f"skipped:  {skipped_part_pages}")
    print(f"root_index:{'written' if args.write_root_index else 'skipped'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
