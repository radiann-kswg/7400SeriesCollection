#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


def load_json_array(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"JSON array expected: {path}")
    out: List[Dict[str, Any]] = []
    for obj in data:
        if isinstance(obj, dict):
            out.append(obj)
    return out


def save_json_array(path: str, data: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def iter_category_files(categories_dir: str) -> Iterable[str]:
    for name in sorted(os.listdir(categories_dir)):
        if not name.endswith(".json"):
            continue
        if name.startswith("."):
            continue
        yield os.path.join(categories_dir, name)


def build_category_map_from_categories(categories_dir: str) -> Dict[str, str]:
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


def pn_sort_key(pn: str) -> Tuple[int, str]:
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


@dataclass(frozen=True)
class OutputSpec:
    path: str
    allowed_rarities: Tuple[str, ...]


def choose_bucket(rarity: str, specs: List[Tuple[str, OutputSpec]]) -> Optional[str]:
    for name, spec in specs:
        if rarity in spec.allowed_rarities:
            return name
    return None


def make_skeleton_entry(part_number: str) -> Dict[str, Any]:
    return {
        "PartNumber": part_number,
        "Category": "",
        "GetStartingECS_JP": [],
        "GottenItemsMN_CMOS": [],
        "GottenItemsMN_TTL": [],
        "GottenItemsMN_Other": [],
    }


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


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    overview_path = os.path.join(
        repo_root, "overview", "7400_series_ic_overview.json")
    getstarting_dir = os.path.join(repo_root, "getstarting")

    outputs: List[Tuple[str, OutputSpec]] = [
        (
            "normal_or_lower",
            OutputSpec(
                path=os.path.join(
                    getstarting_dir, "7400_series_ic_purchase_plan_normal_or_lower.json"
                ),
                allowed_rarities=("Commons", "Normal", "Normal+"),
            ),
        ),
        (
            "rare",
            OutputSpec(
                path=os.path.join(
                    getstarting_dir, "7400_series_ic_purchase_plan_rare.json"),
                allowed_rarities=("Rare", "Rare+"),
            ),
        ),
        (
            "maniac",
            OutputSpec(
                path=os.path.join(
                    getstarting_dir, "7400_series_ic_purchase_plan_maniac.json"
                ),
                allowed_rarities=("SuperRare", "Abolition(R+)", "Maniac(SR+)"),
            ),
        ),
        (
            "very_nerd",
            OutputSpec(
                path=os.path.join(
                    getstarting_dir, "7400_series_ic_purchase_wishlist_very_nerd.json"
                ),
                allowed_rarities=("ManiacRare(SSR)", "VeryNerd(UR)"),
            ),
        ),
    ]

    if not os.path.exists(overview_path):
        raise FileNotFoundError(f"overview not found: {overview_path}")

    overview_items = load_json_array(overview_path)

    # PartNumber -> Category（overview が持っていればそれを優先。なければ overview/categories を参照）
    pn_to_category: Dict[str, str] = {}
    overview_has_category = True
    for obj in overview_items:
        pn = obj.get("PartNumber")
        cat = obj.get("Category")
        if not isinstance(pn, str) or not pn:
            continue
        if not isinstance(cat, str) or not cat:
            overview_has_category = False
            break
        pn_to_category[pn] = cat

    if not overview_has_category:
        categories_dir = os.path.join(repo_root, "overview", "categories")
        pn_to_category = build_category_map_from_categories(categories_dir)

    # 既存ファイルの全エントリを集約して、PartNumber単位で保持（重複は警告）
    existing_by_pn: Dict[str, Dict[str, Any]] = {}
    existing_origin: Dict[str, str] = {}
    for bucket_name, spec in outputs:
        if not os.path.exists(spec.path):
            continue
        for obj in load_json_array(spec.path):
            pn = obj.get("PartNumber")
            if not isinstance(pn, str) or not pn:
                continue
            if pn in existing_by_pn:
                # 同一PNが複数ファイルにいる場合は先勝
                continue
            existing_by_pn[pn] = obj
            existing_origin[pn] = bucket_name

    # 生成対象PN一覧（bucketごと）
    pn_by_bucket: Dict[str, List[str]] = {name: [] for name, _ in outputs}

    for obj in overview_items:
        pn = obj.get("PartNumber")
        rarity = obj.get("Rarity")
        if not isinstance(pn, str) or not isinstance(rarity, str):
            continue
        bucket = choose_bucket(rarity, outputs)
        if bucket is None:
            # 未定義のレア度は一旦 normal_or_lower に寄せない（データミス検知のため）
            raise ValueError(f"Unknown Rarity '{rarity}' for PartNumber={pn}")
        pn_by_bucket[bucket].append(pn)

    # 書き込み（既存エントリは内容を保持しつつ、正しいbucketに再配置）
    for bucket_name, spec in outputs:
        pn_list = sorted(set(pn_by_bucket[bucket_name]), key=pn_sort_key)
        out: List[Dict[str, Any]] = []
        for pn in pn_list:
            category = pn_to_category.get(pn)
            if not isinstance(category, str) or not category:
                raise ValueError(f"Category not found for PartNumber={pn}")

            if pn in existing_by_pn:
                out.append(ordered_with_category(existing_by_pn[pn], category))
            else:
                out.append(ordered_with_category(
                    make_skeleton_entry(pn), category))
        save_json_array(spec.path, out)
        print(f"[INFO] Wrote {bucket_name}: {spec.path} ({len(out)} items)")

    # 既存にあったが overview に存在しないPNを検出
    overview_pn_set = {
        obj.get("PartNumber")
        for obj in overview_items
        if isinstance(obj, dict) and isinstance(obj.get("PartNumber"), str)
    }
    extras = [pn for pn in existing_by_pn.keys() if pn not in overview_pn_set]
    if extras:
        extras_sorted = sorted(extras, key=pn_sort_key)
        print("[WARN] Found PartNumber entries not present in overview:")
        for pn in extras_sorted:
            print(f"  - {pn} (from {existing_origin.get(pn, 'unknown')})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
