# 2026-05-30 pcb-demo/ KiCAD環境セットアップ

## 目的

- 入手済み7400シリーズIC（164件）について、KiCAD 10.0.3 での最小デモPCB制作環境を整備する。
- `usage/` と同様のカテゴリ/パーツ番号フォルダ構成で `pcb-demo/` を作成。
- スクリプトにより `.kicad_pro` / `.kicad_sch` / `.kicad_pcb` / `.kicad_sym` / `README.md` のスタブを一括生成。

## 変更点

| ファイル | 操作 |
|---------|------|
| `pcb-demo/_templates/template.kicad_pro` | 新規作成（KiCAD 10プロジェクトテンプレート） |
| `pcb-demo/_templates/template.kicad_sch` | 新規作成（空回路図テンプレート、KiCAD 8互換形式） |
| `pcb-demo/_templates/template.kicad_pcb` | 新規作成（50×50mm外形付きPCBテンプレート） |
| `pcb-demo/_templates/template.kicad_sym` | 新規作成（カスタムシンボルスタブ） |
| `pcb-demo/_templates/README_template.md` | 新規作成（READMEテンプレート） |
| `scripts/generate_pcb_demo_projects.py` | 新規作成（プロジェクト自動生成スクリプト） |
| `.vscode/tasks.json` | KiCAD CLI関連タスクを追記 |
| `.github/copilot-instructions.md` | `pcb-demo/` セクションとKiCADガイドラインを追記 |

## 実行コマンド

```powershell
# dry-run（変更なし・一覧表示）
python3 scripts/generate_pcb_demo_projects.py

# 実際に生成
python3 scripts/generate_pcb_demo_projects.py --apply

# 特定カテゴリのみ
python3 scripts/generate_pcb_demo_projects.py --apply --category 01_buffers_inverters

# 既存を上書き
python3 scripts/generate_pcb_demo_projects.py --apply --overwrite
```

## 前提

- KiCAD 10.0.3: `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`
- テンプレートは KiCAD 8 互換形式（version 20231120 / 20240108）で作成
  - KiCAD 10 が初回保存時に自動アップグレードする
- 入手済みIC: 164件（`getstarting/7400_series_ic_collection_acquisition_history.json`）
- 対象: `GottenItemsMN_CMOS` / `GottenItemsMN_TTL` / `GottenItemsMN_Other` いずれかに値がある行

## 検証結果

- `python3 scripts/generate_pcb_demo_projects.py` (dry-run) で実行確認

## 残課題

- 各プロジェクトの回路図に実際のKiCAD標準ライブラリシンボル（74xx）を配置する作業はユーザー手動
- ピン配置・真理値表は `usage/{category}/{74xNN}/` の一次資料確認チェックリストを参照
- Gerber出力/DRC自動実行が必要な場合は `kicad-cli pcb export gerbers` を tasks.json に追加
