# 2026-02-15 所持IC（カテゴリ01〜04）サンプル回路解説 自動生成

## 目的

- 所持している 7400シリーズ汎用型番のうち、カテゴリ `01_buffers_inverters`〜`04_xor_xnor_gates` の各パーツについて、`usage/06_encoders_decoders/74x141` の構成を参考に「チートシート + サンプル回路解説」を揃える。
- 仕様断定は一次資料（データシートPDF）に照合し、未確認事項は書かない。

## 変更点

- スクリプト追加: [scripts/generate_usage_samples_owned_01_04.py](scripts/generate_usage_samples_owned_01_04.py)
  - 所持パーツ（カテゴリ01〜04、入手履歴ベース）を抽出
  - `usage/{category}/{74xNN}/01_basic_function_demo.md` を生成（既存は上書きしないデフォルト）
  - 可能な場合はTIのsymlink PDF等からピン配置を機械抽出して反映（抽出できない場合はスタブを生成）
- 一時作業ファイル（Git管理外想定）
  - `.temp/datasheet_fetch/` 配下にPDFを取得（必要な場合）
  - `.temp/owned_targets_01_04.json` 等の集計出力

## 実行コマンド

- 集計（任意）
  - `python .temp/report_owned_targets_01_04.py`
- 生成（PDFダウンロード込み）
  - `python scripts/generate_usage_samples_owned_01_04.py --download`

## 検証結果

- 生成後に以下を確認する:
  - `usage/01_buffers_inverters`〜`usage/04_xor_xnor_gates` 配下に `01_basic_function_demo.md` が追加されていること
  - 追加されたMD内で、ピン配置が抽出できたものはピン表が埋まっていること
  - 抽出できなかったものは「要一次資料」スタブであること（断定を避ける）

## 残課題

- メーカー別PDF（特にTOSHIBA系）でピン配置がテキスト抽出できない場合の取り扱い方針（OCR導入の是非など）
- TI以外の公式URL/DocID/Rev/参照日の体系的な補完
