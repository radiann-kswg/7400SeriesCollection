# 2026-11-22 新規入手 5 型番の pinspec 作成とオープンコレクタ出力の扱い（D29）

## 目的

若松通商で注文した 5 型番（SN74284N / SN74285N / SN74LS385N / SN7489N / SN74LS227N）について、Specimen Tile 生成の前段となるピン仕様（REQUIREMENTS §4.1）を一次資料で確認し、`pcb-demo/_carrier/pinspec/` に記録する。あわせて、これまで全部 DNP としていたオープンコレクタ出力の表示方法を決める。

## 変更点

- 入手履歴（`getstarting/`、git 追跡外）: 5 型番の `GetStartingECS_JP` に「若松通商」を追加
- `datasheets/7400_series_ic_datasheet_collection_status.json`: `autofill_gottenitems.py` → `sort_datasheet_by_partnumber.py` で 5 型番を追加（コミット 82e46f0）
- `pcb-demo/_carrier/pinspec/`: `74x284.json` / `74x285.json` / `74x385.json` / `74x89.json` / `74x227.json` を新規作成
- REQUIREMENTS D29（新設）: `open_collector` 出力接点を LED のみのセルとし、`active_low` 出力と同じ赤 LED + プルアップ配線（+5V → Dk → Rk 4.7kΩ → 接点 k、点灯 = L）にする
- `scripts/generate_specimen_tile.py`: `cells()` で `open_collector` を `out` に、`components()` で OC 出力の LED をプルアップ配線に変更。docstring と回路図注記を更新
- `pcb-demo/REQUIREMENTS.md`（版 0.11、D29 追加、§2.3・§4.1 更新）、`pcb-demo/_carrier/README.md`（版 0.7、§6.2 更新）

## 一次資料（目視確認）

| 汎用型番 | PDF | ピン数 | VCC/GND | 主な出力 | 信頼度 |
|---|---|---|---|---|---|
| 74x284 / 74x285 | `datasheets/_download/TI(TexasInstruments)/SN74284,SN74285.pdf`（Revised December 1983） | 16 | 16 / 8 | Y: オープンコレクタ | ピン 95% / 出力形式 92% |
| 74x385 | `datasheets/_download/TI(TexasInstruments)/SN74LS/SN74LS385.PDF`（D2412, Revised April 1985） | 20 | 20 / 10 | SUM: トーテムポール | ピン 95% / 出力形式 90% |
| 74x89 | `datasheets/_download/TI(TexasInstruments)/SN7489.pdf`（D1416, Revised February 1984） | 16 | 16 / 8 | Q̄: オープンコレクタ（反転） | ピン 93% / 出力形式 98% |
| 74x227 | `datasheets/_download/TI(TexasInstruments)/SN74LS/SN74LS224,SN74LS227,SN74LS228.PDF`（Revised March 1985、Rochester 表紙付き） | 20 | 20 / 10 | Q: オープンコレクタ、IR/OR: トーテムポール | ピン 95% / Q 98% / IR・OR 93% |

全項目が信頼度 85% 以上のため自動確認とした。レンダリング PNG（`datasheets/.cache/pdf_render/`）は確認後に削除済み。

## 実行コマンド（再現手順）

```powershell
.\.venv\Scripts\python.exe scripts\render_datasheet_pages.py --pdf '<PDF>' --pages 1-4 --dpi 150 --outdir datasheets/.cache/pdf_render/<名前>
# pinspec 読み込みとセル種別の確認（生成は行わない）
& 'C:\Program Files\KiCad\10.0\bin\python.exe' -c "import sys; sys.path.insert(0,'scripts'); import generate_specimen_tile as g; print(g.cells(g.load_part('74x89')))"
```

## 検証結果

- 変更前（HEAD）と変更後のスクリプトで、既存 pinspec 14 型番の `components()` の出力が完全一致（OC 接点を持たないため影響なし）
- 新規 5 型番のセル種別:
  - 74x284 / 74x285: 出力（OC・赤プルアップ）接点 13〜16
  - 74x89: 出力（OC・赤プルアップ）接点 5・7・13・15
  - 74x385: 出力（白）接点 2・9・12・19、クロック接点 1
  - 74x227: 出力（OC・赤プルアップ）接点 12・13・14・16、出力（白）接点 3・17、クロック接点 4・19
- タイルの生成・ERC/DRC は未実施

## 残課題

- R10: クロックセルの配置は接点 11 でしか検証されていない。74x385（接点 1）と 74x227（接点 4・19）はこのままでは DRC が通らない可能性が高い
- D29 の実機確認: OC オフ時の漏れ電流（データシート上 最大 40〜100 µA）で LED がごく薄く光らないか
- `datasheets/datasheet_sources.json` の 5 型番の Notes が「PDF未保存」のままだが、PDF は `_download/` に保存済み
- `scripts/sort_datasheet_by_partnumber.py` が保存時にファイル末尾の改行を落とす（今回は手で補った）
- 74x227 の PDF ファイル名にカンマが含まれる（74x284/285 も同様）。`render_datasheet_pages.py --part` の自動探索で見つかるかは未確認
