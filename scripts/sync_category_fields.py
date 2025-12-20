#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Iterable, List


def load_json_array(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"JSON array expected: {path}")
    return [obj for obj in data if isinstance(obj, dict)]


def save_json_array(path: str, data: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


_PART_NUMBER_LINE_RE = re.compile(
    r'^(\s*)"PartNumber"\s*:\s*"([^"]+)"\s*,\s*$')
_CATEGORY_LINE_RE = re.compile(r'^\s*"Category"\s*:\s*"[^"]*"\s*,?\s*$')


def _insert_category_after_partnumber(
    text: str, pn_to_category: Dict[str, str], *, strict: bool
) -> str:
    lines = text.splitlines(keepends=True)

    out: List[str] = []
    missing: List[str] = []

    for idx, line in enumerate(lines):
        match = _PART_NUMBER_LINE_RE.match(line)
        if not match:
            out.append(line)
            continue

        indent, pn = match.group(1), match.group(2)
        out.append(line)

        next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
        if _CATEGORY_LINE_RE.match(next_line):
            continue

        category = pn_to_category.get(pn)
        if not isinstance(category, str) or not category:
            missing.append(pn)
            continue

        newline = "\n" if line.endswith("\n") else ""
        out.append(f'{indent}"Category": "{category}",{newline}')

    if missing and strict:
        uniq = sorted(set(missing))
        raise ValueError(
            f"Category not found for PartNumber(s): {', '.join(uniq)}")

    updated = "".join(out)
    # Safety check: keep JSON valid
    json.loads(updated)
    return updated


def update_file_inplace_with_category(
    path: str, pn_to_category: Dict[str, str], *, strict: bool
) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    updated = _insert_category_after_partnumber(
        original, pn_to_category, strict=strict)
    if updated == original:
        return False

    with open(path, "w", encoding="utf-8") as f:
        f.write(updated)
    return True


def iter_category_files(categories_dir: str) -> Iterable[str]:
    for name in sorted(os.listdir(categories_dir)):
        if not name.endswith(".json"):
            continue
        if name.startswith("."):
            continue
        yield os.path.join(categories_dir, name)


def build_category_map(categories_dir: str) -> Dict[str, str]:
    if not os.path.isdir(categories_dir):
        raise FileNotFoundError(f"categories dir not found: {categories_dir}")

    mapping: Dict[str, str] = {}
    duplicates: Dict[str, List[str]] = {}

    for path in iter_category_files(categories_dir):
        category = os.path.splitext(os.path.basename(path))[0]
        for obj in load_json_array(path):
            pn = obj.get("PartNumber")
            if not isinstance(pn, str) or not pn:
                continue
            if pn in mapping and mapping[pn] != category:
                duplicates.setdefault(pn, [mapping[pn]]).append(category)
                continue
            mapping[pn] = category

    if duplicates:
        items = ", ".join(
            f"{pn}=>{sorted(set(cats))}" for pn, cats in sorted(duplicates.items())
        )
        raise ValueError(f"PartNumber appears in multiple categories: {items}")

    return mapping


def ordered_with_category(obj: Dict[str, Any], category: str) -> Dict[str, Any]:
    # 先頭に PartNumber / Category を置き、それ以外は元の順序を維持
    out: Dict[str, Any] = {}
    pn = obj.get("PartNumber")
    if isinstance(pn, str):
        out["PartNumber"] = pn
    out["Category"] = category
    for k, v in obj.items():
        if k in ("PartNumber", "Category"):
            continue
        out[k] = v
    return out


def update_array_with_category(
    arr: List[Dict[str, Any]], mapping: Dict[str, str], *, strict: bool
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    missing: List[str] = []

    for obj in arr:
        pn = obj.get("PartNumber")
        if not isinstance(pn, str) or not pn:
            out.append(obj)
            continue
        category = mapping.get(pn)
        if category is None:
            missing.append(pn)
            out.append(obj)
            continue
        out.append(ordered_with_category(obj, category))

    if missing and strict:
        uniq = sorted(set(missing))
        raise ValueError(
            f"Category not found for PartNumber(s): {', '.join(uniq)}")

    return out


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    overview_path = os.path.join(
        repo_root, "overview", "7400_series_ic_overview.json")
    categories_dir = os.path.join(repo_root, "overview", "categories")
    getstarting_dir = os.path.join(repo_root, "getstarting")

    mapping = build_category_map(categories_dir)

    # 1) overview に Category を追記（フォーマット変更を避けるためテキスト差し込み）
    changed = update_file_inplace_with_category(
        overview_path, mapping, strict=True)
    print(
        f"[INFO] Updated Category in overview: {overview_path} (changed={changed})"
    )

    # 2) purchase_* に Category を追記
    purchase_files = [
        os.path.join(getstarting_dir,
                     "7400_series_ic_purchase_plan_normal_or_lower.json"),
        os.path.join(getstarting_dir,
                     "7400_series_ic_purchase_plan_rare.json"),
        os.path.join(getstarting_dir,
                     "7400_series_ic_purchase_plan_maniac.json"),
        os.path.join(getstarting_dir,
                     "7400_series_ic_purchase_wishlist_very_nerd.json"),
    ]

    for path in purchase_files:
        if not os.path.exists(path):
            continue
        changed = update_file_inplace_with_category(path, mapping, strict=True)
        print(
            f"[INFO] Updated Category in purchase file: {path} (changed={changed})"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
