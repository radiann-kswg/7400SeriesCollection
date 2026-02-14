#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Migrate usage/ structure to the integrated layout.

Target layout:
  usage/{カテゴリ名}/{パーツ番号}/**.md

Special-case layout:
    usage/A_combinated_samples/{パーツ番号}/**.md  (複数IC連携サンプル: 例 74x181,182)

This script migrates:
- old cheatsheet tree under usage/: cheatsheets/{category}/{74xNN}.md -> usage/{category}/{74xNN}/{74xNN}.md
- old cheatsheet category index under usage/: cheatsheets/{category}/index.md   -> usage/{category}/index.md
- old manual circuit docs that lived as 74x* folders directly under usage/ (e.g. 74x141/*)
    -> usage/{category}/{74x*}/**.md

Notes:
- Default is dry-run. Use --apply to actually move files.
- By default it will not overwrite existing destination files; use --force to overwrite.
- It also adjusts a few well-known relative links inside migrated cheatsheet pages.

"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
USAGE_DIR = REPO_ROOT / "usage"
OLD_CHEATSHEETS_DIR = USAGE_DIR / "cheatsheets"
OVERVIEW_CATEGORIES_DIR = REPO_ROOT / "overview" / "categories"


@dataclass(frozen=True)
class MoveAction:
    src: Path
    dst: Path
    kind: str  # "file" | "dir"


def _read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_part_to_category_map() -> Dict[str, str]:
    """Map generic PartNumber (e.g. 74x141) -> category dir (e.g. 06_encoders_decoders)."""

    mapping: Dict[str, str] = {}

    if not OVERVIEW_CATEGORIES_DIR.exists():
        return mapping

    for path in sorted(OVERVIEW_CATEGORIES_DIR.glob("*.json")):
        category = path.stem
        raw = _read_json(path)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            pn = str(item.get("PartNumber", "")).strip()
            if pn and pn not in mapping:
                mapping[pn] = category

    return mapping


def iter_old_cheatsheet_part_pages() -> Iterable[Tuple[str, Path]]:
    if not OLD_CHEATSHEETS_DIR.exists():
        return

    for category_dir in sorted(OLD_CHEATSHEETS_DIR.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name
        for md in sorted(category_dir.glob("*.md")):
            if md.name.lower() == "index.md":
                continue
            yield (category, md)


def iter_old_cheatsheet_category_indexes() -> Iterable[Tuple[str, Path]]:
    if not OLD_CHEATSHEETS_DIR.exists():
        return

    for category_dir in sorted(OLD_CHEATSHEETS_DIR.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name
        idx = category_dir / "index.md"
        if idx.exists() and idx.is_file():
            yield (category, idx)


def first_generic_part_from_dirname(name: str) -> Optional[str]:
    # e.g. "74x181,182" => "74x181"
    first = name.split(",", 1)[0].strip()
    return first if first.startswith("74x") else None


def iter_old_manual_part_dirs() -> Iterable[Path]:
    for p in sorted(USAGE_DIR.iterdir()):
        if p.is_dir() and p.name.startswith("74x"):
            yield p


def rewrite_cheatsheet_links(text: str) -> str:
    # Old cheatsheets lived under usage/ in a cheatsheets/<cat>/<part>.md tree
    # New location will be:      usage/<cat>/<part>/<part>.md
    # So repo-root relative links need one extra "../".
    text = text.replace("(../../overview/", "(../../../overview/")
    text = text.replace("(../../datasheets/", "(../../../datasheets/")
    text = text.replace("(../../getstarting/", "(../../../getstarting/")
    return text


_RE_LOCAL_PART_LINK = re.compile(r"\(\./(?P<fn>74x[^)\\/]+?\.md)\)")


def rewrite_category_index_links(text: str) -> str:
    # ./74x153.md -> ./74x153/74x153.md
    def repl(m: re.Match[str]) -> str:
        fn = m.group("fn")
        stem = fn[:-3] if fn.lower().endswith(".md") else fn
        return f"(./{stem}/{fn})"

    return _RE_LOCAL_PART_LINK.sub(repl, text)


def plan_moves(part_to_category: Dict[str, str]) -> List[MoveAction]:
    actions: List[MoveAction] = []

    # Cheatsheet part pages
    for category, md in iter_old_cheatsheet_part_pages():
        part = md.stem
        dst = USAGE_DIR / category / part / md.name
        actions.append(MoveAction(src=md, dst=dst, kind="file"))

    # Cheatsheet category index
    for category, idx in iter_old_cheatsheet_category_indexes():
        dst = USAGE_DIR / category / "index.md"
        actions.append(MoveAction(src=idx, dst=dst, kind="file"))

    # Manual circuit example directories (old layout: usage/ directly contained 74x* dirs)
    for src_dir in iter_old_manual_part_dirs():
        # If the folder name suggests multi-part series (comma-separated), put it under A_combinated_samples.
        if "," in src_dir.name:
            dst_dir = USAGE_DIR / "A_combinated_samples" / src_dir.name
        else:
            generic = first_generic_part_from_dirname(src_dir.name)
            category = part_to_category.get(generic or "", "99_other")
            dst_dir = USAGE_DIR / category / src_dir.name
        actions.append(MoveAction(src=src_dir, dst=dst_dir, kind="dir"))

    return actions


def _move_file(src: Path, dst: Path, *, apply: bool, force: bool, verbose: bool) -> Tuple[bool, str]:
    if dst.exists() and not force:
        return (False, "skip (exists)")

    if verbose:
        print(f"FILE: {src} -> {dst}")

    if apply:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and force:
            dst.unlink()
        shutil.move(str(src), str(dst))

    return (True, "moved")


def _merge_dir(src_dir: Path, dst_dir: Path, *, apply: bool, force: bool, verbose: bool) -> Tuple[int, int]:
    """Move src_dir into dst_dir, merging children. Returns (moved_items, skipped_items)."""

    moved = 0
    skipped = 0

    if verbose:
        print(f"DIR:  {src_dir} -> {dst_dir}")

    if not apply:
        # Dry-run: just count children.
        for child in src_dir.iterdir():
            target = dst_dir / child.name
            if target.exists() and not force:
                skipped += 1
            else:
                moved += 1
        return moved, skipped

    dst_dir.mkdir(parents=True, exist_ok=True)

    for child in src_dir.iterdir():
        target = dst_dir / child.name
        if target.exists() and not force:
            skipped += 1
            continue
        if target.exists() and force:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        shutil.move(str(child), str(target))
        moved += 1

    # Remove now-empty src_dir
    try:
        src_dir.rmdir()
    except OSError:
        pass

    return moved, skipped


def _rewrite_file_in_place(path: Path, rewrite_fn, *, apply: bool) -> bool:
    text = path.read_text(encoding="utf-8")
    new_text = rewrite_fn(text)
    if new_text == text:
        return False
    if apply:
        path.write_text(new_text, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate usage/ to integrated category/part structure")
    parser.add_argument("--apply", action="store_true", help="Actually move files")
    parser.add_argument("--force", action="store_true", help="Overwrite destination files if they exist")
    parser.add_argument("--verbose", action="store_true", help="Print every action")

    args = parser.parse_args()

    part_to_category = build_part_to_category_map()
    actions = plan_moves(part_to_category)

    moved_files = 0
    skipped_files = 0
    rewritten_files = 0
    moved_dir_items = 0
    skipped_dir_items = 0

    # Process files first
    for act in actions:
        if act.kind != "file":
            continue

        did, reason = _move_file(act.src, act.dst, apply=args.apply, force=args.force, verbose=args.verbose)
        if did:
            moved_files += 1

            # Rewrite only when the destination file actually exists.
            if args.apply:
                # Rewrite link depths for cheatsheet part pages
                if act.dst.parent.name.startswith("74x") and act.dst.name.lower().endswith(".md") and act.src.parent.parent.name == "cheatsheets":
                    if _rewrite_file_in_place(act.dst, rewrite_cheatsheet_links, apply=True):
                        rewritten_files += 1

                # Rewrite links for category index pages
                if act.dst.name.lower() == "index.md" and act.src.parent.parent.name == "cheatsheets":
                    if _rewrite_file_in_place(act.dst, rewrite_category_index_links, apply=True):
                        rewritten_files += 1
        else:
            skipped_files += 1
            if args.verbose:
                print(f"SKIP: {act.src} -> {act.dst} ({reason})")

    # Then directories (manual circuit docs)
    for act in actions:
        if act.kind != "dir":
            continue
        m, s = _merge_dir(act.src, act.dst, apply=args.apply, force=args.force, verbose=args.verbose)
        moved_dir_items += m
        skipped_dir_items += s

    # Cleanup old cheatsheets tree if empty (best-effort)
    if args.apply and OLD_CHEATSHEETS_DIR.exists():
        try:
            # Remove empty category dirs
            for d in sorted(OLD_CHEATSHEETS_DIR.glob("*") , reverse=True):
                if d.is_dir():
                    try:
                        d.rmdir()
                    except OSError:
                        pass
            OLD_CHEATSHEETS_DIR.rmdir()
        except OSError:
            pass

    print("=== migrate_usage_structure ===")
    print(f"apply:            {args.apply}")
    print(f"force:            {args.force}")
    print(f"moved files:      {moved_files}")
    print(f"skipped files:    {skipped_files}")
    print(f"rewritten files:  {rewritten_files}{'' if args.apply else ' (dry-run)'}")
    print(f"moved dir items:  {moved_dir_items}")
    print(f"skipped dir items:{skipped_dir_items}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
