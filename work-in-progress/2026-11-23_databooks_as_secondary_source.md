# 2026-11-23 データブック（二次資料）の活用と NSC データブックのパス変更

## 目的

メーカー刊行データブックの全冊スキャンを `datasheets/_download/{メーカー}/_databooks/` に収録し始めた。これを個別データシートの二次資料として照合に使えるようにする。あわせて、National の 1987 ALS/AS Logic Databook を `NSC(NationalSemiconductor)/` 直下から `NSC(NationalSemiconductor)/_databooks/` へ移したので、参照パスを直す。

## 変更点

### パスの修正

`datasheets/_download/NSC(NationalSemiconductor)/1987_ALS_AS_Logic_Databook.pdf` → `datasheets/_download/NSC(NationalSemiconductor)/_databooks/1987_ALS_AS_Logic_Databook.pdf`

- `datasheets/datasheet_sources.json`（74x1804 / DM74AS1804N の `LocalPath`。移動後の sha256 は記録値と一致）
- `pcb-demo/_carrier/pinspec/74x1804.json`（`source.file`）
- `usage/02_nand_and_gates/74x1804/74x1804.md`（5 か所）
- `work-in-progress/2026-11-22_new_parts_pinspec_d29.md`（移動した旨を追記。当時のパスは残した）

### 指示書

- `AGENTS.md`: ディレクトリ構造に `{メーカー}/_databooks/` と `NSC(NationalSemiconductor)/` を追加。「一次資料の優先順位」の 3 番目にデータブックを入れ、「データブック（二次資料）の使い方」節を新設（使う場面・`[x]` にしてよい条件・ページ探し・レンダリング・引用の書き方・索引の更新・`datasheet_sources.json` への登録条件）
- `.github/copilot-instructions.md`: 上と同じ内容を反映
- `CLAUDE.md` / `.github/prompts/factcheck-interactive.prompt.md`: ファクトチェック手順の対象確認とレンダリングにデータブックの確認を追加

### スクリプト（`scripts/render_datasheet_pages.py`）

- `--find TEXT`: レンダリングせず、OCR テキスト層から TEXT（品番など）を含む PDF ページ番号を表示する。空白と大文字小文字は無視
- 100 ページを超える PDF は `--pages` なしだとエラーで止まる（データブックを全ページ PNG 化しないため）

### 索引（Git 管理外）

- `datasheets/_download/NSC(NationalSemiconductor)/_databooks/README.md` を新規作成（TI 側の README と同じ形式。DM74AS1804 のページを記載）

## データブックでの相互確認（2026-11-23）

TI 側 README の索引にある 13 型番について、データブックの該当ページを PNG 化（140 dpi）して目視し、既存の pinspec（個別 PDF で照合済み）のピン配置と突き合わせた。データブックは `datasheets/_download/TI(TexasInstruments)/_databooks/` 以下。

| 汎用型番 | データブック | 印刷ページ / PDF ページ | 改訂 | 結果 | 読み取り信頼度 |
|---|---|---|---|---|---|
| 74x82 | 1985 The TTL Data Book Vol. 2 | 3-330 / 381 | REVISED DECEMBER 1983（個別 PDF と同じ） | 全 14 ピン一致（VCC=4、GND=11、6〜9 は NC） | 98% |
| 74x265 | 1985 The TTL Data Book Vol. 2 | 3-878 / 929 | REVISED DECEMBER 1983（個別 PDF は MARCH 1988） | 全 16 ピン一致 | 98% |
| 74x295 | 1985 The TTL Data Book Vol. 2 | 3-940 / 991 | REVISED DECEMBER 1983（個別 PDF は MARCH 1988） | 全 14 ピン一致（SN74LS295B） | 97% |
| 74x385 | 1985 The TTL Data Book Vol. 2 | 3-1050 / 1101 | D2412, REVISED APRIL 1985（同じ） | 全 20 ピン一致 | 97% |
| 74x89 | 1986 The TTL Data Book Vol. 4 | 5-3 / 346 | D1416, REVISED FEBRUARY 1984（同じ） | 全 16 ピン一致。オープンコレクタ出力 | 98% |
| 74x189 | 1986 The TTL Data Book Vol. 4 | 5-19 / 362 | D2417, REVISED FEBRUARY 1985（同じ） | 全 16 ピン一致。LS189A は 3 ステート・反転出力 | 98% |
| 74x284 / 74x285 | 1986 The TTL Data Book Vol. 4 | 5-33 / 376 | REVISED DECEMBER 1983（同じ） | 両型番とも全 16 ピン一致 | 98% |
| 74x1000 | 1986 ALS/AS Logic Data Book | 2-825 / 864 | D2661, REVISED MAY 1986（同じ） | 全 14 ピン一致 | 98% |
| 74x1002 | 1986 ALS/AS Logic Data Book | 2-829 / 868 | D2661, REVISED MAY 1986（同じ） | 全 14 ピン一致 | 98% |
| 74x1032 | 1986 ALS/AS Logic Data Book | 2-849 / 888 | D2661, REVISED MAY 1986（同じ） | 全 14 ピン一致 | 98% |
| 74x1804 | 1986 ALS/AS Logic Data Book | 2-893 / 932 | REVISED MAY 1986（TI SN74AS1804 / SN74ALS1804A） | 全 20 ピン一致（VCC=5、GND=15）。所蔵品の原典は National 側 | 98% |
| 74x227 | 1986 LSI Logic Data Book | 2-13 / 46 | REVISED MARCH 1985（同じ） | 全 20 ピン一致。LS227 はオープンコレクタ出力 | 97% |
| 74x60 | 1985 The TTL Data Book Vol. 2 | 3-245 / 296 | REVISED DECEMBER 1983 | ページの所在だけ確認（pinspec なし。タイル対象外） | — |

- スキャンは鮮明で、ピン配置図は大きく判読しやすい。不一致は 0 件
- pinspec のある 13 型番は、各 `pcb-demo/_carrier/pinspec/{型番}.json` の `notes` に相互確認の記録を 1 行追記した（`pins`・`source`・`confidence` は変更なし）
- TI 側 README の索引は、PDF ページ番号のある 13 行すべてが正しいことを確認した
- レンダリング PNG（`datasheets/.cache/pdf_render/*_databook/`）は確認後に削除

## 実行コマンド（再現手順）

```powershell
$py = ".\.venv\Scripts\python.exe"
# ページ探し（OCR テキスト層）
& $py scripts\render_datasheet_pages.py --pdf "datasheets/_download/TI(TexasInstruments)/_databooks/1986_TI_The_TTL_Data_Book_Vol_4.pdf" --find SN7489
# 該当ページだけ PNG 化
& $py scripts\render_datasheet_pages.py --pdf "datasheets/_download/TI(TexasInstruments)/_databooks/1986_TI_The_TTL_Data_Book_Vol_4.pdf" --pages 346 --dpi 140 --outdir datasheets/.cache/pdf_render/74x89_databook
# 検査
& $py scripts\check_demo_pin_tables.py
```

## 検証結果

- `--find SN7489`（1986 Vol. 4）→ PDF 13・346〜351 ページ。`--find DM74AS1804`（National 1987）→ PDF 7・424・638 ページ。索引の値と一致
- `--pages` なしで 445 ページのデータブックを指定 → エラーで終了（終了コード 1）。`--part 74x00 --pages 1` は従来どおり動作
- pinspec 13 件は変更前に `json.dumps(indent=2, ensure_ascii=False)` での往復が元ファイルと完全一致することを確認してから追記
- `check_demo_pin_tables.py` → エラー 0 件

## 残課題

- データブックのページ索引（`_databooks/README.md`）は Git 管理外。追跡できる機械可読の索引（品番 → データブック・ページ）は作っていない。型番が増えて `--part` から自動でデータブックのページまで出したくなったら追加する
- TI 側 README で PDF ページが空欄の行（1976 TTL、1988 Standard TTL）は未確認。1976 年版は OCR テキスト層が無く `--find` が効かない
- 74x93（所蔵 DM74LS93N）: National の LS 系データブックが未収録。収録すれば TI 資料による照合（信頼度 80%・ユーザー確認待ち）を解消できる
- 74x5074（所蔵 74F5074N）・74x280（所蔵 74F280BN）: Signetics の FAST データブックが未収録（TI 側 README に 1990 FAST Supplement の該当ページのメモあり）。保存先フォルダ名は未定
- 74x1000 の M74ALS1000P（三菱）は未照合のまま
- 今回の 13 型番の `usage/{カテゴリ}/{型番}/{型番}.md` のファクトチェック項目（真理値表・定格・電気特性）は未着手。個別 PDF とデータブックの両方で実施できる
