#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""usage/{category}/{74xNN}/**.md の末尾へ一次資料参照/検証コマンドの定型フッターを追記する。

- 追記は冪等（マーカーがあればスキップ）
- Markdown内のリンクは「各ドキュメントから見た相対パス」で生成

目的:
- datasheets を Git 管理外にする前提でも、一次資料参照の導線を残す
- Web上の参照URLを scripts/check_datasheet_sources.py で機械的に検証できるようにする
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
USAGE_DIR = REPO_ROOT / "usage"
MARKER_BEGIN = "<!-- DATASHEET_FACTCHECK_FOOTER -->"
MARKER_END = "<!-- /DATASHEET_FACTCHECK_FOOTER -->"


def iter_usage_markdown_files() -> Iterable[Path]:
    # New layout: usage/{category}/{74xNN}/**.md
    for path in sorted(USAGE_DIR.glob("**/*.md")):
        if not path.is_file():
            continue

        rel = path.relative_to(USAGE_DIR)
        if not rel.parts:
            continue

        # Skip templates and index pages
        if rel.parts[0].startswith("_"):
            continue
        if path.name.lower() == "index.md":
            continue
        if len(rel.parts) < 2:
            continue

        part_dir = rel.parts[1]
        if not part_dir.startswith("74x"):
            continue

        # Skip auto-generated cheatsheet page: usage/{category}/{74xNN}/{74xNN}.md
        if path.name == f"{part_dir}.md":
            continue

        yield path


def build_footer_for(doc_path: Path) -> str:
    rel = doc_path.relative_to(REPO_ROOT)
    depth = len(rel.parent.parts)  # e.g. usage/06_encoders_decoders/74x141 => 3
    prefix = "../" * depth

    datasheet_sources_link = f"{prefix}datasheets/datasheet_sources.json"
    checker_link = f"{prefix}scripts/check_datasheet_sources.py"

    # 注意: コマンドは「リポジトリルートで実行」が前提。
    return (
        "\n\n---\n\n"
        f"{MARKER_BEGIN}\n\n"
        "## 一次資料（参照情報と検証）\n\n"
        f"- 参照情報: [{datasheet_sources_link}]({datasheet_sources_link})\n"
        f"- 検証スクリプト: [{checker_link}]({checker_link})\n\n"
        "リポジトリルートで以下を実行:\n\n"
        "```bash\n"
        "python3 scripts/check_datasheet_sources.py --skip-empty --report .temp/datasheet_fetch/report.json\n"
        "# （必要ならDL+sha256）\n"
        "python3 scripts/check_datasheet_sources.py --skip-empty --download --report .temp/datasheet_fetch/report.json\n"
        "```\n\n"
        f"{MARKER_END}\n"
    )


def has_footer(text: str) -> bool:
    return MARKER_BEGIN in text and MARKER_END in text


def ensure_trailing_newline(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Append fact-check footer to usage/{category}/{74xNN}/**.md")
    parser.add_argument("--apply", action="store_true", help="Actually write changes")
    args = parser.parse_args()

    targets = list(iter_usage_markdown_files())
    changed = 0
    skipped = 0

    for path in targets:
        original = path.read_text(encoding="utf-8")
        if has_footer(original):
            skipped += 1
            continue

        updated = ensure_trailing_newline(original) + build_footer_for(path)
        if args.apply:
            path.write_text(updated, encoding="utf-8", newline="\n")
        changed += 1

    print("=== append_usage_factcheck_footer ===")
    print(f"targets:  {len(targets)}")
    print(f"changed:  {changed}{'' if args.apply else ' (dry-run)'}")
    print(f"skipped:  {skipped}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
