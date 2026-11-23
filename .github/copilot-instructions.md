# GitHub Copilot 向けの入口 — 7400 シリーズ IC Collection Database

このリポジトリの指示は、ルートの [`AGENTS.md`](../AGENTS.md) にまとめてある（全エージェント共通の単一の正本）。**作業の前に必ず `AGENTS.md` を読み、それに従うこと。** 回答は日本語で行う。

- Copilot のコーディングエージェント・コードレビュー・VS Code（`AGENTS.md` を読む設定）は、ルートの `AGENTS.md` を直接読む。このファイルは、`AGENTS.md` を読まない Copilot の機能のための入口として置いている。
- このファイルに共通の指示を書き足さない。指示を変えるときは `AGENTS.md` を直す。
- Copilot での対話型ファクトチェックは [`.github/prompts/factcheck-interactive.prompt.md`](prompts/factcheck-interactive.prompt.md)（VS Code の Agent チャットで `#factcheck-interactive 74x00`）。手順と信頼度の基準は `AGENTS.md` の「対話型ファクトチェック手順」。
