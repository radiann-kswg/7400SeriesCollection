#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GottenItems_MN を CMOS/TTL/Other に分類して移し替えるスクリプト。

要件:
- CMOS:  正規表現 r"^([A-Z]{0,2})74(HC[TU]?)(\d{2,3})([A-Z]{0,3})$" にマッチ
- TTL:   正規表現 r"^([A-Z]{0,2})74((?:L|LS|S)?)(\d{2,3})([A-Z]{0,3})$" にマッチし、
         グループ2が "LS" または "L" または "S"（＝TTL系）
- その他: 上記いずれにも該当しない。

スラッシュ含み要素（例: "MM74HC04N/MC74HC04N"）は、前後を個別判定し、
両側が同一カテゴリならそのカテゴリに、混在なら Other に格納する。

対象ファイルは引数で指定。上書き保存する。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import List, Tuple


RE_CMOS = re.compile(
    r"^([A-Z]{0,2})74(HC[TU]?)\d{2,3}([A-Z]{0,3})$", re.IGNORECASE)
# TTL系: L, LS, S を許容（依頼の例に 74S374N などがあるため）
RE_TTL = re.compile(
    r"^([A-Z]{0,2})74((?:L|LS|S)?)(\d{2,3})([A-Z]{0,3})$", re.IGNORECASE)


def classify_token(token: str) -> str:
    """トークン1個を CMOS/TTL/Other に分類して返す。

    ルール:
    - CMOS: RE_CMOS にマッチ
    - TTL:  RE_TTL にマッチ かつ サブグループ2が L/LS/S のいずれか
    - その他: 上記以外
    """
    s = token.strip()
    if not s:
        return "Other"

    if RE_CMOS.match(s):
        return "CMOS"

    m = RE_TTL.match(s)
    if m:
        fam = m.group(2).upper() if m.group(2) else ""
        if fam in {"L", "LS", "S"}:
            return "TTL"

    return "Other"


def classify_item(item: str) -> str:
    """アイテム全体（スラッシュを含む可能性あり）を分類。

    - '/' を含む場合は前後をそれぞれ classify_token し、
      両者のカテゴリが同一ならそのカテゴリ、異なるなら Other を返す。
    - 含まない場合はそのまま classify_token の結果を返す。
    """
    if "/" in item:
        left, right = item.split("/", 1)
        cl = classify_token(left)
        cr = classify_token(right)
        return cl if cl == cr else "Other"
    return classify_token(item)


def process_record(rec: dict) -> dict:
    """1レコードを分類してフィールドを書き換える。

    - 入力: rec は辞書で 'GottenItems_MN' を含む想定（無ければスキップ）
    - 出力: rec を破壊的に更新して返す
    """
    items: List[str] = rec.get("GottenItems_MN", []) or []

    cmos: List[str] = []
    ttl: List[str] = []
    other: List[str] = []

    for it in items:
        category = classify_item(it)
        if category == "CMOS":
            cmos.append(it)
        elif category == "TTL":
            ttl.append(it)
        else:
            other.append(it)

    # 新フィールドへ格納
    rec["GottenItemsMN_CMOS"] = cmos
    rec["GottenItemsMN_TTL"] = ttl
    rec["GottenItemsMN_Other"] = other
    # 旧フィールドは空配列にして退避（消し切らず安全側に）
    rec["GottenItems_MN"] = []

    return rec


def process_file(path: Path) -> Tuple[int, int, int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError("ルートは配列(JSON array)である必要があります")

    total = len(data)
    moved_c = moved_t = moved_o = 0

    for rec in data:
        before = rec.get("GottenItems_MN", []) or []
        process_record(rec)
        moved_c += len(rec["GottenItemsMN_CMOS"])
        moved_t += len(rec["GottenItemsMN_TTL"])
        moved_o += len(rec["GottenItemsMN_Other"])

    # 上書き保存
    path.write_text(json.dumps(data, ensure_ascii=False,
                    indent=2), encoding="utf-8")
    return total, moved_c, moved_t, moved_o


def main() -> None:
    ap = argparse.ArgumentParser(
        description="GottenItems_MN を CMOS/TTL/Other に移し替え")
    ap.add_argument("json_path", type=str, help="対象JSONファイルパス")
    args = ap.parse_args()

    path = Path(args.json_path)
    if not path.exists():
        raise SystemExit(f"ファイルが見つかりません: {path}")

    total, c, t, o = process_file(path)
    print(f"Processed {total} records. CMOS:{c} TTL:{t} Other:{o}")


if __name__ == "__main__":
    main()
