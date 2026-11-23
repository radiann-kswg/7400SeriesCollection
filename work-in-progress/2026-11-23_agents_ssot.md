# 2026-11-23 エージェント指示の SSOT 化（Codex・Claude・Copilot 共通）

## 目的

- Codex でのコードレビューを含め、複数のエージェントが同じ指示を読むようにする。
- `AGENTS.md` と `.github/copilot-instructions.md` の二重管理（同じ内容を両方に反映する運用）をやめ、`AGENTS.md` を単一の正本にする。
- KiCad MCP が Cowork（Claude デスクトップ）と Codex からも使えるようになったことを反映する。

## 変更点

- `AGENTS.md`
  - 冒頭に「指示ファイルの構成（SSOT）」: エージェントごとに読むファイル、共通の指示は `AGENTS.md` だけに書くこと、判断と残課題は作業ログに残すこと。
  - `CLAUDE.md` にあった「Agent skills」（Issue tracker・Triage labels・Domain docs）を移した（Codex の mattpocock-skills も読めるように）。
  - `.github/copilot-instructions.md` にだけあった内容のうち、共通のもの（データシートの保管ルール、Python の拡張性の指針）を取り込んだ。
  - 「対話型ファクトチェック手順」を共通の 6 段（信頼度の上げ下げの基準を含む）にし、`CLAUDE.md` から移した。
  - KiCAD MCP の登録先（Claude Code・Codex・Claude デスクトップ）。
  - 末尾に Codex のコードレビュー用の「Code Review Rules」（データの整合性、一次資料、Specimen Tiles）。
- `CLAUDE.md`: 先頭に `@AGENTS.md`。Claude での実行方法（PNG を Read で目視、Cowork では PDF を直接目視してよい）だけを残した。
- `.github/copilot-instructions.md`: `AGENTS.md` への案内と Copilot のプロンプトの場所だけにした（961 行 → 7 行）。Copilot のコーディングエージェントとコードレビューはルートの `AGENTS.md` を読む。
- `README.md`・`scripts/seed_datasheet_sources_from_usage_and_history.py`（コメント）: 参照先を `.github/copilot-instructions.md` から `AGENTS.md` に変更。

`.github/copilot-instructions.md` にだけあり、取り込まなかったもの: コーディングパターン集（JSON の読み書きの例と、中身の無い型番正規化の雛形）、`.work-in-progress/` の扱い（フォルダが無い）、スクリプトの細かい説明（各スクリプトの冒頭にある）。

## 検証

- 旧 `.github/copilot-instructions.md` の見出しと本文を `AGENTS.md` と突き合わせ、共通の決まり（基本ルール、スキーマ、一次資料照合、禁止事項、pcb-demo の設計ルール）が `AGENTS.md` にあることを確認した。
- `copilot-instructions` を参照している箇所を検索し、`AGENTS.md` 自身の説明以外に残っていないことを確認した（作業ログと `.archive/` は記録なので変えていない）。

## 残課題

- 7400SeriesProcessor のサブモジュール `collection/` を、この変更を push したあとで更新する（Processor 側の参照先は `collection/AGENTS.md` の「対話型ファクトチェック手順」に変更済み）。
- `.github/prompts/factcheck-interactive.prompt.md` は Copilot のプロンプトとして残した。信頼度の基準を `AGENTS.md` と二重に持っているので、次に直すときは `AGENTS.md` を指す形にする。
