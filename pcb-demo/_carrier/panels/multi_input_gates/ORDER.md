# JLCPCB 発注チェックリスト — multi_input_gates パネル

**全項目が `[x]` になるまで発注しない。** これが発注ゲート（[`REQUIREMENTS.md`](../../../REQUIREMENTS.md) D11）。

本ファイルは `pcb-demo/ORDER_CHECKLIST.md` のコピー（2026-11-28 作成）。7400sCCP8 の動作確認用に、同じ発注でまとめて出す 4 パネルの 1 枚（REQUIREMENTS D33）。

- 対象型番（パネルの場合はパネル名と配置）: multi_input_gates（100×100mm、2×2、V-cut、カテゴリ 02_nand_and_gates） A=74x11（左上） / B=74x30（右上） / C=74x132（左下） / D=74x20（右下）
- 同じ発注のパネル: data_selectors / octal_buffers / decoders / multi_input_gates（D33）
- 発注の前提: テスト発注その1（74x00 / 74x244 / 74x273 の単体タイル）の実機動作確認が済んでから発注する（2026-09-25 ユーザー決定）
- 発注日:
- 発注枚数:

---

## A. 設計データ

- [x] 対象全型番について **VCC / GND のピン位置を一次資料で確認**した（→ REQUIREMENTS §2.5、`_carrier/README.md` §6.4） （74x11 は VCC=接点20（ピン14）・GND=接点7、74x30 は VCC=接点20（ピン14）・GND=接点7、74x132 は VCC=接点20（ピン14）・GND=接点7、74x20 は VCC=接点20（ピン14）・GND=接点7。いずれも角ピンで非標準なし）
- [x] 対象全型番について**ピン数**を確認した（接点マッピング §6.1 の入力になる） （74x11=DIP-14、74x30=DIP-14、74x132=DIP-14、74x20=DIP-14）
- [x] 対象全型番の `_carrier/pinspec/{型番}.json` があり、各ピンの方向を一次資料で確認した（信頼度 85% 以上、または目視確認済み） （2026-11-28 作成。信頼度 74x11 95%、74x30 95%、74x132 95%、74x20 95%。各 source 欄に DocID と確認日）
- [x] 電源接点に I/O セルが載っていない（載っていると VCC/GND が LED とスイッチに繋がる） （generate_specimen_tile.py の生成ログで確認）
- [x] 未使用接点の I/O セルが DNP 指定されている （生成ログの DNP 数で確認）
- [x] 出力接点の `SWk`・`R(20+k)` が DNP、入力接点の `Rk`（Rled）・`Dk`（LED）が DNP になっている（D25。入力接点はスイッチのみ） （BOM の数: LED・Rled = 出力数、SW・Rd = 入力数で一致）
- [x] リファレンス指定子が命名規則どおり（`Dk` / `Rk` / `R(20+k)`） （generate_specimen_tile.py の機械的付与。パネルでは A_〜D_ 接頭辞）
- [x] `Rd` が 220Ω（省略・220Ω 未満への変更がない。→ D16、`_carrier/README.md` §2.2 安全規則） （C22962）
- [x] シルクの型番・機能名・ピン名が対象 IC と一致している （panel_top.png を目視、2026-11-28）
- [x] SMD 部品がすべて**上面**にある（Economic 組立の制約） （CPL の Layer が全件 Top）
- [ ] スイッチのランド・位置決め穴を MSS12C02LS の寸法図で照合した（`_carrier/Specimen.pretty` は MSK12C02 の流用。R8。パイロットでは本項目を意図的に未チェックとし実発注を最終確認とする方針を採った場合、その旨を記録する）

## B. 検証

- [x] ERC エラー 0（`scripts/verify_kicad_sch.py`、または KiCAD MCP が使える環境では `run_erc`） （kicad-cli sch erc --severity-all、4 タイル 0 errors / 0 warnings、2026-11-28）
- [x] 回路図と基板の等価性 0（`kicad-cli pcb drc --schematic-parity`） （4 タイルとも footprint errors 0）
- [x] DRC エラー 0（`kicad-cli pcb drc --severity-all`。JLCPCB の設計ルールを適用した状態で。silk 系 warning の許容は REQUIREMENTS §9 R9 に従う） （4 タイルとも violations 0 / unconnected 0（warning 含む）。パネルも violations 0）
- [x] Edge.Cuts が閉じている （DRC で確認）
- [ ] （パネル発注時のみ）V-cut 線がパネルを端から端まで直線で貫いている
- [ ] 銅箔が基板端から 0.5mm 以上離れている
- [ ] 最小パターン幅が 0.25mm 以上

## C. 部品

- [x] 全部品に LCSC 部品番号（`Cxxxxx`）が付いている （C14663 / C2290 / C23162 / C22962 / C3008585）
- [x] Basic / Extended の別を確認した（JLCONE の部品検索、または `https://jlcpcb.com/partdetail/{Cxxxxx}`。Cowork では Web 調査で代替する） （2026-09-25 Web 調査。`Claude outputs/2026-09-25_order_gate_parts_check.md`。クロックセルなし）
- [x] Extended 部品の種類数と追加費用（$3/種）を把握している （1 種（C3008585）= $3）
- [ ] 全部品の在庫を確認した（発注直前に再確認すること。LCSC 在庫と JLCPCB 組立在庫は別なので両方見る）
- [x] 抵抗値が 220Ω（Rd）/ 4.7kΩ（Rled）の 2 種類に収まっている（D16。クロックセルの RCK=10kΩ は別枠） （クロックセルなし）

## D. 製造データ

- [x] Gerber + ドリルを出力した（`kicad-cli pcb export gerbers` / `drill`） （gerbers/ と multi_input_gates_panel_gerbers.zip）
- [x] BOM を出力した（`kicad-cli sch export bom`）。列名が `Comment` / `Designator` / `Footprint` / `LCSC Part #` （build_mixed_panel.py がタイル BOM をマージ。同一部品は 1 行、5 行）
- [x] CPL を出力した（`kicad-cli pcb export pos`）。列が `Designator` / `Mid X` / `Mid Y` / `Layer` / `Rotation` （kicad-cli pcb export pos → multi_input_gates_cpl.csv に整形）
- [x] **CPL に BOM へ無い designator が含まれていない**（ソケット `U1`・ピンヘッダ `J1`・基準マーク・取付穴を除外したか） （BOM 90 = CPL 90、完全一致）
- [ ] CPL の回転を目視確認した（特に LED の極性とスイッチの向き。SOT-23-5 は JLCPCB 側で +180° 補正が必要になりやすい）
- [ ] Gerber ビューアで全レイヤーを目視確認した

## E. 発注

> 異種 4 型番の面付けは JLCPCB で「Different Design」扱いの追加料金になる。Economic 組立が異種面付けパネルを受けるかは JLCONE で確認すること。混載パネルの実見積もりは 2026-11-28 時点で未取得。

- [ ] 組立サービスが **Economic**（SMD・上面のみ）になっている
- [ ] 発注枚数が最小数量 5 枚以上
- [ ] **見積もり総額が予算内**（パイロットは 30,000 円 → REQUIREMENTS §5。4 パネル同時発注の予算はユーザー判断）
- [ ] JLCPCB の部品マッチング結果を確認し、未マッチの部品がない
- [ ] 手はんだ部品（DIP-20 ソケット × 4、2 ピンヘッダ × 4。パネル 1 枚あたり）を別途手配した

## 未チェック項目の補足

- R8（スイッチ寸法）はパイロット方針どおり実発注を最終確認とするため意図的に未チェック。
- V-cut・銅箔と基板端の距離・最小パターン幅・CPL 回転・Gerber ビューア目視は未実施。
- 在庫は発注直前に LCSC と JLCPCB 組立在庫の両方で再確認する。
- REQUIREMENTS R12（2026-11-28 レビュー）: TTL 品を挿すと出力 H の白 LED が暗いか消えて見え、負論理出力の赤 LED は非選択でも薄く点くことがある。発注前にテスト発注その 1 のタイルで見え方を確かめることを推奨（対策の要否はユーザー判断）。

## F. 発注後

- [ ] 見積もり内訳（基板 / 組立 / 部品 / 送料 / 関税）を本ファイルに記録した
- [ ] 実機検証の結果を記録し、不具合があれば `REQUIREMENTS.md` と `_carrier/README.md` に反映して版を上げた
- [ ] R8（MSS12C02LS のランド・外形・3D モデル）について、実装された現物での確認結果を記録した

---

## 関連ドキュメント

- 要件定義: [`REQUIREMENTS.md`](../../../REQUIREMENTS.md)
- 共通キャリア設計仕様: [`_carrier/README.md`](../../README.md)
