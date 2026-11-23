# 2026-11-23 手創り屋で追加注文した 30 実型番の反映

## 目的

手創り屋（2026-11-23 16:02 JST 注文、受領未確認）で追加注文した 25 汎用型番・30 実型番について、入手履歴（`getstarting/`、git 追跡外。ユーザーが記録済み）と `datasheets/datasheet_sources.json`（GPT 側が PDF の保存と同時に記録済み）に合わせて、リポジトリの残りのデータを更新する。

## 変更点

- `datasheets/7400_series_ic_datasheet_collection_status.json`
  - `autofill_gottenitems.py` で新規 12 汎用型番・30 実型番を追加（値は暫定の「(収集予定:…)」「(保留)」）
  - `sort_datasheet_by_partnumber.py` で並べ直し（180 件）
  - `datasheet_sources.json` の LocalPath と LocalSha256 で保存済み PDF を確認できた 29 実型番を、暫定値からメーカー名に更新
  - 暫定値のまま残したもの: `HD74LS114P`（Renesas の資料が未入手で、sources にも LocalPath なし）
  - 自動推定の誤りを訂正: `SN74LS461NS` は TI でなく MMI（SkinnyDIP 表記）、`74LS190N` は Raytheon、`M74LS133P` は Mitsubishi、`74F521PC` は Fairchild
- `usage/**/74xNN.md`: `auto_check_factcheck.py --part` を 25 汎用型番に実行。13 ファイルで「対象の実型番を決める」と「データシート参照先」のチェック項目を自動確認に更新（ほかの 12 汎用型番は更新済みで変更なし）
- `datasheets/datasheet_sources.json`: GPT 側の記録をそのまま使い、このセッションでは書き換えていない

## 一次資料の確認（このセッションで実施）

- 新規保存の PDF 19 本と既存 PDF の 1 ページ目で、型番・資料番号・改訂を読み、sources の記録と食い違いが無いことを確認した
- 画像主体の PDF 3 本（SN74S260 / SN74LS592,593 / SN74LS688）は 1 ページ目を目視した。資料番号は SDLS208 / SDLS004 / SDLS008（D2617）、改訂は December 1983 / January 1981 / January 1981 のいずれも Revised March 1988
- 注意が要る資料:
  - `SN74LS12.PDF` は Rochester Electronics が TI の資料から起こした版（TI 公式配信ではない）
  - `SN74LS396.PDF` は 4 ページ版で、PDF メタデータが ALLDATASHEET 経由の転載を示す
  - `SN74LS279A.PDF` は A 付きの型番だけを載せる。実型番 `SN74LS279N` は、sources で 1981 TI データブックに紐づいている
- 新規のデータブック 3 冊（Mitsubishi 1985 / MMI 1981 / Raytheon 1977）はテキスト層で型番を確認した（M74LS133P は PDF 168〜169 ページ、SN54/74LS461 は 187〜190 ページ、LS190 は 145〜153 ページ）。ピン配置などの目視照合は未実施

## 実行コマンド（再現手順）

```powershell
.\.venv\Scripts\python.exe scripts\autofill_gottenitems.py
.\.venv\Scripts\python.exe scripts\sort_datasheet_by_partnumber.py
# 収集状況の暫定値を sources の記録に合わせてメーカー名へ（.temp の一時スクリプト。sources は読むだけ）
foreach ($p in '74x12','74x76',... ) { .\.venv\Scripts\python.exe scripts\auto_check_factcheck.py --part $p }
```

`sort_datasheet_by_partnumber.py` は保存時に末尾の改行を落とすため、そのあとの更新スクリプトで改行を補った。

## 検証結果

- 入手履歴の全実型番（180 汎用型番）が収集状況 JSON に載っている。PartNumber は昇順で重複なし
- 収集状況 JSON は CRLF のまま。差分は追加のみ（既存値の変更なし）
- 29 実型番の PDF について、sources の LocalSha256 とファイルの SHA-256 が一致

## 残課題

- `HD74LS114P`: Renesas の資料が未入手
- `TC74HC242P`（既存の「(収集予定:TOSHIBA)」）: 1986 Toshiba データブックに載っているか未確認（同じ冊子で TC74HC107P / 390P / 646P は記録済み）
- 新しい 25 汎用型番のうち、Specimen Tile の pinspec が無い型番は 74x93 を除いてすべて未作成。対象の絞り込み（レア度が高いもの、DIP-20 に収まるもの、クロックセルの接点条件）はユーザー判断待ち
- ピン配置などの usage チェック項目（目視照合）は未着手
- 受領後に現物の刻印を入手履歴の実型番と照合する（Raytheon 表記の 74LS190N、MMI の SN74LS461NS は特に）

## 引継ぎ（Codex コードレビュー・次の作業者向け）

### レビューしてほしい点

- 収集状況 JSON の暫定値の更新が、`datasheet_sources.json` の LocalPath・メーカー表記と食い違っていないか（更新に使った一時スクリプトは `.temp/` にあり Git 管理外。メーカー表記は sources が `TI(TexasInstruments)` 形式、収集状況が `TI(Texas Instruments)` 形式で、空白の入れ方が違う）
- `datasheet_sources.json` は GPT 側が記録した内容をそのままコミットに含めている。このセッションでは 25 汎用型番のエントリ追加・追記だけで、既存エントリの変更・削除は無いことを確認した。Url に第三者ミラー（`media.onzuu.com` など）が含まれる。Notes にその旨が書かれているかを見てほしい
- usage の 13 ファイルは `auto_check_factcheck.py` の機械的な更新だけ（ピン配置などの目視項目は `- [ ]` のまま）

### 資料の出所について注意が要るもの（TI 公式配信ではない）

- `SN74LS12.PDF`: Rochester Electronics が TI の資料から起こした版
- `SN74LS396.PDF`: 4 ページ版。PDF メタデータが ALLDATASHEET 経由の転載を示す
- `SN74LS279A.PDF`: A 付きの型番だけを載せる。実型番 `SN74LS279N` は sources で 1981 TI データブックに紐づいている

### 確認が途中のもの

- Mitsubishi 1985・MMI 1981・Raytheon 1977 の 3 冊は、テキスト層で型番を確認しただけ。ピン配置などの目視照合は未実施（対象: `M74LS133P`、`SN74LS461NS`、`74LS190N`）
- 3 冊とも `_databooks/README.md` の索引がまだ無い（README は Git 管理外）。ページは本ログの「一次資料の確認」を参照
- 受領後に、現物の刻印を入手履歴の実型番と照合する（Raytheon 表記の `74LS190N`、MMI の `SN74LS461NS` は特に。MMI の NS は 24 ピンの Skinny DIP で、TI の NS パッケージとは別物）

### 次の作業（ユーザー判断待ち）

- Specimen Tile 用 pinspec の作成。新しい 25 汎用型番のうち pinspec があるのは 74x93 だけ。対象の絞り込みが要る
  - 候補: レア度の高い 74x1004（SSR）、74x114・74x133・74x260（SR+）、74x242（SuperRare）
  - 制約: DIP-20 ソケットに入らない型番は対象外。クロックセルは接点 1・11 だけ対応（R10）。接点 20 が電源でない型番は R11 で止まる
  - 進め方: 計画を示して合意を取ってから、一次資料を目視して pinspec を書く（REQUIREMENTS §4.1）
