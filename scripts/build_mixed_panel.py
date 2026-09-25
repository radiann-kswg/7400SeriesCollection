#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_mixed_panel.py — 異なる型番のSpecimen Tileを2x2混載パネルにする（Phase 2 / R6検証）

KiCAD同梱pythonで実行する（KiKit APIとpcbnewを使用）:
    & 'C:\Program Files\KiCad\10.0\bin\python.exe' scripts\build_mixed_panel.py ^
        --name commons_gates 74x00 74x08 74x10 74x21

- 入力: pcb-demo/_carrier/tiles/{型番}/{型番}_tile.kicad_pcb（生成済みであること）
- 出力: pcb-demo/_carrier/panels/{name}/{name}_panel.kicad_pcb
        {name}_bom.csv（各タイルBOMをリネーム規則適用でマージ）
- 配置: 2x2（引数順に 左上A・右上B・左下C・右下D）、V-cut x=中央/y=中央
- リファレンス/ネットは「{接頭辞}_元名」にリネーム（A_SW1 等。D5の機械的付与を維持）
- CPLはパネルpcbから kicad-cli pcb export pos で別途出力し、列名を整形する
  （本スクリプトは kicad-cli を呼ばない。gen後に PowerShell 側で実行する）
"""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

import pcbnew
from kikit.panelize import Panel, Origin

ROOT = Path(__file__).resolve().parents[1]
CARRIER = ROOT / "pcb-demo" / "_carrier"
TILE_MM = 50          # タイル外形（正方形）
BASE_MM = 50          # パネル左上のシート座標
PREFIX = "ABCD"


def fmm(v):
    return pcbnew.FromMM(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="パネル名（出力ディレクトリ名）")
    ap.add_argument("parts", nargs=4, help="型番4つ（左上・右上・左下・右下の順）")
    args = ap.parse_args()

    out_dir = CARRIER / "panels" / args.name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_pcb = out_dir / f"{args.name}_panel.kicad_pcb"

    panel = Panel(str(out_pcb))
    ref_map = []  # (part, prefix)
    for n, part in enumerate(args.parts):
        src = CARRIER / "tiles" / part / f"{part}_tile.kicad_pcb"
        if not src.exists():
            sys.exit(f"error: {src} がありません（先に generate_specimen_tile.py を実行）")
        row, col = divmod(n, 2)
        dest = pcbnew.VECTOR2I(
            fmm(BASE_MM + TILE_MM * col + TILE_MM / 2),
            fmm(BASE_MM + TILE_MM * row + TILE_MM / 2),
        )
        prefix = PREFIX[n]
        panel.appendBoard(
            str(src), dest, origin=Origin.Center,
            netRenamer=lambda _, orig, p=prefix: f"{p}_{orig}",
            refRenamer=lambda _, orig, p=prefix: f"{p}_{orig}",
            inheritDrc=(n == 0),  # KiKitは複数ボードのDRCルールマージ非対応。全タイル同一proなので先頭のみ継承
        )
        ref_map.append((part, prefix))

    panel.addVCutV(fmm(BASE_MM + TILE_MM))
    panel.addVCutH(fmm(BASE_MM + TILE_MM))
    panel.save()
    # Specimen.pretty の参照。tiles/ と panels/ は同じ深さなので先頭タイルの表をそのまま使える
    shutil.copy(CARRIER / "tiles" / args.parts[0] / "fp-lib-table", out_dir / "fp-lib-table")

    # BOM マージ（タイルBOMの Designator 列に接頭辞を付けて結合）
    bom_rows, header, merged = [], None, {}
    for part, prefix in ref_map:
        bom = CARRIER / "tiles" / part / f"{part}_bom.csv"
        if not bom.exists():
            sys.exit(f"error: {bom} がありません（kicad-cli sch export bom で先に出力）")
        with open(bom, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        if header is None:
            header = rows[0]
        des_i = [i for i, h in enumerate(rows[0]) if "designator" in h.lower()]
        if not des_i:
            sys.exit(f"error: {bom} に Designator 列がありません: {rows[0]}")
        di = des_i[0]
        for r in rows[1:]:
            if not r or not r[di].strip():
                continue
            r = list(r)
            r[di] = ",".join(f"{prefix}_{d.strip()}" for d in r[di].split(","))
            # 同一部品（Designator 以外の列が一致）は1行にまとめる。JLCPCB の BOM は部品ごと1行
            key = tuple(v for i, v in enumerate(r) if i != di)
            if key in merged:
                merged[key][di] += "," + r[di]
            else:
                merged[key] = r
                bom_rows.append(r)
    out_bom = out_dir / f"{args.name}_bom.csv"
    with open(out_bom, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL, lineterminator="\n")
        w.writerow(header)
        w.writerows(bom_rows)

    print(f"panel : {out_pcb.relative_to(ROOT)}")
    print(f"bom   : {out_bom.relative_to(ROOT)} ({len(bom_rows)} 行)")
    print("layout: " + " / ".join(f"{pfx}={part}" for part, pfx in ref_map))
    print("次: kicad-cli pcb drc と export pos（CPL）をパネルpcbに対して実行")


if __name__ == "__main__":
    main()
