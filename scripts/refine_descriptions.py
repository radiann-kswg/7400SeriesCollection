#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Description/Description_JP の表記ゆれを正規化するスクリプト。

注意:
- 意味内容は変えず、用語・記法を揃えるのみ
- Rarity は一切変更しない
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List


def load_array(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"JSON array expected: {path}")
    return [obj for obj in data if isinstance(obj, dict)]


def save_array(path: str, arr: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(arr, f, ensure_ascii=False, indent=2)
        f.write("\n")


def normalize_en(desc: str) -> str:
    s = desc
    rules = [
        (r"\bopen collector\b", "open-collector"),
        (r"\bOpen collector\b", "Open-collector"),
        (r"\bOpen Collector\b", "Open-collector"),
        (r"\bopen-\s*collector\b", "open-collector"),
        (r"\bthree[\s-]?state\b", "three-state"),
        (r"\bTri[\s-]?state\b", "three-state"),
        (r"\bnoninverting\b", "non-inverting"),
        (r"\bNoninverting\b", "Non-inverting"),
        (r"\bedge triggered\b", "edge-triggered"),
        (r"\bEdge triggered\b", "Edge-triggered"),
        (r"\bnegative[\s-]edge[\s-]triggered\b", "negative-edge-triggered"),
        (r"\bpositive[\s-]edge[\s-]triggered\b", "positive-edge-triggered"),
        (r"\bSchmitt[\s-]?trigger\b", "Schmitt-trigger"),
        (r"\bbi[\s-]?directional\b", "bidirectional"),
    ]
    for pat, rep in rules:
        s = re.sub(pat, rep, s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_jp(desc: str) -> str:
    s = desc
    rules = [
        (r"3[\s　]?状態", "3状態"),
        (r"オープン[\s　]?コレクタ", "オープンコレクタ"),
        (r"シュミット[\s　]?トリガ", "シュミットトリガ"),
        (r"非[\s　]?反転", "非反転"),
        (r"反転[\s　]?/\s*非反転", "反転/非反転"),
        (r"レジスタ[\s　]?ファイル", "レジスタファイル"),
        (r"ドライバ[\s　]?/\s*バッファ", "バッファ/ドライバ"),
        (r"バッファ[\s　]?/\s*ドライバ", "バッファ/ドライバ"),
        (r"シリアル[\s　]?/\s*パラレル", "シリアル/パラレル"),
        (r"パラレル[\s　]?/\s*シリアル", "パラレル/シリアル"),
    ]
    for pat, rep in rules:
        s = re.sub(pat, rep, s)

    parts = [p.strip() for p in re.split(r"[\n\r]+", s) if p.strip()]
    uniq: List[str] = []
    seen = set()
    for p in parts:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return " / ".join(uniq)


def refine(items: List[Dict[str, Any]]) -> None:
    for obj in items:
        d = obj.get("Description")
        if isinstance(d, str):
            obj["Description"] = normalize_en(d)
        dj = obj.get("Description_JP")
        if isinstance(dj, str):
            obj["Description_JP"] = normalize_jp(dj)


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    overview_path = os.path.join(
        repo_root, "overview", "7400_series_ic_overview.json")

    items = load_array(overview_path)
    refine(items)
    save_array(overview_path, items)

    print(f"[INFO] Refined descriptions: {overview_path} ({len(items)} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
