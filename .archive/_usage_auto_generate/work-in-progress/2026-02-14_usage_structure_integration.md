# 2026-02-14 usage 構造の統合（cheatsheets + 回路例）

## 目的

- `usage` 配下の `cheatsheets`（自動生成チートシート）と、`usage` 直下の `74x*` フォルダ（手書き回路例）を統合し、
  `usage/{カテゴリ名}/{パーツ番号}/**.md` の形へ移行する。
- それに伴い、usage を参照するスクリプト群のパス前提を更新する。

## 変更点

- usage 構造を移行
  - 旧: `usage` 配下 `cheatsheets/{category}/{74xNN}.md`
  - 新: `usage/{category}/{74xNN}/{74xNN}.md`
  - 旧: `usage` 直下の `74x141/*`, `74x181,182/*`
  - 新: それぞれのカテゴリ配下へ統合（例: `usage/06_encoders_decoders/74x141/`）
- `.github/copilot-instructions.md` の一次資料優先順位を更新
  - ① `scripts/check_datasheet_sources.py --download` で再現可能な Web 自動取得 PDF
  - ② `datasheets/_download/` の手動入手 PDF（整合確認用）
  - ③ Web 検索 + 手動確認情報（URL/DocID/Rev/参照日）
- scripts のパス前提を更新
  - `scripts/generate_usage_cheatsheets.py`: 出力先を `usage/` 配下の新構造に変更
  - `scripts/seed_datasheet_sources_from_usage_and_history.py`: 新構造から Markdown を探索
  - `scripts/append_usage_factcheck_footer.py`: 新構造での対象探索（チートシート本体は除外）
- 追加
  - `scripts/migrate_usage_structure.py`（dry-run 付き移行スクリプト）

## 実行コマンド

- 移行 dry-run:

```powershell
& "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/migrate_usage_structure.py
```

- 移行適用:

```powershell
& "D:/VisualStudio Code Userfile/7400SeriesCollection/.venv/Scripts/python.exe" scripts/migrate_usage_structure.py --apply
```

- 旧 `cheatsheets` フォルダ削除（usage配下）:

```powershell
Remove-Item -Recurse -Force "usage\\cheatsheets"
```

## 検証

- `scripts/generate_usage_cheatsheets.py` 実行で例外なし（既存ページはスキップ、カテゴリ index は更新）
- `scripts/seed_datasheet_sources_from_usage_and_history.py` dry-run 実行で例外なし
- `scripts/append_usage_factcheck_footer.py` dry-run 実行で例外なし

## 残課題

- 既存の手書き回路例（74x141 系）は一次資料照合済みか再確認が必要（特にピン配置など断定事項）。
- `usage/index.md` のナビゲーションは必要に応じて改善（カテゴリ/実回路例の導線）。
