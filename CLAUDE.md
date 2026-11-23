@AGENTS.md

# CLAUDE.md — Claude 向けの補足（7400 シリーズ IC Collection Database）

> 共通の指示は [`AGENTS.md`](AGENTS.md) にだけ書く（全エージェント共通の単一の正本）。このファイルには Claude の道具でしか通じないことだけを書く。
> 両ファイルに矛盾が生じた場合はこの `CLAUDE.md` を優先する。共通の指示を変えるときは `AGENTS.md` を直し、ここには写さない。

---

## Claude での対話型ファクトチェック

手順と信頼度の基準は `AGENTS.md` の「対話型ファクトチェック手順」。Claude では次のように行う。

- `render_datasheet_pages.py` で PNG 化したページ（`datasheets/.cache/pdf_render/`）を Read（画像表示）で目視する。Cowork では PDF をステージして Read のページ指定で直接目視してもよい（PNG 化を省ける）。文字層から抜いた数値も、該当ページを目視してから採用する。
- `render_datasheet_pages.py` は PyMuPDF が要る。Windows では `python3` を `.venv\Scripts\python.exe` に読み替える。
