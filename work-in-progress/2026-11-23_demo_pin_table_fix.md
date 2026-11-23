# 2026-11-23 デモ資料のピン表と KiCad 注記の誤り修正（Issue #1）

## 目的

GitHub Issue #1（74x164 の 10 番ピン誤植と他 4 品種の同様の誤り）に対応する。デモ資料 `usage/{カテゴリ}/{型番}/01_basic_function_demo.md` のピン表は PDF からの機械抽出で、パッケージ名（FK）・I/O 種別（I / O）・説明文（Active-Low / Feedback）をピン名として取り込み、反転表記（上線）を落としていた。`pcb-demo/{カテゴリ}/{型番}/{型番}.kicad_sch`（テキスト注釈版）の【ピン配置】注記は、このピン表を写したもの。

## 一次資料での照合（2026-11-23）

ピン表のある 27 型番のうち、制御ピンを持つ 14 型番を照合した。各 PDF の Pin Configuration ページを PNG 化して目視（`.temp/render_pinpages.py`、130 dpi）。レンダリング PNG は確認後に削除済み。

| 型番 | 実型番 | 資料（`datasheets/_download/` 以下） | 結果 | 信頼度 |
|---|---|---|---|---|
| 74x164 | SN74HC164N | `TI(TexasInstruments)/SN74HC/SN74HC164.PDF` p.4（SCLS115G） | 9=/CLR、10=QE に修正 | 98% |
| 74x595 | SN74HC595 | `TI(TexasInstruments)/SN74HC/SN74HC595.PDF` p.3（SCLS041J） | 19 行→16 ピンに修正（QC〜QH、QH'、/SRCLR、RCLK、/OE、SER） | 98% |
| 74x21 | SN74HC21N | `TI(TexasInstruments)/SN74HC/SN74HC21.PDF` p.3（SCLS087F） | 3=NC、欠落していた 11=NC を追加 | 98% |
| 74x125 | SN74HC125N | `TI(TexasInstruments)/SN74HC/SN74HC125.PDF` p.3（SCLS104F） | 1/4/10/13 を /1OE〜/4OE に修正 | 98% |
| 74x126 | SN74HC126N | `TI(TexasInstruments)/SN74HC/SN74HC126.PDF` p.3（SCLS103F） | 誤りなし（OE は High アクティブ） | 98% |
| 74x74 | SN74HC74N | `TI(TexasInstruments)/SN74HC/SN74HC74.PDF` p.3（SCLS094F） | /1CLR、/1PRE、/1Q、/2Q、/2PRE、/2CLR に修正 | 98% |
| 74x240 | SN74LS240N | `TI(TexasInstruments)/SN74LS/SN74LS240.PDF` p.3（SDLS144D） | 1=/1G、19=/2G（「2G/2G」を修正） | 96% |
| 74x244 | SN74HC244N | `TI(TexasInstruments)/SN74HC/SN74HC244.PDF` p.3（SCLS130H） | 1=/1OE、19=/2OE | 98% |
| 74x245 | SN74HC245N | `TI(TexasInstruments)/SN74HC/SN74HC245.PDF` p.3（SCLS131F） | 19=/OE（上線はピン配置図で確認。表には上線なし） | 93% |
| 74x273 | SN74HC273N | `TI(TexasInstruments)/SN74HC/SN74HC273.PDF` p.3（SCLS136F） | 1=/CLR | 97% |
| 74x373 | SN74HC373N | `TI(TexasInstruments)/SN74HC/SN74HC373.PDF` p.3（SCLS140G） | 1=/OE | 98% |
| 74x238 | CD74HC238E | `TI(TexasInstruments)/CD74HC/CD74HC138,CD74HC238.PDF` p.3（SCHS147J） | 4=/G0、5=/G1（「G・G」を修正）、6=G2 | 95% |
| 74x157 | SN74HC157N | `TI(TexasInstruments)/SN74HC/SN74HC157.PDF` p.3（SCLS113F） | 1=/A/B（Ā/B）、15=/G | 96% |
| 74x393 | SN74HC393N | `TI(TexasInstruments)/SN74HC/SN74HC393.PDF` p.3（SCLS143E） | 誤りなし（CLR は High アクティブ） | 98% |

全項目が 85% 以上のため自動確認とした。反転表記はリポジトリ既存の書き方に合わせ `/` 前置（例 /CLR）。

## 変更点

- デモ資料 14 件: ピン配置節の見出しを「ピン配置（一次資料で照合済み）」にし、照合記録（資料・ページ・DocID・信頼度）と表を更新
- KiCad 注記 10 件（テキスト注釈版の 74x21 / 157 / 164 / 238 / 240 / 244 / 245 / 273 / 373 / 595）: 【ピン配置】注記の文字列だけを書き換え（下記スクリプトの `--sync-kicad --apply`）。74x125・74x74 は実シンボル回路図で、注記を持たないため対象外。`kicad-cli sch erc` で 4 件を読み込み確認（違反 0）
- `scripts/generate_pcb_demo_projects.py`: 【ピン配置】注記の整形を `format_pin_text()` に切り出し（162 型番で `build_sch_from_demo()` の出力が変更前と完全一致することを確認）
- `scripts/check_demo_pin_tables.py`（新規、標準ライブラリのみ）: デモ資料のピン表と KiCad 注記を検査。ピン数（DIP 標準ピン数・pinspec の package_pins）、範囲外・欠け・重複、不自然な名前（FK / I / O / Feedback / Active-Low / X/X）、同名の重複、pinspec との名前・反転表記の不一致、KiCad 注記とピン表の不一致を検出。`--sync-kicad --apply` で注記だけを書き換える

## 検証

- 変更前の資料に対して実行するとエラー 47 件（Issue の 5 品種と 74x240 / 244 / 273 / 238 を検出）
- 変更後: `python scripts/check_demo_pin_tables.py` → ピン表 27 件 / エラー 0 件（終了コード 0）

## 残課題

- 照合記録のないピン表 13 件（74x00 / 02 / 04 / 05 / 06 / 08 / 10 / 11 / 14 / 27 / 32 / 86 / 132。制御ピンのないゲート類）。pinspec のある 74x00 / 04 / 08 / 10 / 14 は一致を確認済み。`--show-info` で一覧表示できる
- 反転を検出できるのは pinspec のある型番だけ。pinspec のない型番は照合記録（I-UNCHK）で管理する
- `AGENTS.md` のスクリプト一覧への追記は未実施（同時刻に別セッションが AGENTS.md を編集中のため）
- Issue #1 へのコメント・クローズと commit はユーザー指示待ち
