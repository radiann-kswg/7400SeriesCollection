# 2026-06-15 全カテゴリ デモ回路資料生成 + KiCAD スケマティック再生成

## 目的

- 入手済み7400シリーズIC（約162件）のうちデモ資料未作成分（109件）について、`usage/{カテゴリ}/{型番}/01_basic_function_demo.md` を一括生成する。
- 既存スクリプト `generate_usage_samples_owned_01_04.py`（カテゴリ01〜04限定）の対象を全カテゴリ（01〜18、99_other）に拡張した新スクリプトを作成し実行。
- 生成した demo MD をもとに `generate_pcb_demo_projects.py` を再実行し、KiCAD ライブラリシンボルを組み込んだスケマティックに更新。

## 変更点

| ファイル / フォルダ | 操作 | 備考 |
|---|---|---|
| `scripts/generate_usage_samples_all_categories.py` | **新規作成** | 全カテゴリ対応の demo MD 一括生成スクリプト |
| `usage/` 配下 106件の `01_basic_function_demo.md` | **新規作成** | スクリプトにより自動生成（53件は既存のためスキップ） |
| `usage/99_other/74x33/01_basic_function_demo.md` | **手動作成** | overview 未登録のため手動（SN74ALS33AN, オープンコレクタNORバッファ） |
| `usage/99_other/74x276/01_basic_function_demo.md` | **手動作成** | overview 未登録のため手動（SN74276N, クワッドJK-FF） |
| `usage/99_other/74x1034/01_basic_function_demo.md` | **手動作成** | overview 未登録のため手動（SN74AS1034AN, 3-stateバッファ） |
| `pcb-demo/` 配下 820ファイル | **再生成（上書き）** | 実シンボル20件 + テキスト注釈142件 |

## 実行コマンド（再現手順）

```powershell
# 1. 全カテゴリ demo MD 生成（TIデータシートPDF自動ダウンロード、ピン抽出付き）
python3 scripts/generate_usage_samples_all_categories.py --download --sleep 0.5

# 2. KiCAD プロジェクト再生成（既存を上書き）
python3 scripts/generate_pcb_demo_projects.py --apply --overwrite

# 特定部品のみ再実行する場合
python3 scripts/generate_usage_samples_all_categories.py --download --part 74x74
python3 scripts/generate_pcb_demo_projects.py --apply --overwrite --part 74x74
```

## 検証結果

### demo MD 生成（`generate_usage_samples_all_categories.py`）

| 区分 | 件数 |
|---|---:|
| 新規書込（`[書込]`） | 106 |
| スキップ（既存、`--force` なし） | 53 |
| ピン情報スタブ（PDF 未抽出） | 133 |
| エラー | 0 |

- ピン抽出成功: TI SN74* の PDF からは `pypdf` でピン機能表を自動抽出。
- ピン抽出失敗（スタブ）: TI 以外のメーカー品、DL 不可の型番、"Pin Functions" 表が検出できなかった場合。

### KiCAD スケマティック再生成（`generate_pcb_demo_projects.py --apply --overwrite`）

| 区分 | 件数 |
|---|---:|
| 生成ファイル総数 | 820 |
| 実ライブラリシンボル使用（`kicad_sch_gen.py`） | 20 |
| テキスト注釈（demo MD の配線情報を回路図に埋め込み） | 142 |
| テンプレートスタブ（情報なし） | 0 |

- 実シンボル対応型番: `kicad_sch_gen.py` 内 `PART_TO_KICAD_SYM` dict の47件のうち、demo MD が存在した20件。

## 発生した問題と対処

| 問題 | 対処 |
|---|---|
| Windows ターミナル（CP932）で `UnicodeEncodeError`（print 文の em ダッシュ `—`） | `generate_usage_samples_all_categories.py` の該当 print を ASCII ハイフン `-` に修正 |
| 74x33 / 74x276 / 74x1034 が `overview/7400_series_ic_overview.json` 未登録のためスクリプトで処理不可 | 3ファイルを直接 Python で手動生成 |

## 残課題

- **133件のピン情報スタブ**: ピン表が `- ピン配置: 要一次資料確認` のまま。TI symlink でも DL 不可の型番、または PDF 内の "Pin Functions" 表が正規表現にマッチしなかった部品。一次資料を確認次第、各 `01_basic_function_demo.md` を手動更新してください。
- **74x33 / 74x276 / 74x1034 が overview 未登録**: `overview/7400_series_ic_overview.json` にエントリがないため、スクリプト再実行時にこれらはスキップされます。overview への追記はユーザー判断で。
- **KiCAD 実シンボル非対応品**: `PART_TO_KICAD_SYM` に未登録の型番（142件）はテキスト注釈形式。KiCAD で本格的に使用する場合はシンボルの手動配置が必要。
- **PCB レイアウト**: `.kicad_pcb` はテンプレート（外形のみ）。部品配置・配線・DRC はユーザー手動作業。
