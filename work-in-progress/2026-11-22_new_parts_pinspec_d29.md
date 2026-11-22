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

## 追記: R10（クロックセル配置）と UR/SSR 級タイルの一括生成（同日 21:00〜）

### 目的

手持ちの UR（VeryNerd）・SSR（ManiacRare）級 23 型番をタイル化する。あわせて R10（クロックセルを置ける接点が限られる）を一般化する。

### 対象の整理

| 区分 | 型番 |
|---|---|
| タイル生成済み（7） | 74x284 / 74x285 / 74x89 / 74x385 / 74x182 / 74x280 / 74x381 |
| pinspec のみ（R10 で生成停止） | 74x227（LDCK=接点4・UNCK=接点19）、74x93（CKA=接点20） |
| 対象外 | 74x181・74x841（24 ピンで DIP-20 ソケットに入らない）、74x124（VCC/GND が 2 組・外付けコンデンサと電圧入力が必要） |
| PDF 待ち（公式サイトから取得不可） | 74x23 / 60 / 82 / 189 / 265 / 295 / 1000 / 1002 / 1032 / 1804 / 5074 |
| 未入手 | 74x382（入手履歴に行はあるが実型番なし） |

`fetch_missing_datasheets.py --part` は TI が HTTP 404、onsemi（MC74F280）が PDF でなく HTML を返し、いずれも取得できなかった。

### スクリプトの変更（`scripts/generate_specimen_tile.py`）

1. D29 の実装漏れ修正: 基板配線の選択条件に `open_collector` を追加（部品のネットだけプルアップ側になり、配線が通常パターンのままで短絡していた）
2. D31: プルアップ LED セルの配線を再設計（+5V を外周レール際のビア → 裏面 u=-1.0 → D の A 側ビア、LA は u=-2.6 を迂回）
3. D30: `place_clock_cell()` の GND スタブ・LA ビア・迂回レーンを実パッド基点の局所オフセット（`nudge()`）に変更。接点 1 では LA ビアを左外周レールから離す
4. D30: `CLOCK_CONTACTS = (1, 11)` と `check_clock_contacts()` を追加。対応外の接点にクロックがある型番は生成前に停止
5. 回路図: クロックセルの列幅を 40→48 グリッドに変更（2 個以上で 74LVC1G14 の出力ピンと次セルの SWT の GND が重なり、P ネットが GND に短絡していた）
6. 説明シルクが 3 行になる場合、英文が実測で 46mm 以内なら 1 行にする（3 行目が上段ソケットのパッドに掛かるため。74x381 で発生）

### 実行コマンド

```powershell
& 'C:\Program Files\KiCad\10.0\bin\python.exe' scripts\generate_specimen_tile.py 74x284 74x285 74x89 74x385 74x182 74x280 74x381
kicad-cli sch erc --severity-all --format json -o <out> <tile>.kicad_sch
kicad-cli pcb drc --severity-all --schematic-parity --format json -o <out> <tile>.kicad_pcb
kicad-cli sch export bom ... --exclude-dnp / kicad-cli pcb export pos --format csv --side front --exclude-dnp
```

検証用の補助スクリプトは `.temp/tile_check.py`（ERC/DRC 集計）、`.temp/board_cmp.py`（基板の配線・ビア・部品位置・パッドネットの比較）、`.temp/bomcpl.py`（BOM と CPL の突き合わせ）。

### 検証結果

| 型番 | ERC | DRC（警告含む） | 等価性 | BOM / CPL |
|---|---|---|---|---|
| 74x284 | 0 | 0 | 0 | 29 / 29 一致 |
| 74x285 | 0 | 0 | 0 | 29 / 29 一致 |
| 74x89 | 0 | 0 | 0 | 29 / 29 一致 |
| 74x385 | 0 | 0 | 1（UG1 の NC ピン。既存 74x273 の UG11 と同じ既知の警告） | 41 / 41 一致 |
| 74x182 | 0 | 0 | 0 | 29 / 29 一致 |
| 74x280 | 0 | 0 | 0 | 23 / 23 一致 |
| 74x381 | 0 | 0 | 0 | 37 / 37 一致 |

既存 12 タイル（74x00/04/08/10/125/14/21/244/273/374/377/574）を変更後のスクリプトで再生成し、HEAD の基板と配線・ビア・部品位置・パッドネットが完全一致することを確認した。

### 作業ツリーの状態（未コミット）

- 既存 12 タイルの `.kicad_sch` / `.kicad_pcb` / 一部 `.kicad_pro` は検証のための再生成で、UUID と日付だけが変わった状態で残っている（形状は一致）。`git checkout` で戻すかはユーザー判断
- 診断用に生成した 74x227 / 74x74 / 74x595 のタイル（不具合を含む）は `.temp/stale_tiles/` に退避

### 残課題

- R10: 接点 1・11 以外のクロックセル（74x227・74x93・74x74・74x595 が該当）。奥行きを詰めたセルと u 反転版の配線の設計が必要
- 74x93: 手持ちは DM74LS93N（National）だが照合は TI の SN74LS93。信頼度 80% のためユーザー確認待ち
- 74x280: 74F280（NXP・onsemi）の一次資料が未入手
- PDF 待ちの 11 型番
- 74x595 の説明シルクが 4 行になり生成時のアサーションで止まる（UR/SSR 外、今回は未対応）

## 追記: 追加入手したデータシート 10 型番の照合とタイル生成（同日 21:40〜）

ユーザーが TI の原典 PDF を追加で入手（74x60 / 82 / 189 / 265 / 295 / 1000 / 1002 / 1032 / 1804）。74x23 は 2026-06 から `SN7423.PDF` が手元にあったが、前回の検索で拾えていなかった。74x5074 の PDF は見つからず未入手のまま。

### 照合結果

| 型番 | ピン数 / 電源 | 出力 | 結果 |
|---|---|---|---|
| 74x23 | 16 / 16・8 | トーテムポール | pinspec・タイル生成。エキスパンダ入力 1X / 1X̄ は nc（開放）。説明シルクは D32 で短縮 |
| 74x60 | 14 / 14・7 | エキスパンダ出力 | 対象外（7423 等のエキスパンダ入力に接続する専用品で単体では出力を表示できない） |
| 74x82 | 14 / 4・11（非標準） | トーテムポール | pinspec のみ。接点 20 に入力セルが来て左上ツーリングホールと衝突（R11）。overview の説明誤り（4-bit → 2 ビット）を silk_desc で回避 |
| 74x189 | 16 / 16・8 | 3 ステート（反転） | pinspec・タイル生成 |
| 74x265 | 16 / 16・8 | トーテムポール | pinspec・タイル生成 |
| 74x295 | 14 / 14・7 | 3 ステート | pinspec のみ（CLK が接点 15、R10） |
| 74x1000 | 14 / 14・7 | トーテムポール | pinspec・タイル生成（M74ALS1000P は未照合） |
| 74x1002 | 14 / 14・7 | トーテムポール | pinspec・タイル生成 |
| 74x1032 | 14 / 14・7 | トーテムポール | pinspec・タイル生成 |
| 74x1804 | 20 / 5・15（中央） | トーテムポール | pinspec のみ（所蔵は DM74AS1804N で TI 資料との照合のため信頼度 80%・要確認。R11 にも該当） |

### データの更新

- `datasheets/datasheet_sources.json`: PDF を保存した 14 件（上記 + 74x284 / 285 / 385 / 89 / 227）に LocalPath / LocalBytes / LocalSha256 / LocalCheckedAt を追加し、注記の「PDF未保存」を「LocalPath に保存済み（Url 先との一致は未確認）」に更新
- `datasheets/7400_series_ic_datasheet_collection_status.json`: 同 13 件を「(収集予定:TI)」→「TI(Texas Instruments)」に更新（74x1804 は所蔵型番が DM74AS1804N のため変更なし）

### スクリプトの変更

- D32: `silk_desc` / `silk_desc_jp`（pinspec の任意項目）をシルクにだけ使う
- R11: `check_corner_contact()` を追加（接点 20 が電源でない型番は生成前に停止）

### 検証結果（新規 6 タイル）

| 型番 | ERC | DRC（警告含む） | 等価性 | BOM / CPL |
|---|---|---|---|---|
| 74x23 | 0 | 0 | 0 | 25 / 25 一致 |
| 74x189 | 0 | 0 | 0 | 29 / 29 一致 |
| 74x265 | 0 | 0 | 0 | 29 / 29 一致 |
| 74x1000 | 0 | 0 | 0 | 25 / 25 一致 |
| 74x1002 | 0 | 0 | 0 | 25 / 25 一致 |
| 74x1032 | 0 | 0 | 0 | 25 / 25 一致 |

診断で生成された 74x82 のタイル（ツーリングホールと衝突）は `.temp/stale_tiles/74x82` に退避。
