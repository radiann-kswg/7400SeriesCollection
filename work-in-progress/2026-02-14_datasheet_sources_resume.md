# 2026-02-14 datasheet_sources 再開メモ

## 目的

- 旧ローカル環境セッション（.work-in-progress/2026-02-14_session-log.md）の続きとして、
  `datasheets/datasheet_sources.json` の URL 検証の「未解決42件」を扱える状態にする。
- 将来的な自動化のため、検証結果を機械的に処理できる形（JSON）で残す。

## 現状（ログからの引き継ぎ）

- TI symlink URL を埋めた 168 件のうち、成功 126 / 失敗 42。
  - 404: 41
  - 非PDF（Content-Type が text/html）: 1（SN74S280N）

## 今回やったこと

- `scripts/check_datasheet_sources.py` を改修し、レポートJSONに **成功だけでなく失敗も1件ずつ構造化して記録**するようにした。
  - `Items[].Result` = `OK|FAIL|SKIP`
  - 失敗は `ErrorType / Error / HttpStatus(HTTPErrorの場合)` を保持
  - 集計用に `OkCount/FailCount/SkipCount` を追加

## 再現コマンド

- TI symlink のみ検証（失敗も含めた構造化レポート生成）
  - `python3 scripts/check_datasheet_sources.py --skip-empty --only-ti-symlink --strict-mime --report .temp/datasheet_fetch/report_ti_resume_v2.json`

## 次にやること（未解決の扱い方）

- 404 の 41件は、どちらかの方針が必要。
  - A) TI公式の別URL（製品ページ/別命名のPDFなど）を手で登録する
  - B) `Url` を空に戻して「要手動確認」にする（候補URLは Notes に残す等）
- SN74S280N（text/html）は URL候補の見直しが必要（symlink 先がPDFではない）。
