# -*- coding: utf-8 -*-
"""
自動補完スクリプト: getstarting側の `GottenItemsMN_**` にある型番を、
`datasheets/7400_series_ic_datasheet_collection_status.json` の
`GottenItems_MakerOfDataSheet` に不足分として追記する。

追加時の値ルール:
- 型番からメーカー名が高確度で推定できる場合: "(収集予定:<メーカー名>)"
- 推定できない場合: "(保留)"

推定ポリシー（保守的に高確度な接頭辞のみ採用）:
- SN74... -> TI(Texas Instruments)
- CD74... -> TI(Texas Instruments)
- U74...  -> UTC(Unisonic Technologies)
- HD74... -> RENESAS
- TC74... -> TOSHIBA
- MM74... または MC74... -> FAIRCHILD(Fairchild Semiconductor)
- 74HC...（ベンダ接頭辞なし） -> PHILIPS(NXP Semiconductors)
  （既存値は上書きしないので、AP等のバリエーションとの不一致は回避される）

使い方（PowerShell）:
  python ./scripts/autofill_gottenitems.py

オプション:
  --dry-run   書き込みせず差分のみ表示
  --verbose   追記の詳細ログを表示
  --datasheets <path>
  --getstarting <path>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Set


def guess_maker(part_code: str) -> str | None:
    code = part_code.strip()
    # スラッシュ区切り（例: "MM74HC04N/MC74HC04N"）は先頭だけ見て推定
    if "/" in code:
        code = code.split("/")[0].strip()

    starts = code.upper()
    try:
        if starts.startswith("SN74"):
            return "TI(Texas Instruments)"
        if starts.startswith("CD74"):
            return "TI(Texas Instruments)"
        if starts.startswith("U74"):
            return "UTC(Unisonic Technologies)"
        if starts.startswith("HD74"):
            return "RENESAS"
        if starts.startswith("TC74"):
            return "TOSHIBA"
        if starts.startswith("MM74") or starts.startswith("MC74"):
            return "FAIRCHILD(Fairchild Semiconductor)"
        # ベンダ接頭辞なしの74HCシリーズはPHILIPS/NXPに寄せる（既存値は上書きしない）
        if starts.startswith("74HC"):
            return "PHILIPS(NXP Semiconductors)"
    except Exception:
        pass
    return None


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def collect_gotten_items(entry: Dict[str, Any]) -> Set[str]:
    items: Set[str] = set()
    for k, v in entry.items():
        if k.startswith("GottenItemsMN_") and isinstance(v, list):
            for item in v:
                if isinstance(item, str) and item.strip():
                    items.add(item.strip())
    return items


def index_by_partnumber(arr: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for obj in arr:
        pn = obj.get("PartNumber")
        if isinstance(pn, str):
            idx[pn] = obj
    return idx


def main() -> int:
    parser = argparse.ArgumentParser()
    base_dir = os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))  # repo root
    default_datasheets = os.path.join(
        base_dir, "datasheets", "7400_series_ic_datasheet_collection_status.json")
    default_getstarting = os.path.join(
        base_dir, "getstarting", "7400_series_ic_collection_acquisition_history.json")

    parser.add_argument(
        "--datasheets", default=default_datasheets, help="データシート側JSONのパス")
    parser.add_argument(
        "--getstarting", default=default_getstarting, help="所持状況側JSONのパス")
    parser.add_argument("--dry-run", action="store_true", help="書き込みせず差分のみ表示")
    parser.add_argument("--verbose", action="store_true", help="追記の詳細を表示")
    args = parser.parse_args()

    datasheets_path = args.datasheets
    getstarting_path = args.getstarting

    # 入力の存在確認
    if not os.path.exists(datasheets_path):
        print(
            f"[ERROR] datasheets JSON not found: {datasheets_path}", file=sys.stderr)
        return 2
    if not os.path.exists(getstarting_path):
        print(
            f"[ERROR] getstarting JSON not found: {getstarting_path}", file=sys.stderr)
        return 2

    # ロード
    datasheets = load_json(datasheets_path)
    getstarting = load_json(getstarting_path)

    if not isinstance(datasheets, list) or not isinstance(getstarting, list):
        print(
            "[ERROR] Unexpected JSON structure (expected top-level arrays)", file=sys.stderr)
        return 2

    ds_idx = index_by_partnumber(datasheets)

    total_added_keys = 0
    total_new_parts = 0
    added_by_part: Dict[str, List[str]] = {}

    for gs_entry in getstarting:
        if not isinstance(gs_entry, dict):
            continue
        part_number = gs_entry.get("PartNumber")
        if not isinstance(part_number, str):
            continue

        wanted_items = collect_gotten_items(gs_entry)
        if not wanted_items:
            continue

        ds_entry = ds_idx.get(part_number)
        if ds_entry is None:
            ds_entry = {"PartNumber": part_number,
                        "GottenItems_MakerOfDataSheet": {}}
            datasheets.append(ds_entry)
            ds_idx[part_number] = ds_entry
            total_new_parts += 1

        maker_dict = ds_entry.get("GottenItems_MakerOfDataSheet")
        if not isinstance(maker_dict, dict):
            maker_dict = {}
            ds_entry["GottenItems_MakerOfDataSheet"] = maker_dict

        for code in sorted(wanted_items):
            if (code in maker_dict):
                continue  # 既存は上書きしない
            maker = guess_maker(code)
            if maker:
                value = f"(収集予定:{maker})"
            else:
                value = "(保留)"
            maker_dict[code] = value
            total_added_keys += 1
            added_by_part.setdefault(
                part_number, []).append(f"{code} => {value}")

    # 出力 or Dry-run結果表示
    if args.dry_run:
        print("[DRY-RUN] 追記予定の集計:")
        print(f"  新規PartNumber数: {total_new_parts}")
        print(f"  追加キー総数:     {total_added_keys}")
        if args.verbose:
            for pn, items in added_by_part.items():
                print(f"\n[PartNumber: {pn}] 追加 {len(items)} 件")
                for line in items:
                    print(f"  - {line}")
        return 0

    if total_new_parts or total_added_keys:
        save_json(datasheets_path, datasheets)

    print("[DONE] 自動補完 完了")
    print(f"  新規PartNumber: {total_new_parts}")
    print(f"  追加キー総数  : {total_added_keys}")
    if args.verbose and added_by_part:
        for pn, items in added_by_part.items():
            print(f"\n[PartNumber: {pn}] 追加 {len(items)} 件")
            for line in items:
                print(f"  - {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
