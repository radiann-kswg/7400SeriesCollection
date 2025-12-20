#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Description/Description_JP の表記ゆれを自動で正規化するスクリプト。

対象:
- 7400_series_ic_overview.json（ベース、Rarity不変更）
- 7400_series_ic_overview_fp.json（Rarity不変更）

処理:
- EN: ハイフン表記の統一（open-collector / three-state / edge-triggered など）
- EN: noninverting→non-inverting、Schmitt-trigger の統一など
- JP: 表記の統一（3状態出力/オープンコレクタ/反転/非反転/イネーブル等）
- JP/EN: 重複改行・重複文の削除、前後空白の除去

注意:
- Rarity は一切変更しない
- 意味内容は変えず、用語・記法を揃えるのみ
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE_JSON = os.path.join(WORKSPACE_ROOT, "7400_series_ic_overview.json")
FP_JSON = os.path.join(WORKSPACE_ROOT, "7400_series_ic_overview_fp.json")


def load_array(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"JSON array expected: {path}")
    return data


def save_array(path: str, arr: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(arr, f, ensure_ascii=False, indent=2)


def normalize_en(desc: str) -> str:
    s = desc
    repl = [
        (r"\bopen collector\b", "open-collector"),
        (r"\bOpen collector\b", "Open-collector"),
        (r"\bOpen Collector\b", "Open-collector"),
        (r"\bopen- collector\b", "open-collector"),
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
        # noop for normalization
        (r"\bcomplementary outputs\b", "complementary outputs"),
        (r"\bdriver\/line driver\b", "line driver"),
    ]
    for pat, rep in repl:
        s = re.sub(pat, rep, s)
    # collapse multiple spaces
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_jp(desc: str) -> str:
    s = desc
    repl = [
        (r"3[\s　]?状態", "3状態"),
        (r"オープン[\s　]?コレクタ", "オープンコレクタ"),
        (r"シュミット[\s　]?トリガ", "シュミットトリガ"),
        (r"非[\s　]?反転", "非反転"),
        (r"反転[\s　]?/\s*非反転", "反転/非反転"),
        (r"イネーブル", "イネーブル"),  # stabilize spelling (noop)
        (r"レジスタ[\s　]?ファイル", "レジスタファイル"),
        (r"ドライバ[\s　]?/\s*バッファ", "バッファ/ドライバ"),
        (r"バッファ[\s　]?/\s*ドライバ", "バッファ/ドライバ"),
        (r"シリアル[\s　]?/\s*パラレル", "シリアル/パラレル"),
        (r"パラレル[\s　]?/\s*シリアル", "パラレル/シリアル"),
    ]
    for pat, rep in repl:
        s = re.sub(pat, rep, s)
    # 行分割→重複文の削除→' / 'で再結合
    parts = [p.strip() for p in re.split(r"[\n\r]+", s) if p.strip()]
    uniq: List[str] = []
    seen = set()
    for p in parts:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    s = " / ".join(uniq)
    return s


def refine(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for obj in items:
        if not isinstance(obj, dict):
            continue
        if "Description" in obj and isinstance(obj["Description"], str):
            obj["Description"] = normalize_en(obj["Description"])
        if "Description_JP" in obj and isinstance(obj["Description_JP"], str):
            obj["Description_JP"] = normalize_jp(obj["Description_JP"])
        # Rarity は変更しない
    return items


def main() -> int:
    base = load_array(BASE_JSON)
    fp = load_array(FP_JSON)

    base_ref = refine(base)
    fp_ref = refine(fp)

    save_array(BASE_JSON, base_ref)
    save_array(FP_JSON, fp_ref)

    print(
        f"[INFO] Refined descriptions: base={len(base_ref)}, fp={len(fp_ref)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
