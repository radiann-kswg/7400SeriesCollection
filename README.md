# 7400 シリーズ汎用 IC Collection Database

7400 シリーズ汎用 IC の収集状況、購入履歴、データシート収集状況を管理する JSON データベースです。

## 📋 プロジェクト概要

このリポジトリは以下の目的で運用されています：

- **コレクション管理**: 入手済み IC の記録と管理
- **在庫追跡**: 所持している IC 型番の一覧化
- **購入計画支援**: レア度別の購入予定リスト
- **データシート管理**: メーカー別データシートの収集状況追跡
- **回路設計ナレッジベース**: 実際の使用例・回路設計情報の蓄積
- **汎用型番チートシート**: `74xNN` ごとの要点・注意点・一次資料確認の導線

## 🗂️ ディレクトリ構造

```
7400SeriesCollection/
├── overview/                             # overview系データ
│   ├── 7400_series_ic_overview.json      # マスターデータ：全IC情報
│   └── categories/                       # 上記マスタを論理分類で分割したJSON群
├── datasheets/                           # データシート管理
│   ├── 7400_series_ic_datasheet_collection_status.json
│   └── _download/                        # ダウンロード済みPDF保管
│       ├── FAIRCHILD(FairchildSemiconductor)/
│       ├── PHILIPS(NXPSemiconductors)/
│       ├── RENESAS/
│       ├── TI(TexasInstruments)/
│       │   ├── CD74HC/
│       │   ├── SN74HC/
│       │   └── SN74LS/
│       ├── TOSHIBA/
│       └── UTC(UnisonicTechnologies)/
├── getstarting/                          # 入手・購入管理
│   ├── 7400_series_ic_collection_acquisition_history.json
│   ├── 7400_series_ic_purchase_plan_normal_or_lower.json
│   ├── 7400_series_ic_purchase_plan_rare.json
│   ├── 7400_series_ic_purchase_plan_maniac.json
│   └── 7400_series_ic_purchase_wishlist_very_nerd.json
├── scripts/                              # 自動化スクリプト
│   ├── autofill_gottenitems.py          # データシート情報自動同期
│   ├── merge_fp.py                      # データ統合処理
│   ├── refine_descriptions.py           # 説明文洗練化
│   ├── split_overview_by_logic_category.py # overviewを論理分類で分割
│   └── sort_datasheet_by_partnumber.py  # データシートソート
└── usage/                                # 回路設計実例
  ├── 06_encoders_decoders/             # カテゴリ
  │   └── 74x141/                       # パーツ番号
  │       ├── 74x141.md                 # チートシート（自動生成）
  │       └── 01_simple_nixie_tube_demo.md  # 実回路例（手書き）
  └── 10_arithmetic/
    └── 74x181,182/                   # 複数IC連携時はカンマ区切り
```

## 📊 データファイル説明

### マスターデータ

#### `overview/7400_series_ic_overview.json`

全 7400 シリーズ IC の基本情報を格納するマスターデータベース。

```json
{
  "PartNumber": "74x00",
  "Description": "Quad 2-input NAND gate",
  "Description_JP": "4回路2入力NANDゲート",
  "Rarity": "Commons"
}
```

**レア度分類**:

- **一般流通品**: `Commons`, `Normal`, `Normal+`, `Rare`, `Rare+`, `SuperRare`
- **廃止品/特殊品**: `Abolition(R+)`, `Maniac(SR+)`, `ManiacRare(SSR)`, `VeryNerd(UR)`

### 入手管理データ

#### `getstarting/7400_series_ic_collection_acquisition_history.json`

実際に入手した IC の記録（購入先、コメント含む）。

```json
{
  "PartNumber": "74x00",
  "GetStartingECS_JP": ["秋月電子", "Amazon"],
  "Comments": ["Amazonの74HCシリーズICキットから入手"],
  "GottenItemsMN_CMOS": ["74HC00N", "SN74HC00N"],
  "GottenItemsMN_TTL": ["SN74S00N"],
  "GottenItemsMN_Other": []
}
```

### データシート管理

#### `datasheets/7400_series_ic_datasheet_collection_status.json`

各パーツのデータシート入手状況を追跡。

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

**ステータス表記**:

- `"メーカー名"`: データシート入手済み
- `"(収集予定:メーカー名)"`: 未入手、収集予定
- `"(保留)"`: 収集保留中

## 🔧 スクリプト使用方法

### データシート情報の自動同期

入手履歴からデータシート収集状況を自動生成：

```bash
python3 scripts/autofill_gottenitems.py
```

### データ統合処理

レア度別購入予定 JSON の生成：

```bash
python3 scripts/merge_fp.py
```

### マスターデータの論理分類分割

Wikipedia の 7400 シリーズ機能分類を参考に、`overview/7400_series_ic_overview.json` を分類別 JSON に分割して `overview/categories/` に出力します。

```bash
python3 scripts/split_overview_by_logic_category.py
```

出力される分類ファイル（例）:

- `01_buffers_inverters.json`
- `02_nand_and_gates.json`
- `03_nor_or_gates.json`
- `04_xor_xnor_gates.json`
- `05_flipflops_latches.json`
- `06_encoders_decoders.json`
- `07_data_selectors_mux_demux.json`
- `08_counters.json`
- `09_registers.json`
- `10_arithmetic.json`
- `11_error_detection_correction.json`
- `12_memory_storage.json`
- `13_programmable_logic.json`
- `14_system_controllers_timing.json`
- `15_interfaces_links.json`
- `16_analog_mixed_signal.json`
- `99_other.json`

```

### VS Code タスク

VS Code から実行可能なタスク：

- **Generate FP/ALL JSONs**: データ統合処理
- **Refine Descriptions**: 説明文洗練化
- **Regenerate ALL after refine**: 洗練後の再生成

※ これらのタスクは `scripts/merge_fp.py` / `scripts/refine_descriptions.py` を実行します。

## 📝 メーカー型番接頭辞

| 接頭辞               | メーカー                            |
| -------------------- | ----------------------------------- |
| `SN74*`, `CD74*`     | TI (Texas Instruments)              |
| `U74*`               | UTC (Unisonic Technologies)         |
| `HD74*`              | RENESAS                             |
| `TC74*`              | TOSHIBA                             |
| `MM74*`, `MC74*`     | FAIRCHILD (Fairchild Semiconductor) |
| `74HC*` (接頭辞なし) | PHILIPS (NXP Semiconductors)        |

## 🔗 参照リソース

- [List of 7400-series integrated circuits - Wikipedia](https://en.wikipedia.org/wiki/List_of_7400-series_integrated_circuits)
- [GitHub Copilot Instructions](.github/copilot-instructions.md) - 詳細な開発ガイドライン

## 📐 回路設計例の作成

`usage/`ディレクトリに実際の回路設計例を追加できます。

### ディレクトリ命名規則

```text
usage/
└── {カテゴリ名}/
  └── 74x{型番}/
    ├── 74x{型番}.md  # チートシート（自動生成）
    ├── 01_*回路名.md
    ├── 02_*回路名.md
    └── ...
```

## 🧾 汎用型番チートシート（usage/{カテゴリ名}/{74xNN}/{74xNN}.md）

`overview/7400_series_ic_overview.json` を元に、汎用型番（`74xNN`）ごとのチートシートを生成します。

- 入口: [usage/index.md](usage/index.md)
- 生成スクリプト: [scripts/generate_usage_cheatsheets.py](scripts/generate_usage_cheatsheets.py)

```bash
python3 scripts/generate_usage_cheatsheets.py
```

方針: ピン配置/真理値表/電気特性などの断定は一次資料が必要なため、未検証のまま書かない（リンクとチェックリスト中心）。

複数 IC 連携時は `74x181,182/` のようにカンマ区切り。

### 必須記載項目

1. 回路概要
2. 回路の仕様
3. ピンアサインと配線方法
4. 必要部品リスト
5. 配線の注意事項
6. 表示器の対応（LED、7 セグ、ニキシー管等）
7. 動作確認手順
8. トラブルシューティング
9. 回路の拡張性

詳細は[Copilot Instructions](.github/copilot-instructions.md#回路設計ドキュメント作成ガイド-usage)を参照。

## 🛡️ データ整合性の維持

このプロジェクトは複数の JSON ファイル間で整合性を保つ必要があります：

- **PartNumber**: すべてのファイルで`74x`形式を使用
- **文字エンコーディング**: UTF-8 を厳守
- **配列順序**: PartNumber 昇順を維持
- **型番表記**: 汎用表記（`74x00`）と実際の型番（`SN74HC00N`）を区別

## 🚫 禁止事項

1. 既存データの意図しない改変
2. PartNumber 体系の破壊（`74x`形式の維持）
3. 文字コードの変更（UTF-8 厳守）
4. JSON スキーマの勝手な変更
5. ファイル間の不整合を引き起こす操作

## 📄 ライセンス

このプロジェクトは個人のコレクション管理データベースです。

---

**管理者**: radiann-kswg
**最終更新**: 2025 年 11 月 20 日
```
