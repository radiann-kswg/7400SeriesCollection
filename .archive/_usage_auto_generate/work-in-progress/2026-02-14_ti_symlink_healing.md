# 2026-02-14 TI symlink URL healing (lit/ds/symlink)

## 目的

- `datasheets/datasheet_sources.json` の TI `https://www.ti.com/lit/ds/symlink/` リンクについて、404 等で到達できないものを保守的な候補生成で自動回復し、残りを手動対応へ渡せる形に整理する。
- PDF 本体は Git 管理外前提のため、URL/メタ情報（FinalUrl/ContentType/ContentLength/CheckedAt 等）で再現性を確保する。

## 対象

- TI symlink 168件（既存の検証対象一式）
- 直近フォーカス: 旧 FAIL 27 を「追加候補で自動回復できる分だけ回復」→ `--update` で `datasheet_sources.json` へ反映

## 実装（スクリプト）

- 変更ファイル: [scripts/check_datasheet_sources.py](../scripts/check_datasheet_sources.py)

追加した主な機能（保守的）:

- TI symlink の追加候補生成
  - 末尾 suffix strip（既存）
  - ExactPartNumber から base stem 抽出し、`<base>a.pdf` / `a|b|c` 近傍を試す
  - `sn74* -> sn54*` エイリアス候補
  - `sn74hNN... -> sn74NN...` の限定エイリアス（`h` の次が数字の時のみ）
  - `--ti-fallback-gpn`: `https://www.ti.com/lit/gpn/<stem>` を追加候補にする
- 反復検証の効率化
  - `--only-fails-from-report <report.json>`: 既存レポートの FAIL のみ再チェック
  - `--quiet`: OKの逐次出力を抑制
  - `--write-report-every N`: 中間レポートを定期的に書き出して長時間実行を安定化
- 参考情報付与
  - `--ti-check-product-page`: FAIL の場合に `https://www.ti.com/product/<base>` の HTTP status をレポートへ付与
  - `--ti-product-page-datasheet`: 製品ページHTML中の明示的 `...pdf` を候補に追加（best-effort）。現状、効果は限定的。

## 実行ログ/レポート

- レポート類は `.temp/datasheet_fetch/` に出力（Git管理外想定）
- 旧 FAIL 27 の再検証（update 実行含む）:
  - `.temp/datasheet_fetch/report_ti_recheck_prev27_update.json`
  - 結果: Total 27 / OK 13 / FAIL 14

製品ページ有無の参考レポート:

- `.temp/datasheet_fetch/report_ti_with_product_status.json`
  - 旧 FAIL 27 のうち TiProductHttpStatus は概ね 404（=製品ページが見つからない/型番体系が異なる可能性）

## `datasheet_sources.json` 反映状況

- 変更ファイル: [datasheets/datasheet_sources.json](../datasheets/datasheet_sources.json)
- `--update --heal-ti-symlink-url` により、到達できた候補へ `Url` を置換したエントリがある。
  - 例: `SN74H04N -> .../sn7404.pdf`
  - 例: `SN74HC573N -> .../sn74hc573a.pdf`
  - 例: `SN74ALS05N -> .../sn74als05a.pdf`
  - 例: `SN74ALS33N -> .../sn54als33a.pdf`（sn54 エイリアス）

## 残FAIL（14件）

旧 FAIL 27 のうち、追加候補を試しても到達できなかった ExactPartNumber:

- SN74H30N
- SN74HC30N
- SN74LS34N
- SN74LS36N
- SN74ALS1000AN
- SN74ALS1032AN
- SN74S113N
- SN74ALS1244AN
- SN74LS170N
- SN74LS189AN
- SN74LS274N
- SN74LS295BN
- SN74LS381AN
- SN74ALS714N

次工程の方針（案）:

- まずは各FAILについて `AttemptedUrls` をレポートから確認し、TI内の別系列PDF（統合データシート/旧DocID形式など）への手動登録が妥当か判断する。
- 追加規則を入れる場合も「無制限探索をしない」方針を維持し、根拠のある近傍候補だけを追加する。

## 非TI向け（半自動）: ローカルPDFフォールバック

- `datasheets/_download/` に既にPDFがあるが、公式URLを安全に自動生成できないメーカー（NXP/TOSHIBA/RENESAS/UTC等）向けに、[scripts/check_datasheet_sources.py](../scripts/check_datasheet_sources.py) にローカルPDF検索オプションを追加。
- 使い方（例）:
  - `python3 scripts/check_datasheet_sources.py --allow-local-as-ok --local-pdf-root datasheets/_download --update`
    - Url が空/URLプローブ失敗でも、ファイル名一致（ExactPartNumberの保守的variants）でPDFが見つかれば OK とする。
    - `--update` 時は `LocalPath/LocalBytes/LocalSha256/LocalCheckedAt` を sources JSON に追記。

## 再現コマンド（例）

- TI symlink のみチェック（長時間向け）:
  - `python3 scripts/check_datasheet_sources.py --only-ti-symlink --strict-mime --quiet --write-report-every 25`
- FAILだけ再チェック:
  - `python3 scripts/check_datasheet_sources.py --only-ti-symlink --strict-mime --quiet --only-fails-from-report .temp/datasheet_fetch/report_ti_recheck_prev27_update.json`

※ 実際の運用では `--timeout` や `--write-report-every` を調整する。
