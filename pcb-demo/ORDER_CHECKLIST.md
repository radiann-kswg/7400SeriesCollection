# JLCPCB 発注チェックリスト

**全項目が `[x]` になるまで発注しない。** これが発注ゲート（[`REQUIREMENTS.md`](REQUIREMENTS.md) D11）。

1 回の発注ごとに本ファイルをコピーし、`_panel/{パネル名}/ORDER.md` として結果を記録する。本ファイル自体はテンプレートなので `[ ]` のまま維持する。

- 対象パネル:
- 発注日:
- 発注枚数:

---

## A. 設計データ

- [ ] 対象全型番について **VCC / GND のピン位置を一次資料で確認**した（→ REQUIREMENTS §2.5、`_carrier/README.md` §6.4）
- [ ] 対象全型番について**ピン数**を確認した（接点マッピング §6.1 の入力になる）
- [ ] 対象全型番の `_carrier/pinspec/{型番}.json` があり、各ピンの方向を一次資料で確認した（信頼度 85% 以上、または目視確認済み）
- [ ] 電源接点に I/O セルが載っていない（載っていると VCC/GND が LED とスイッチに繋がる）
- [ ] 未使用接点の I/O セルが DNP 指定されている
- [ ] 出力接点の `SWk`・`R(20+k)` が DNP、入力接点は全実装になっている
- [ ] リファレンス指定子が命名規則どおり（`Dk` / `Rk` / `R(20+k)`）
- [ ] `Rd` が 1kΩ（省略・470Ω 以下への変更がない。→ `_carrier/README.md` §2.2 安全規則）
- [ ] シルクの型番・機能名・ピン名が対象 IC と一致している
- [ ] SMD 部品がすべて**上面**にある（Economic 組立の制約）
- [ ] スイッチのランド・位置決め穴を MSS12C02LS の寸法図で照合した（`_carrier/Specimen.pretty` は MSK12C02 の流用）

## B. 検証

- [ ] ERC エラー 0（`run_erc` または `scripts/verify_kicad_sch.py`）
- [ ] 回路図と基板の等価性 0（`kicad-cli pcb drc --schematic-parity`）
- [ ] DRC エラー 0（`run_drc`。JLCPCB の設計ルールを適用した状態で）
- [ ] Edge.Cuts が閉じている
- [ ] V-cut 線がパネルを端から端まで直線で貫いている
- [ ] 銅箔が基板端から 0.5mm 以上離れている
- [ ] 最小パターン幅が 0.25mm 以上

## C. 部品

- [ ] 全部品に LCSC 部品番号（`Cxxxxx`）が付いている
- [ ] Basic / Extended の別を確認した（`search_jlcpcb_parts` / `get_jlcpcb_part`）
- [ ] Extended 部品の種類数と追加費用（$3/種）を把握している
- [ ] 全部品の在庫を確認した（発注直前に再確認すること）
- [ ] 抵抗値が 1kΩ / 4.7kΩ の 2 種類に収まっている

## D. 製造データ

- [ ] Gerber + ドリルを出力した（`export_gerbers` / `export_drill`）
- [ ] BOM を出力した（`export_bom`）。列名が `Comment` / `Designator` / `Footprint` / `LCSC Part #`
- [ ] CPL を出力した（`export_pos`）。列が `Designator` / `Mid X` / `Mid Y` / `Layer` / `Rotation`
- [ ] **CPL に BOM へ無い designator が含まれていない**（ソケット `U1`・ピンヘッダ `J1`・基準マーク・取付穴を除外したか）
- [ ] CPL の回転を目視確認した（特に LED の極性とスイッチの向き）
- [ ] Gerber ビューアで全レイヤーを目視確認した

## E. 発注

- [ ] 組立サービスが **Economic**（SMD・上面のみ）になっている
- [ ] 発注枚数が最小数量 5 枚以上
- [ ] **見積もり総額が予算内**（パイロットは 30,000 円 → REQUIREMENTS §5）
- [ ] JLCPCB の部品マッチング結果を確認し、未マッチの部品がない
- [ ] 手はんだ部品（DIP-20 ソケット × タイル数、2 ピンヘッダ × タイル数）を別途手配した

## F. 発注後

- [ ] 見積もり内訳（基板 / 組立 / 部品 / 送料 / 関税）を `_panel/{パネル名}/ORDER.md` に記録した
- [ ] 実機検証の結果を記録し、不具合があれば `REQUIREMENTS.md` と `_carrier/README.md` に反映して版を上げた

---

## 関連ドキュメント

- 要件定義: [`REQUIREMENTS.md`](REQUIREMENTS.md)
- 共通キャリア設計仕様: [`_carrier/README.md`](_carrier/README.md)
