#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Set

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE_JSON = os.path.join(WORKSPACE_ROOT, "7400_series_ic_overview.json")
DATAS_DIR = os.path.join(WORKSPACE_ROOT, "datas")
RANGE_FILES = [
    "7400_series_ic_missing_description_00-99.json",
    "7400_series_ic_missing_description_100-199.json",
    "7400_series_ic_missing_description_200-299.json",
    "7400_series_ic_missing_description_300-399.json",
    "7400_series_ic_missing_description_400-499.json",
    "7400_series_ic_missing_description_500-599.json",
    "7400_series_ic_missing_description_600-699.json",
    "7400_series_ic_missing_description_700-832.json",
]

OUTPUT_FP = os.path.join(WORKSPACE_ROOT, "7400_series_ic_overview_fp.json")
OUTPUT_ALL = os.path.join(WORKSPACE_ROOT, "7400_series_ic_overview_all.json")

REQUIRED_KEYS = {"PartNumber", "Description", "Description_JP", "Rarity"}
ALLOWED_RARITY = {
    "Commons",
    "Normal",
    "Normal+",
    "Rare",
    "SuperRare",
    "Maniac(SR+)",
    "ManiacRare(SSR)",
    "VeryNerd(UR)",
    "Abolition(R+)",
}


def load_json_array(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"JSON array expected: {path}")
    return data


def index_by_part(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for obj in items:
        if not isinstance(obj, dict):
            continue
        pn = obj.get("PartNumber")
        if isinstance(pn, str):
            idx[pn] = obj
    return idx


def validate_item(obj: Dict[str, Any], context: str) -> None:
    missing = REQUIRED_KEYS - set(obj.keys())
    if missing:
        print(
            f"[WARN] Missing keys {missing} in {context} for PartNumber={obj.get('PartNumber')}")
    r = obj.get("Rarity")
    if isinstance(r, str) and r not in ALLOWED_RARITY:
        print(
            f"[WARN] Unexpected Rarity '{r}' in {context} for PartNumber={obj.get('PartNumber')}")


def pn_sort_key(pn: str) -> tuple:
    num = None
    digits = []
    for ch in reversed(pn):
        if ch.isdigit():
            digits.append(ch)
        else:
            break
    if digits:
        try:
            num = int("".join(reversed(digits)))
        except ValueError:
            num = None
    return (num is None, num if num is not None else 0, pn)


def main() -> int:
    if not os.path.exists(BASE_JSON):
        print(f"[ERROR] Base JSON not found: {BASE_JSON}")
        return 1

    base_items = load_json_array(BASE_JSON)
    base_index = index_by_part(base_items)
    base_parts: Set[str] = set(base_index.keys())

    fp_index: Dict[str, Dict[str, Any]] = {}

    for fname in RANGE_FILES:
        path = os.path.join(DATAS_DIR, fname)
        if not os.path.exists(path):
            print(f"[WARN] Range file not found, skip: {path}")
            continue
        items = load_json_array(path)
        for obj in items:
            if not isinstance(obj, dict):
                continue
            pn = obj.get("PartNumber")
            if not isinstance(pn, str):
                continue
            validate_item(obj, context=fname)
            if pn in base_parts:
                continue
            fp_index[pn] = obj

    fp_items = list(fp_index.values())
    fp_items.sort(key=lambda o: pn_sort_key(str(o.get("PartNumber", ""))))

    if fp_items:
        with open(OUTPUT_FP, "w", encoding="utf-8") as f:
            json.dump(fp_items, f, ensure_ascii=False, indent=2)
        print(f"[INFO] Wrote FP: {OUTPUT_FP} ({len(fp_items)} items)")
    else:
        # Fallback: keep and use existing FP if present
        if os.path.exists(OUTPUT_FP):
            try:
                fp_items = load_json_array(OUTPUT_FP)
                print(
                    f"[INFO] No range files found or empty; using existing FP: {OUTPUT_FP} ({len(fp_items)} items)")
            except Exception as e:
                print(
                    f"[ERROR] Failed to load existing FP at {OUTPUT_FP}: {e}")
        else:
            print(
                f"[INFO] No FP data available to write and no existing FP found. Proceeding with base only.")

    all_index = dict(base_index)
    # Merge FP (from newly built or existing) into ALL
    for obj in fp_items:
        pn = obj.get("PartNumber") if isinstance(obj, dict) else None
        if not isinstance(pn, str):
            continue
        if pn not in all_index:
            all_index[pn] = obj

    all_items = list(all_index.values())
    all_items.sort(key=lambda o: pn_sort_key(str(o.get("PartNumber", ""))))

    with open(OUTPUT_ALL, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Wrote ALL: {OUTPUT_ALL} ({len(all_items)} items)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
