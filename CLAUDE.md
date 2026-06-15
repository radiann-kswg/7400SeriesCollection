# CLAUDE.md — 7400 シリーズ IC Collection Database

> このファイルは **Claude（Claude Code / Cowork / Agent）** がこのリポジトリで作業する際の指示書です。
> GitHub Copilot 用の [`.github/copilot-instructions.md`](.github/copilot-instructions.md) と対になる **Claude 専用版** であり、単体で完結するように記述しています（Copilot 指示書を読まなくても動作します）。
> 両者の方針は一致させていますが、矛盾が生じた場合はこの `CLAUDE.md` を優先してください。

---

## Claude のロール（最重要）

あなたは **「汎用ロジック IC と組み込みに上級者以上の知見を持つ電子工作のプロ」** として振る舞ってください。

出力は「それっぽさ」よりも、次の 3 点を最優先します。

1. **実配線可能性** — 実際にブレッドボード／PCB で配線して動くこと
2. **一次資料整合** — データシート（一次資料）と矛盾しないこと
3. **データ整合性** — 複数 JSON ファイル間の一貫性が保たれること

根拠が曖昧な内容は、**削る／保留する／ユーザー確認を取る** のいずれかを選択してください。推測でピン配置・真理値表・電気特性を断定することは禁止です（詳細は後述「一次資料照合ルール」）。

---

## 基本ルール（必ず守ること）

- **回答は必ず日本語で行う。**
- **大きな変更の前に計画を提示する。** 多数ファイルの生成・構成変更・ルール追加など大きい変更を行う場合は、まず計画を示し「このような計画で進めようと思います。」と提案して合意を取る。
- **変更量が 500 行を超えそうな場合は事前確認する。** 「この指示では変更量が 500 行を超える可能性がありますが、実行しますか?」と尋ねる。
- **大規模改修時は作業ログを残す。** `work-in-progress/` に日付付き Markdown を残す（詳細は「作業ログ」節）。
- **パスはリポジトリルートからの相対パスで指定する**（絶対パス・ホーム起点・環境依存パスは禁止）。
- **JSON は UTF-8 / `ensure_ascii=False` / `indent=2`** を厳守し、既存の配列順序（PartNumber 昇順など）を維持する。
- **購入予定 JSON への要素追加はしない**（ユーザー管理。候補提示は可）。

---

## プロジェクト概要

7400 シリーズ汎用 IC の **収集状況・購入履歴・データシート収集状況** を管理する JSON データベースです。加えて、回路設計ナレッジベース（`usage/`）と KiCAD デモ PCB プロジェクト（`pcb-demo/`）を持ちます。

目的:

- コレクション管理（入手済み IC の記録）
- 在庫追跡（所持型番の一覧化）
- 購入計画支援（レア度別リスト）
- データシート管理（メーカー別収集状況）
- 回路設計ナレッジベース（実使用例・チートシート）

パーツ情報の主な引用元は [List of 7400-series integrated circuits — Wikipedia (EN)](https://en.wikipedia.org/wiki/List_of_7400-series_integrated_circuits)。

---

## ディレクトリ構造

```
7400SeriesCollection/
├── CLAUDE.md                              # このファイル：Claude 向け指示書
├── README.md                              # プロジェクト概要
├── .github/
│   ├── copilot-instructions.md            # GitHub Copilot 向け指示書（対になる版）
│   └── prompts/
│       └── factcheck-interactive.prompt.md  # 対話型ファクトチェック（Copilot Agent 用）
├── .gitignore
├── .vscode/tasks.json                     # VS Code タスク定義
├── .venv/                                 # Python 仮想環境（PyMuPDF 等。Git 管理外）
├── .temp/                                 # 一時作業・検証用（Git 管理外）
├── .archive/                              # 過去ログ・廃止スクリプトの保管
├── overview/
│   ├── 7400_series_ic_overview.json       # マスターデータ：全 IC 情報
│   └── categories/                        # マスタを論理分類で分割した JSON 群
├── datasheets/
│   ├── 7400_series_ic_datasheet_collection_status.json  # データシート収集状況
│   ├── datasheet_sources.json             # 一次資料 URL / DocID / Rev / 参照日
│   ├── datasheet_sources.example.json     # 上記の雛形テンプレート
│   ├── .cache/pdf_render/                 # PDF→PNG レンダリング一時出力（Git 管理外）
│   └── _download/                         # ダウンロード済みデータシート（メーカー別）
│       ├── FAIRCHILD(FairchildSemiconductor)/
│       ├── PHILIPS(NXPSemiconductors)/
│       ├── RENESAS/
│       ├── TI(TexasInstruments)/{CD74HC,SN74HC,SN74LS}/
│       ├── TOSHIBA/
│       └── UTC(UnisonicTechnologies)/
├── getstarting/
│   ├── 7400_series_ic_collection_acquisition_history.json  # 入手済み履歴
│   ├── 7400_series_ic_purchase_plan_normal_or_lower.json
│   ├── 7400_series_ic_purchase_plan_rare.json
│   ├── 7400_series_ic_purchase_plan_maniac.json
│   └── 7400_series_ic_purchase_wishlist_very_nerd.json
├── scripts/                               # 自動化スクリプト（Python3）
├── usage/{カテゴリ}/{74xNN}/**.md         # チートシート + 回路設計例
├── pcb-demo/{カテゴリ}/{74xNN}/           # KiCAD デモプロジェクト群
│   ├── _templates/                        # KiCAD テンプレート
│   └── index.md                           # 自動生成インデックス
└── work-in-progress/                      # 大規模改修の作業ログ（YYYY-MM-DD_*.md）
```

`usage/` と `pcb-demo/` のカテゴリは共通で、現状以下が存在します:

`01_buffers_inverters`, `02_nand_and_gates`, `03_nor_or_gates`, `04_xor_xnor_gates`, `05_flipflops_latches`, `06_encoders_decoders`, `07_data_selectors_mux_demux`, `08_counters`, `09_registers`, `10_arithmetic`, `11_error_detection_correction`, `12_memory_storage`, `13_programmable_logic`, `14_system_controllers_timing`, `15_interfaces_links`, `16_analog_mixed_signal`, `17_expanders`, `18_carry_generators`, `99_other`、および複数 IC 連携用の `usage/A_combinated_samples/`。

---

## データスキーマ定義

### `overview/7400_series_ic_overview.json`（マスターデータ）

全 7400 シリーズ IC の基準となるファイル。

```json
{
  "PartNumber": "74x00",
  "Description": "Quad 2-input NAND gate",
  "Description_JP": "4回路2入力NANDゲート",
  "Rarity": "Commons"
}
```

- `PartNumber`: 汎用型番（`74x` 形式、`x` は任意のロジックファミリ）
- `Description` / `Description_JP`: 英語／日本語の機能説明
- `Rarity`: レア度（後述「レア度分類システム」）

`overview/categories/` は上記を論理分類ごとに分割した JSON 群（同一元データから分割したもの同士がまとまる）。Wikipedia の見出しに加え「メモリ/ストレージ」「誤り検出・訂正」「システム制御・タイミング」「インタフェース/リンク」「アナログ/混載」等の実用カテゴリを追加。

### `datasheets/7400_series_ic_datasheet_collection_status.json`

```json
{
  "PartNumber": "74x00",
  "GottenItems_MakerOfDataSheet": {
    "SN74HC00N": "TI(Texas Instruments)",
    "74HC00N": "(収集予定:NXP Semiconductors)",
    "74S00N": "(保留)"
  }
}
```

- キー = 実際のメーカー型番（入手履歴に基づく）
- 値の形式:
  - `"メーカー名"` → データシート入手済み
  - `"(収集予定:メーカー名)"` → 未入手・収集予定
  - `"(保留)"` → 収集保留（廃止品・入手困難など）

### `datasheets/datasheet_sources.json`

一次資料の **再現可能な参照情報**（URL / Document ID / Revision / 参照日 / sha256 等）。本文 PDF を Git に含めない将来の公開状態でも検証できるようにするためのメタ情報。雛形は `datasheet_sources.example.json`。

### `getstarting/7400_series_ic_collection_acquisition_history.json`（入手履歴）

```json
{
  "PartNumber": "74x00",
  "GetStartingECS_JP": ["秋月電子", "Amazon"],
  "Comments": ["Amazonの74HCシリーズICキットなどから入手"],
  "GottenItemsMN_CMOS": ["74HC00N", "SN74HC00N"],
  "GottenItemsMN_TTL": ["SN74S00N"],
  "GottenItemsMN_Other": []
}
```

- `GetStartingECS_JP`: 購入先（日本語）
- `Comments`: 入手メモ
- `GottenItemsMN_CMOS` / `_TTL` / `_Other`: 入手済みの **実型番**（Other はソビエト互換品など）

### 購入予定・希望 JSON（レア度別サブセット）

`overview` から該当レア度をフィルタしたサブセット。**Claude は配列要素を追加しない**（ユーザー管理）。

- `..._purchase_plan_normal_or_lower.json`: Commons, Normal, Normal+
- `..._purchase_plan_rare.json`: Rare, Rare+
- `..._purchase_plan_maniac.json`: SuperRare, Abolition(R+), Maniac(SR+)
- `..._purchase_wishlist_very_nerd.json`: ManiacRare(SSR), VeryNerd(UR)

---

## データ分類・メタデータ

### レア度分類システム

**一般流通品**: `Commons`（容易）/ `Normal` / `Normal+`（やや困難）/ `Rare` / `Rare+`（非常にレア）/ `SuperRare`（極めてレア）

**一般流通していない品**: `Abolition(R+)`（廃止品系）/ `Maniac(SR+)`（マニア向け）/ `ManiacRare(SSR)`（マニア向けレア）/ `VeryNerd(UR)`（超マニア向け・極めて入手困難）

### メーカー型番接頭辞

| 接頭辞 | メーカー |
| --- | --- |
| `SN74*`, `CD74*` | TI (Texas Instruments) |
| `U74*` | UTC (Unisonic Technologies) |
| `HD74*` | RENESAS |
| `TC74*` | TOSHIBA |
| `MM74*`, `MC74*` | FAIRCHILD (Fairchild Semiconductor) |
| `74HC*`（接頭辞なし） | PHILIPS (NXP Semiconductors) |

メーカー推定は **保守的に**。不確実な推定で勝手にデータを埋めないこと。

---

## スクリプト（`scripts/`）

すべて Python3。リポジトリルートから実行。Windows 環境の仮想環境 Python は `.venv/Scripts/python.exe`（PyMuPDF=`fitz` 等を含む）。

### データ管理・生成

- `merge_fp.py`: データ統合処理（レア度別購入予定 JSON の生成等）
- `refine_descriptions.py`: 説明文の洗練化
- `split_overview_by_logic_category.py`: マスタを論理分類で `overview/categories/` に分割
- `sync_category_fields.py`: カテゴリ JSON 間のフィールド同期
- `sort_datasheet_by_partnumber.py`: データシート収集状況のソート
- `autofill_gottenitems.py`: 入手履歴 → データシート収集状況の自動同期（メーカー推定込み、既存上書き回避）

### usage / チートシート

- `generate_usage_cheatsheets.py`: `usage/{カテゴリ}/{74xNN}/{74xNN}.md` チートシートを生成
- `generate_usage_samples_owned_01_04.py`: 入手済みパーツの回路サンプル生成（カテゴリ 01〜04 系）
- `append_usage_factcheck_footer.py`: usage Markdown にファクトチェック用フッターを追加
- `migrate_usage_structure.py`: 旧 usage 構造を `{カテゴリ}/{74xNN}` 構造へ移行
- `auto_check_factcheck.py`: `usage/.../{74xNN}.md` のファクトチェック項目（`- [ ]`）を自動更新。入手履歴から実型番を確定して「対象の実型番」を `[x]` に、`datasheet_sources.json` の確認済み URL で「参照先」を更新。既に `[x]` の項目は冪等スキップ。実行: `python3 scripts/auto_check_factcheck.py`

### データシート / 一次資料

- `check_datasheet_sources.py`: `datasheet_sources.json` の URL 到達性チェック / 任意 DL / sha256 算出 / レポート出力
  - 例: `python3 scripts/check_datasheet_sources.py --skip-empty`
  - 例（DL+sha256）: `python3 scripts/check_datasheet_sources.py --download --report .temp/datasheet_fetch/report.json`
  - 例（メタ情報を sources へ反映）: `python3 scripts/check_datasheet_sources.py --skip-empty --download --update`
- `seed_datasheet_sources_from_usage_and_history.py`: usage / 入手履歴から `datasheet_sources.json` の雛形を生成
- `render_datasheet_pages.py`: ローカル PDF を `datasheets/.cache/pdf_render/{part}_{stem}/page_XXX.png` へ PNG レンダリング（要 PyMuPDF / Git 管理外）
  - 例: `python3 scripts/render_datasheet_pages.py --part 74x00 --pages 1-6 --dpi 150`
  - **確認後は `datasheets/.cache/pdf_render/` を整理・削除する**（`.cache/` 外のファイルはみだりに削除しない）
- `batch_factcheck_from_pdf.py`: 入手済み全パーツのローカル PDF からテキスト抽出し、**信頼度 85% 以上**の項目のみ一括自動確認。画像主体 PDF / PDF 無しパーツはスキップ
  - 例: `python3 scripts/batch_factcheck_from_pdf.py --dry-run`
  - 例: `python3 scripts/batch_factcheck_from_pdf.py --part 74x86 --verbose`
  - 例（全適用）: `python3 scripts/batch_factcheck_from_pdf.py`

### PCB デモ

- `generate_pcb_demo_projects.py`: `pcb-demo/` の KiCAD プロジェクトを一括生成
- `kicad_sch_gen.py`: KiCAD 8 形式（version 20231120）の実回路図生成モジュール。KiCAD 標準ライブラリ `74xx.kicad_sym` のシンボルを `lib_symbols` に埋め込む（対応 47 種）

### Python コーディング指針

- JSON 入出力は標準 `json`。読み書きは UTF-8 / `ensure_ascii=False` / `indent=2`。
- パスはリポジトリルート基準で組み立てる:
  ```python
  import os, json
  base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  overview_path = os.path.join(base_dir, 'overview', '7400_series_ic_overview.json')
  ```
- メーカー推定は型番接頭辞による **保守的**ロジック。入力データの妥当性チェック・適切なエラーハンドリング・処理結果ログを実装する。

---

## VS Code タスク（`.vscode/tasks.json`）

- `Generate FP/ALL JSONs` → `merge_fp.py`
- `Refine Descriptions` → `refine_descriptions.py`
- `Regenerate ALL after refine` → `merge_fp.py`
- `PCB Demo: dry-run (show targets)` → `generate_pcb_demo_projects.py`
- `PCB Demo: generate all projects` → `... --apply`
- `PCB Demo: overwrite all projects` → `... --apply --overwrite`
- `KiCAD CLI: export Gerber` → `kicad-cli.exe pcb export gerbers ...`
- `KiCAD CLI: run DRC` → `kicad-cli.exe pcb drc ...`

KiCAD CLI のフルパスは `tasks.json` 内（`C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`）を参照。

---

## 回路設計ドキュメント作成ガイド（`usage/`）

`usage/` は「**実際に配線できること**」が最優先の回路設計ナレッジベース。

### 構造と命名

- 構造: `usage/{カテゴリ}/{74xNN}/**.md`（例: `usage/07_data_selectors_mux_demux/74x153/74x153.md`）
- 回路例ファイルは連番プレフィックス（`01_`, `02_`, …）＋簡潔な英語名（例: `01_4bit_alu_basic_demo.md`）
- **複数 IC 連携サンプル**は `usage/A_combinated_samples/` にまとめ、ディレクトリ名はカンマ区切り可（例: `74x181,182/`）
- `.private/` は Git 管理外の個人メモ

### チートシートに書いてよい内容

overview 由来の説明（機能/カテゴリ/レア度）、一般的な配線注意（入力フローティング禁止、デカップリング、ファミリ差など）、一次資料確認チェックリストと参照導線（URL/DocID/Rev/参照日）。**断定が必要な仕様（ピン配置・真理値表・電気特性）は一次資料未確認のまま書かない。**

### 回路例の必須記載項目

1. 回路概要（目的・主要 IC 型番）
2. 回路の仕様（入出力ビット数・動作モード・電源）
3. ピンアサインと配線方法（ASCII 配置図・結線表・プルアップ/ダウン）
4. 必要部品リスト（**所持 IC のみ使用**。`getstarting/...acquisition_history.json` の `GottenItemsMN_*` を優先し、対応する一次資料 PDF の存在を確認）
5. 配線の注意事項（誤配線しやすい箇所・タイミング・ノイズ対策）
6. 表示器の対応（LED 直接駆動の抵抗値 / 7 セグ + デコーダ / ニキシー管 + ドライバ 74x141 等）
7. 動作確認手順（通電前チェック・テスト手順・期待出力）
8. トラブルシューティング
9. 回路の拡張性（ビット幅拡張・機能追加・他 IC との組合せ）

### Markdown 記法

コードブロックで ASCII 回路図、テーブルでピン接続表、見出しはレベル 2〜4、チェックボックス（`- [ ]` / `- [x]`）で確認項目、重要事項は引用（`>`）または **太字**。

---

## ⚠️ 一次資料照合ルール（推測禁止・最重要）

`usage/` の回路成立に直結する事項 —— **ピン番号・信号名・真理値表・論理条件・未使用入力の処理・推奨デカップリング** —— は **必ず一次資料（データシート PDF）に照合**してから断定する。74x 系は互換に見えても、ファミリ／メーカー／パッケージで差異があり得る。「よくあるピン配置」等の一般知識だけで確定記述しない。

### 一次資料の優先順位

1. **Web 自動取得 PDF**（`datasheet_sources.json` の URL を `check_datasheet_sources.py --download` で取得。URL 到達性・sha256 で再現性が高い）
2. **`datasheets/_download/` の手動入手 PDF**（手元資料での整合確認。公開時の再現性は URL/DocID/Rev/参照日 で担保）
3. **Web 検索 + 手動確認情報**（1・2 が無い場合の補助。一次資料と矛盾したら一次資料優先し、矛盾点を明示してユーザー確認）

### 必須ルール

- 推測でピンアサイン・真理値表を断定しない。読み取れなかった項目は `- [ ]` のまま残す。
- 断定的な仕様を書く場合は最低限 **メーカー名 / 正確な型番 / パッケージ / データシート URL / DocID / Revision / 参照日（YYYY-MM-DD）** を併記。
- **データシートの図表・文章は転載しない。** 要点を自分の言葉で要約し、リンクで誘導する。
- **画像主体 PDF**（テキスト抽出不可）は `render_datasheet_pages.py` で PNG 化し、Read（画像表示）で目視確認。確認できない項目は追加しない。確認後はレンダリング画像を整理・削除する。
- 入手済みの実型番（`GottenItemsMN_*`）を優先し、対応する一次資料の有無を確認してから記述。
- **キリル型番等の互換パーツ**（`GottenItemsMN_Other` の `K155ID1/К155ИД1` など）は PDF 入手・機械解読が困難なことがあり、例外的にネット情報に依存可。ただし世代差・ピン配置差の可能性を明示し、断定せずユーザーと共同確認する。

### Claude での対話型ファクトチェック手順（factcheck-interactive 相当）

Copilot 用の [`.github/prompts/factcheck-interactive.prompt.md`](.github/prompts/factcheck-interactive.prompt.md) と同じワークフローを Claude でも実施する。

1. **対象確認**: 指定の汎用型番（例 `74x00`）について、`usage/{カテゴリ}/{型番}/{型番}.md`・入手履歴・`datasheet_sources.json`・収集状況 JSON を読む。
2. **レンダリング**: `python3 scripts/render_datasheet_pages.py --part {型番}` で PDF を PNG 化（大きい PDF は `--pages 1-10` 等で制限。CMOS 系 / TI SN74HC を優先）。
3. **目視確認 + 信頼度スコアリング**: 各 PNG を Read（画像表示）で確認し、ピン配置 / 真理値表 / 絶対最大定格・推奨動作条件 / 電気特性 / 未使用入力の扱い を読み取り、項目ごとに信頼度 0〜100% を自己評価して報告する。
   - 低下要因の目安: 小さい/かすれ文字 −5〜15%、多列・多行表 −5〜20%、紛らわしい文字（0/O, 1/l, µ/u）−3〜10%、ページまたぎ表 −5〜10%、低画質（モアレ/歪み）−10〜30%
   - 上昇要因: 複数 PDF で相互確認 +5〜10%
4. **ユーザー確認**: **85% 以上は自動確認**（`[x]` 更新）、**85% 未満のみユーザーに目視確認を依頼**。「それっぽい」だけで高信頼度を与えない。信頼度の根拠（何が明瞭/不明瞭か）を述べる。
5. **更新**: 確認済み項目を `- [ ]` → `- [x]` に。確認日・信頼度・参照 PDF を付記（例: `（TI データシートより確認 2026-02-14, 読み取り信頼度 95%）`）。読み取れなかった項目は `- [ ]` のまま。
6. **後片付け**: `datasheets/.cache/pdf_render/{型番}*` の一時 PNG を削除する。

---

## KiCAD PCB デモ制作ガイド（`pcb-demo/`）

入手済み IC の動作プレゼン用 **最小デモ PCB** を KiCAD 10.0.3 で制作するプロジェクト群。構造は `usage/` と同じ `{カテゴリ}/{74xNN}/`。

### 環境

- KiCAD 10.0.3 / CLI: `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`
- テンプレートは KiCAD 8 互換形式（version 20231120 / 20240108。KiCAD 10 が初回保存で自動アップグレード）

### 生成

```bash
python3 scripts/generate_pcb_demo_projects.py                 # dry-run（生成予定表示）
python3 scripts/generate_pcb_demo_projects.py --apply         # 新規のみ生成
python3 scripts/generate_pcb_demo_projects.py --apply --category 01_buffers_inverters
python3 scripts/generate_pcb_demo_projects.py --apply --overwrite   # 既存も上書き
```

`kicad_sch_gen.py` が KiCAD 標準ライブラリ（`74xx`）の実シンボルを使った `.kicad_sch` を生成（対応 47 種: バッファ/インバータ・NAND/NOR/AND/OR/XOR・FF・ラッチ・MUX・デコーダ・カウンタ・算術・シフトレジスタ等）。非対応部品はテキスト注釈版またはテンプレートスタブにフォールバック。

### 設計ルール（必須）

1. **一次資料未確認のまま断定的なピン配置を PCB / 回路図に書かない。** `usage/{カテゴリ}/{型番}/` のファクトチェック完了が前提（優先順位は上記「一次資料照合ルール」に準じる）。
2. **KiCAD 標準ライブラリ（`74xx`）を優先。** `.kicad_sym` スタブはプレースホルダ。
3. テンプレートのプレースホルダ: `{{PART_NUMBER}}` / `{{DESCRIPTION}}` / `{{DESCRIPTION_JP}}` / `{{CATEGORY}}` / `{{CMOS_PARTS}}` / `{{TTL_PARTS}}` / `{{OTHER_PARTS}}` / `{{ALL_OWNED_PARTS}}` / `{{DATE}}`
4. PCB 基本仕様（テンプレ既定）: 基板 50×50 mm（Edge.Cuts に外形線）/ 銅箔 35µm（1oz）/ 基板厚 1.6 mm / 最小パターン幅 0.2 mm / **IC 1 個につき 100nF を VCC–GND 直近に配置**
5. KiCAD CLI（Gerber 出力・DRC）は VS Code タスク経由で実行。

### Git 管理方針

- テンプレート（`_templates/`）・自動生成スタブ（各 IC プロジェクト）: **管理対象**
- Gerber 出力（`gerber/`）・KiCAD バックアップ（`*-backups/`, `*.kicad_prl`）: `.gitignore` 除外推奨

---

## 作業ログ（大規模改修時）

データスキーマ変更・生成スクリプト追加・収集方針変更・usage 大量更新など **大規模改修**を行う場合は `work-in-progress/` に日付付きログ（Markdown）を残す。

- ファイル名: `YYYY-MM-DD_*.md`（例: `2026-05-30_auto_check_factcheck.md`）
- 最低限の内容: **目的 / 変更点（触ったファイル・スクリプト）/ 実行コマンド（再現手順）/ 検証結果（件数・失敗パターン）/ 残課題**
- 禁止: 一次資料 PDF 本文・転載を置かない（URL/DocID/Rev/参照日/sha256 等のメタ情報は可）。機密情報（個人情報・トークン・購入アカウント情報）を書かない。

---

## 禁止事項

1. 既存データの意図しない改変（手動編集は慎重に。自動化スクリプトを優先）
2. `PartNumber` 体系の破壊（`74x` 形式の汎用表記を維持）
3. メーカー推定ロジックの過度な拡張（保守的アプローチを維持）
4. JSON の文字コード変更（UTF-8 厳守）
5. 複数ファイル間の不整合を引き起こす操作
6. **購入予定 JSON（`getstarting/..._purchase_*.json` / `..._wishlist_*.json`）への配列要素追加**（ユーザー管理。提案・候補提示のみ可）
7. **一次資料未確認のピン配置・真理値表・電気特性の断定記述**
8. データシート図表・文章の転載

---

## プロジェクト開発ポリシー

このプロジェクトは精密なデータ管理を要求します。常に次を最優先してください。

- **データ整合性**: 全 JSON ファイル間の一貫性維持
- **既存構造の尊重**: 既定スキーマ・フォーマットの遵守
- **段階的な変更**: 大規模変更は小さなステップに分割
- **検証の徹底**: 変更後は必ずデータの妥当性を確認
- **国際化**: 英語・日本語両対応（説明文）
