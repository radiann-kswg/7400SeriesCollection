#!/usr/bin/env python3
"""
audit_kicad_coverage.py

入手済み全 74xx 型番について、実シンボル回路図を生成できるか
（74xx.kicad_sym に対応シンボルが存在するか）を一覧する監査スクリプト。

オーバーライド表 (PART_TO_KICAD_SYM) と自動探索 (kicad_lib.discover_symbol)
の両方を考慮し、解決できた型番／できなかった型番を報告する。
KiCAD ライブラリが存在する環境（通常 Windows）で実行すること。

  python scripts/audit_kicad_coverage.py
  python scripts/audit_kicad_coverage.py --csv coverage.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
HISTORY_JSON = BASE_DIR / "getstarting" / "7400_series_ic_collection_acquisition_history.json"

import importlib.util as _u
_spec = _u.spec_from_file_location("kicad_sch_gen", SCRIPT_DIR / "kicad_sch_gen.py")
_g = _u.module_from_spec(_spec)
_spec.loader.exec_module(_g)


def owned_parts() -> list[str]:
    hist = json.loads(HISTORY_JSON.read_text(encoding="utf-8"))
    out = []
    for e in hist:
        if e.get("GottenItemsMN_CMOS") or e.get("GottenItemsMN_TTL") or e.get("GottenItemsMN_Other"):
            out.append(e["PartNumber"])
    return sorted(set(out))


def resolve(part: str) -> tuple[str, str | None]:
    """(source, symbol) を返す。source は override / discover / none。"""
    if part in _g.PART_TO_KICAD_SYM:
        return ("override", _g.PART_TO_KICAD_SYM[part][1])
    if _g._kl is not None:
        sym = _g._kl.discover_symbol(_g._lib_path("74xx"), part)
        if sym:
            return ("discover", sym)
    return ("none", None)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    args = ap.parse_args()

    if not _g.KICAD_LIB_DIR.exists():
        print(f"[WARN] KiCAD ライブラリが見つかりません: {_g.KICAD_LIB_DIR}")
        print("       自動探索は機能しません（オーバーライド表のみ判定）。")

    parts = owned_parts()
    rows = []
    n_override = n_discover = n_none = 0
    for p in parts:
        src, sym = resolve(p)
        rows.append((p, src, sym or ""))
        if src == "override":
            n_override += 1
        elif src == "discover":
            n_discover += 1
        else:
            n_none += 1

    covered = n_override + n_discover
    print("=" * 60)
    print(f"入手済み型番: {len(parts)}")
    print(f"  実シンボル化可能: {covered}  ({covered * 100 // max(len(parts),1)}%)")
    print(f"    - override 指定 : {n_override}")
    print(f"    - 自動探索      : {n_discover}")
    print(f"  未対応(テキスト版): {n_none}")
    print("=" * 60)
    if n_none:
        print("未対応（74xx.kicad_sym に該当シンボル無し）:")
        print("  " + ", ".join(p for p, s, _ in rows if s == "none"))

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["part", "source", "symbol"])
            w.writerows(rows)
        print(f"\nCSV 出力: {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
