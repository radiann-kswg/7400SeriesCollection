# JLCPCB 発注チェックリスト — 74x00

**全項目が `[x]` になるまで発注しない。** これが発注ゲート（[`REQUIREMENTS.md`](../../../REQUIREMENTS.md) D11）。

`ORDER_CHECKLIST.md`（テンプレート）を 74x00 用にコピーしたもの。2026-09-17、D25（入力接点スイッチのみ化）
適用後の再検証・製造データ作成の結果を記録する。**D26により非パネル（1枚=1回路）で発注する**
（JLCPCB PCBAビューアでパネル化Gerberに対しBOM/CPLの自動複製が機能しなかったため）。

- 対象型番: 74x00（DIP-14、VCC=接点20 GND=接点7、入力セル8/出力セル4/DNP6、クロックセルなし）
- 基板構成: **1枚 = 1回路**（50×50mm、非パネル。[`REQUIREMENTS.md`](../../../REQUIREMENTS.md) D26。パネル化技術自体はD9・R6で確立済みだがこの発注では使用しない）
- 発注日: （未定・ユーザー記入）
- 発注枚数: （未定。JLCPCB組立の最小ロットは5枚。予算に応じてユーザー記入）

---

## A. 設計データ

- [x] 対象型番について VCC / GND のピン位置を一次資料で確認した（`_carrier/pinspec/74x00.json`。D15以前に確認済み、本セッションでは未変更）
- [x] 対象型番についてピン数を確認した（`DIP-14`。`load_part()` が生成時に検証）
- [x] `_carrier/pinspec/74x00.json` があり、各ピンの方向を一次資料で確認した
- [x] 電源接点に I/O セルが載っていない（`load_part()` が VCC/GND の一意性を生成時に検証）
- [x] 未使用接点の I/O セルが DNP 指定されている（DNP6個。本セッションBOM/DNP突合で確認）
- [x] 出力接点の `SWk`・`R(20+k)` が DNP、入力接点の `Rk`（Rled）・`Dk`（LED）が DNP になっている（D25。本セッションで実装し、`.kicad_sch` を直接パースして型番ごとに突合確認済み）
- [x] リファレンス指定子が命名規則どおり（`Dk` / `Rk` / `R(20+k)` / `SWk`。生成スクリプトが機械的に付与）
- [x] `Rd` が 220Ω（D16。470Ω 以下への変更なし。`74x00_bom.csv` で確認）
- [x] シルクの型番・機能名・ピン名が対象 IC と一致している（本セッションでJLCONEの配置プレビューを目視し、74x00は表面実装位置・ピンラベル（VCC/4B/4A/4Y/3B/3A/3Y、1A/1B/1Y/2A/2B/2Y/GND）が標準DIP配置・データシート順と一致することを確認）
- [x] SMD 部品がすべて上面にある（Economic 組立の制約。CPL の Layer 列が全行 `Top`）
- [ ] スイッチのランド・位置決め穴を MSS12C02LS の寸法図で照合した（`_carrier/Specimen.pretty` は MSK12C02 の流用）
  - **未完了・意図的に未チェック**: 端子3パッド・位置決め穴2つは純正図面（C3008585 Rev2, 2020-06-17）で確認済みだが、4隅の SH パッドと外形（F.Fab/F.CrtYd）は旧 MSK12C02 の流用値のまま（[`REQUIREMENTS.md`](../../../REQUIREMENTS.md) R8「ほぼ解決」）。**2026-09-17、ユーザーの明示判断により現物サンプルでの事前確認は行わず、本発注そのものを最終確認とする。**
  - 補足: フットプリントの `model` プロパティも `SW_SPDT_Shouhan_MSK12C02.step`（ドナー部品の3Dモデル）を指したままで、真のMSS12C02LSの3Dモデルではない。**JLCONEの配置プレビュー（3D）に表示されるスイッチの形状はドナー部品の代替形状であり、実物のMSS12C02LSの形状・寸法を示すものではない**ため、プレビュー上の見た目で現物確認の代わりにはならない。

## B. 検証

- [x] ERC エラー 0（本セッション、74x00 タイル再生成後に再実行）
- [x] 回路図と基板の等価性 0（`--schematic-parity`。既知の warning のみ、error 0）
- [x] DRC エラー 0（JLCPCB 設計ルール適用状態。severity=warning のみ、既知パターンと一致）
- [x] Edge.Cuts が閉じている（DRC の閉輪郭チェックでエラー0）
- [x] 銅箔が基板端から 0.5mm 以上離れている（DRC edge clearance ルールでエラー0）
- [x] 最小パターン幅が 0.25mm 以上（DRC track width ルールでエラー0）

## C. 部品

- [x] 全部品に LCSC 部品番号（`Cxxxxx`）が付いている（BOM 記載 5 種すべて。手はんだの `U1`・`J1` は LCSC番号なしでBOM/CPLから除外——設計上の意図どおり）
- [ ] Basic / Extended の別を確認した — **未確認**。JLCPCB の部品検索ページがJS描画のためこのセッションからは取得できなかった。JLCONE へのアップロード時に自動判定されるので、そこで確認すること（Extended 1種につき $3 追加）
- [ ] Extended 部品の種類数と追加費用（$3/種）を把握している — 上記未確認のため保留
- [ ] 全部品の在庫を確認した（発注直前に再確認すること） — LCSC在庫は2026-09-17時点の参考値（発注直前に再確認要）: SHOU HAN MSS12C02LS(C3008585) 48,145、Panasonic EVQP2R02M(C79161) 1,600、TI SN74LVC1G14DBVR(C7835) 342,890。抵抗・コンデンサ・LED(C14663/C2290/C23162/C22962/C2286/C25804/C106248)はJLCPCB Basicパーツ帯の一般部品で在庫枯渇リスクは低いと見られるが未個別確認。
- [x] 抵抗値が 220Ω（Rd）/ 4.7kΩ（Rled）の 2 種類に収まっている（D16。クロックセルの RCK=10kΩ は別枠、本型番はクロックセルなしのため該当なし）

## D. 製造データ

- [x] Gerber + ドリルを出力した（`kicad-cli pcb export gerbers`/`export drill`。**`74x00_tile.kicad_pcb`（非パネル、50×50mm）から**。ファイル: `74x00_tile_gerbers.zip`）
- [x] BOM を出力した（`kicad-cli sch export bom`。`74x00_tile.kicad_sch` から。列名 `Comment` / `Designator` / `Footprint` / `LCSC Part #`。ファイル: `74x00_bom.csv`）
- [x] CPL を出力した（`kicad-cli pcb export pos`。`74x00_tile.kicad_pcb` から。列 `Designator` / `Mid X` / `Mid Y` / `Layer` / `Rotation`。ファイル: `74x00_cpl.csv`）
- [x] CPL に BOM へ無い designator が含まれていない（`U1`・`J1`・基準マーク・取付穴を除外。本セッションで自動突合し完全一致（25件）を確認済み。Gerber・BOM・CPLとも同一の`74x00_tile`から出力しているため一致は自明）
- [x] CPL の回転を目視確認した（JLCONEの配置プレビューで、上側セル列と下側セル列のスイッチが180°の関係で対向配置されていることを確認——上下対称レイアウトとして意図どおり）
- [ ] Gerber ビューアで全レイヤーを目視確認した — Component Placementsタブ（Top）は確認済み。他レイヤー（Bottom/Mask/Silk等）は未確認。JLCONEのPCBタブで確認すること

## E. 発注（ユーザー作業）

- [ ] 組立サービスが Economic（SMD・上面のみ）になっている
- [ ] 発注枚数が最小数量 5 枚以上
- [ ] 見積もり総額が予算内（パイロットは 30,000 円 → [`REQUIREMENTS.md`](../../../REQUIREMENTS.md) §5。超過時は抵抗アレイ化→タクトスイッチのみ化→パイロット6種縮小の順に縮退）
- [ ] JLCPCB の部品マッチング結果を確認し、未マッチの部品がない
- [ ] 手はんだ部品（DIP-20 ソケット・2ピンヘッダ、各1個×発注枚数）を別途手配した

## F. 発注後（ユーザー作業）

- [ ] 見積もり内訳（基板 / 組立 / 部品 / 送料 / 関税）をこのファイルに記録した
- [ ] 実機検証の結果を記録し、不具合があれば `REQUIREMENTS.md` と `_carrier/README.md` に反映して版を上げた
- [ ] SHOU HAN スイッチ（R8）の現物確認結果——4隅SHパッド・外形が実装上問題ないか——をここに記録し、問題があれば `_carrier/Specimen.pretty` のフットプリント修正につなげる

---

## 製造データの場所

すべて `pcb-demo/_carrier/tiles/74x00/` にある（非パネル・D26のため、Gerber/BOM/CPL/KiCadソースが全て同じ場所・同じタイル基準）。

- Gerber + ドリル: `pcb-demo/_carrier/tiles/74x00/74x00_tile_gerbers.zip`
- BOM: `pcb-demo/_carrier/tiles/74x00/74x00_bom.csv`
- CPL: `pcb-demo/_carrier/tiles/74x00/74x00_cpl.csv`
- KiCad ソース: `pcb-demo/_carrier/tiles/74x00/74x00_tile.kicad_{sch,pcb,pro}`

## 関連ドキュメント

- 要件定義: [`REQUIREMENTS.md`](../../../REQUIREMENTS.md)
- 共通キャリア設計仕様: [`_carrier/README.md`](../../README.md)
- 作業ログ: [`work-in-progress/2026-09-16_specimen_tile_phase1.md`](../../../../work-in-progress/2026-09-16_specimen_tile_phase1.md)
