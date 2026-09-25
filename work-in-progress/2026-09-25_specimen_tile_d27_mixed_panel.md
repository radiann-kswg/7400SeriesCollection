# 2026-09-25 Specimen Tile D27（穴配置・説明シルク）と混載パネル commons_gates

「7400 IC PCB回路制作 その３」（Halvan 切断で中断）の続き。引き継ぎは `Claude outputs/D27_pending_handoff.md`。

## その３で完了済み（コミット a6ff6eb まで）
- ツーリングホール Ø1.152mm NPTH ×2 を (2.5, 2.5) / (48.5, 48.5) に追加（D27(b)）
- `wrap_cjk()` による和文の折り返し
- pinspec 74x08 / 74x10 / 74x21（TI SN74HC、信頼度95%）
- `scripts/build_mixed_panel.py`（KiKit で異種4型番の 2×2 パネル + BOM マージ）
- 部品区分・在庫の Web 調査（`Claude outputs/2026-09-25_order_gate_parts_check.md`）

## このセッションで実施
1. 引き継ぎパッチを適用: 説明シルクを横帯（y16.8〜20.2mm）へ全幅・中央寄せで移し、右中央の M2（MTG2）を戻して左右対称にした（D27(a)(c)）
2. 再生成後の DRC で新たに見つかった2件を修正（`generate_specimen_tile.py`）
   - `silk_overlap`: 説明の英文行と和文行が重なった。和文グリフは公称サイズより背が高いため、行ピッチを 1.25 → 1.45mm にした
   - `extra_footprint` ×4（MTG1/MTG2/TH1/TH2）: 回路図に無い穴が等価性チェックに引っかかった。穴に `FP_BOARD_ONLY` を付けた（REQUIREMENTS R9 に記載されていた「MTG の extra footprint 通知」もこれで解消）
3. 74x00/74x08/74x10/74x21 を再生成し、ERC 0 errors / 0 warnings、DRC violations 0 / unconnected 0 / footprint errors 0 を確認（`--severity-all --schematic-parity`）
4. `build_mixed_panel.py`: BOM の同一部品をまとめて1行にするよう修正（旧: タイルごとに行が分かれ 20 行 → 新: 5 行）
5. commons_gates パネルを再構築: DRC 0、Gerber・ドリル・ZIP・CPL を再出力、BOM↔CPL 96件一致、全件 Top、panel_top.png を目視
6. `REQUIREMENTS.md` v0.9 に D27 を追加。`ORDER_CHECKLIST.md` テンプレートを D16/D26/D27 と Cowork の手順に合わせて修正
7. `pcb-demo/_carrier/panels/commons_gates/ORDER.md` を作成（22項目チェック済み、15項目は未チェック）

## 実行コマンド（Windows）
```powershell
& 'C:\Program Files\KiCad\10.0\bin\python.exe' scripts\generate_specimen_tile.py 74x00 74x08 74x10 74x21
kicad-cli sch erc --severity-all -o <tile>\erc.rpt <tile>.kicad_sch
kicad-cli pcb drc --severity-all --schematic-parity -o <tile>\drc.rpt <tile>.kicad_pcb
& 'C:\Program Files\KiCad\10.0\bin\python.exe' scripts\build_mixed_panel.py --name commons_gates 74x00 74x08 74x10 74x21
kicad-cli pcb export pos --format csv --units mm --side front --exclude-dnp -o pos_raw.csv <panel>.kicad_pcb
kicad-cli pcb export gerbers -l 'F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts,User.Comments' -o gerbers\ <panel>.kicad_pcb
kicad-cli pcb export drill --generate-map --map-format gerberx2 -o gerbers\ <panel>.kicad_pcb
```
タイル BOM は回路図の差分が UUID だけだったため再出力していない。

## 残課題
- 74x244 / 74x273 は D27 の変更後に再生成していない（テスト発注その1の発注データがあるため、ユーザー判断待ち）
- ORDER.md の未チェック項目: V-cut 目視、銅箔と基板端の距離、最小パターン幅、CPL 回転、Gerber ビューア、在庫の直前再確認、E/F 節
- JLCONE で実見積もり（異種面付けの Different Design 料金、Economic 組立が異種面付けパネルを受けるか）
- C25804（RCK 10kΩ）の LCSC 在庫切れはクロックセル付き型番に影響（commons_gates には無関係）

## 追記1（同日、D28 同カテゴリ混載パネル）

ユーザー依頼: 74x244 と 74x273 を、同カテゴリのロジック IC 3 つずつと併せて新規設計する。

- 型番の選定: 入手履歴にあり、TI SN74HC の PDF が手元にあるもの
  - 01_buffers_inverters: 74x244 + 74x04 / 74x14 / 74x125（74x04・74x14 はパイロット12型番の一部）
  - 05_flipflops_latches: 74x273 + 74x374 / 74x574 / 74x377（いずれも CLK がピン11 = 接点11）
- pinspec 新規 8 件（TI SN74HC データシート p.3 を目視、信頼度 95%）: 74x04 / 14 / 125 / 74 / 595 / 374 / 574 / 377
  - 74x125・74x374・74x574・74x595 の出力は 3 ステートとして tri_state にした（データシートの I/O 欄は Output）
  - 74x74 の反転出力は KiCad のオーバーバー記法 `~{1Q}` とし active_low（赤 LED）
- 74x74（クロックが接点3・17）と 74x595（接点15・16）は、クロックセルが隣接セルと衝突して DRC 80 件前後になり断念（REQUIREMENTS R10）。pinspec は残し、生成物は削除
- 74x595 は和文説明が長く、横帯 3 行の assert にも掛かった（R10 対応時に説明の短縮も必要）
- `build_mixed_panel.py`: `fp-lib-table` を先頭タイルからコピーするよう修正（無いと Specimen ライブラリの lib_footprint_issues が 70 件前後出る）
- タイル BOM の出力手順を `.temp/export_bom.cmd` に置き、既存 74x273_bom.csv とバイト一致することを確認してから全型番に使用:
  `kicad-cli sch export bom --fields "Reference,Value,Footprint,LCSC Part #" --labels "Designator,Comment,Footprint,LCSC Part #" --group-by "Value,Footprint,LCSC Part #" --sort-field Reference --ref-range-delimiter "" --exclude-dnp`
- 検証結果
  - タイル: 74x244 / 04 / 14 / 125 は ERC 0・DRC 0（warning 含む）。74x273 / 374 / 574 / 377 は ERC 0・errors 0、warning は型番シルクと D11 の重なり 4 件と UG11 NC の net_conflict 1 件（R9 既知）
  - buffers_drivers: DRC 0、BOM 5 行 / 112 件 = CPL 112 件、全件 Top
  - octal_dff: DRC warning 16 件（上記×4）、BOM 10 行 / 164 件 = CPL 164 件、全件 Top
  - 両パネルとも panel_top.png を目視
- `ORDER.md` を両パネルに作成（22 項目チェック済み / 15 項目未チェック）

### 残課題（追加）
- 74x244 / 74x273 のタイル単位の発注データ（tiles/{型番}/ の Gerber ZIP・CPL・ORDER.md）はテスト発注その1の記録として残してあり、再生成後の基板とは一致しない
- octal_dff の型番シルクが D11 に一部隠れる（R9）。気になるならクロックタイルだけ型番の位置を変える
- R10: クロックセル配置の一般化（74x74 / 74x595 / 74x164 / 74x393 などパイロット残りに必要）
