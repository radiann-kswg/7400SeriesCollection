# GitHub Copilot Instructions - 7400 シリーズ IC Collection Database

## プロジェクト概要

このリポジトリは 7400 シリーズ汎用 IC の収集状況、購入履歴、データシート収集状況を管理する JSON データベースです。
コレクション管理、在庫追跡、及び購入計画の支援を目的としています。

## ディレクトリ構造

プロジェクトのディレクトリ構造は以下の通りです：

```
7400SeriesCollection/
├── .github/
│   └── copilot-instructions.md          # このファイル：GitHub Copilot 向け指示書
├── 7400シリーズ汎用IC概要.json           # マスターデータ：全IC情報
├── datasheets/
│   └── 7400シリーズ汎用ICデータシート収集状況.json
│                                         # データシート収集管理
├── getstarting/
│   ├── 7400シリーズ汎用IC所持状況･入手履歴.json
│   │                                     # 実入手済みIC履歴
│   ├── 7400シリーズ汎用IC所持状況･購入予定(ノーマル級以下).json
│   ├── 7400シリーズ汎用IC所持状況･購入予定(レア級).json
│   ├── 7400シリーズ汎用IC所持状況･購入予定(マニア級).json
│   └── 7400シリーズ汎用IC所持状況･購入希望(ベリーナード級).json
│                                         # レア度別購入計画リスト
├── scripts/
│   ├── autofill_gottenitems.py          # 入手履歴からデータシート情報を自動同期
│   ├── merge_fp.py                      # データ統合処理スクリプト
│   ├── refine_descriptions.py           # 説明文洗練化スクリプト
│   └── sort_datasheet_by_partnumber.py  # データシートソート処理
└── usage/
    └── *.md                              # 7400シリーズICを用いた回路設計情報
                                          # （Markdown形式で追加予定）
```

### ディレクトリ別の役割

#### ルートディレクトリ (`/`)

- **`7400シリーズ汎用IC概要.json`**: 全 7400 シリーズ IC のマスターデータベース
  - すべてのパーツ情報の基準となるファイル
  - 型番、説明（英語/日本語）、レア度を管理

#### `.github/`

- GitHub 関連の設定・ドキュメント格納
- **`copilot-instructions.md`**: GitHub Copilot への開発ガイドライン

#### `datasheets/`

- データシート収集状況の管理
- **`7400シリーズ汎用ICデータシート収集状況.json`**:
  - 各パーツのデータシート入手状況
  - 収集予定メーカー・型番の記録

#### `getstarting/`

- IC の入手・購入管理に関するデータ
- **入手履歴 JSON**: 実際に入手した IC の記録（購入先、コメント含む）
- **購入予定 JSON（レア度別）**:
  - `ノーマル級以下`: Commons, Normal, Normal+ クラス
  - `レア級`: Rare, Rare+ クラス
  - `マニア級`: SuperRare, Abolition(R+), Maniac(SR+) クラス
  - `ベリーナード級`: ManiacRare(SSR), VeryNerd(UR) クラス

#### `scripts/`

- データ管理・自動化スクリプト
- Python3 で実行される処理スクリプト群
- VS Code タスクから実行可能

#### `usage/`

- **7400 シリーズ IC を実際に使用した回路設計の実例・ナレッジベース**
- Markdown 形式で記述
- 回路図、設計ノート、アプリケーション例などを格納予定

### ファイルパス指定の規則

**重要**: Markdown ファイル内や Python スクリプト内でファイルパスを指定する際は、**リポジトリルートからの相対パス**を使用してください。

#### 正しいパス指定例

```markdown
<!-- usage/内のMarkdownファイルから参照する場合 -->

詳細は [7400 シリーズ汎用 IC 概要.json](../7400シリーズ汎用IC概要.json) を参照。
入手履歴は [こちら](../getstarting/7400シリーズ汎用IC所持状況･入手履歴.json) 。
```

```python
# scripts/内のPythonスクリプトからファイルを読み込む場合
import os
import json

# リポジトリルートを基準とした相対パス
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
overview_path = os.path.join(base_dir, '7400シリーズ汎用IC概要.json')
history_path = os.path.join(base_dir, 'getstarting', '7400シリーズ汎用IC所持状況･入手履歴.json')
```

#### 避けるべきパス指定

- ❌ 絶対パス（`/Users/username/...`, `C:\Users\...`）
- ❌ ホームディレクトリ起点（`~/...`）
- ❌ 環境依存のパス

## ファイル構造とデータスキーマ

### メインデータファイル概要

- `7400シリーズ汎用IC概要.json`: 全 7400 シリーズ IC の基本情報（型番、説明、レア度）
- `getstarting/7400シリーズ汎用IC所持状況･入手履歴.json`: 実際に入手した IC の履歴
- `datasheets/7400シリーズ汎用ICデータシート収集状況.json`: データシート収集状況
- `getstarting/7400シリーズ汎用IC所持状況･購入予定(*.json`: 購入予定リスト（レア度別）

### データスキーマの理解

#### 7400 シリーズ汎用 IC 概要.json

```json
{
  "PartNumber": "74x00", // 汎用型番（xは任意のロジックファミリ）
  "Description": "英語説明", // 英語での機能説明
  "Description_JP": "日本語説明", // 日本語での機能説明
  "Rarity": "Commons|Normal|..." // レア度分類
}
```

#### 入手履歴.json

```json
{
  "PartNumber": "74x00",
  "GetStartingECS_JP": ["購入先1", "購入先2"],
  "Comments": ["入手コメント"],
  "GottenItemsMN_CMOS": ["実際の型番"], // CMOS系
  "GottenItemsMN_TTL": ["実際の型番"], // TTL系
  "GottenItemsMN_Other": ["実際の型番"] // その他
}
```

### レア度分類システム

#### 一般的に流通しているパーツ

- `Commons`: 一般的で入手容易
- `Normal`: 通常入手可能
- `Normal+`: やや入手困難
- `Rare`: レア品
- `Rare+`: 非常にレア
- `SuperRare`: 極めてレア

#### 中古販売など一般流通は現在していないパーツ

- `Abolition(R+)`: 廃止品系
- `Maniac(SR+)`: マニア向け
- `ManiacRare(SSR)`: マニア向けでレア
- `VeryNerd(UR)`: 超マニア向けで極めて入手困難

### メーカー型番接頭辞の理解

- `SN74*`: TI (Texas Instruments)
- `CD74*`: TI (Texas Instruments)
- `U74*`: UTC (Unisonic Technologies)
- `HD74*`: RENESAS
- `TC74*`: TOSHIBA
- `MM74*`, `MC74*`: FAIRCHILD (Fairchild Semiconductor)
- `74HC*` (接頭辞なし): PHILIPS (NXP Semiconductors)

## コーディング支援ガイドライン

### パーツ概要引用 URL

- https://en.wikipedia.org/wiki/List_of_7400-series_integrated_circuits (英語版 Wikipedia)

### JSON 編集時の注意点

1. **文字エンコーディング**: UTF-8 を使用、日本語文字を適切に処理
2. **データ整合性**: PartNumber の一貫性を保つ
3. **配列の順序**: 既存の順序を維持（PartNumber の昇順など）
4. **型番表記**: `74x`形式での汎用表記と実際の型番の区別を理解

### Python スクリプト開発時

1. **JSON ファイル処理**: `json`モジュールを使用、適切なエラーハンドリング
2. **メーカー推定ロジック**: 型番接頭辞による保守的な推定を実装
3. **データ検証**: 入力データの妥当性チェック
4. **ログ出力**: 処理結果の詳細なログを提供

### 新機能開発の指針

1. **データ整合性の維持**: 複数 JSON ファイル間の一貫性
2. **拡張性**: 新しいメーカーやロジックファミリへの対応
3. **国際化**: 英語・日本語両対応
4. **エラー処理**: 不正データに対する適切な処理

## 自動化スクリプトの理解

### `scripts/autofill_gottenitems.py`

- 入手履歴からデータシート収集状況へのデータ自動同期
- メーカー推定による収集予定データの自動生成
- 既存データの上書き回避

### VS Code タスク

- `Generate FP/ALL JSONs`: データの統合処理
- `Refine Descriptions`: 説明文の洗練化
- `Regenerate ALL after refine`: 洗練後の再生成

## 推奨されるコーディングパターン

### JSON データの読み書き

```python
import json
import os

# UTF-8でJSONファイルを読み込み
with open('file.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# インデント付きで保存
with open('file.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

### 型番の正規化

```python
def normalize_part_number(part_num):
    """型番を汎用形式に正規化"""
    # SN74HC00N -> 74x00 の変換ロジック
    pass
```

### データ検証

```python
def validate_part_data(part_data):
    """パーツデータの妥当性を検証"""
    required_fields = ['PartNumber', 'Description', 'Rarity']
    for field in required_fields:
        if field not in part_data:
            raise ValueError(f"Required field {field} is missing")
```

## 禁止事項

- 既存データの意図しない改変
- PartNumber 体系の破壊
- メーカー推定ロジックの過度な拡張（保守的アプローチを維持）
- JSON ファイルの文字コード変更
- データの不整合を引き起こす操作

このプロジェクトは精密なデータ管理を要求するため、データ整合性と既存構造の尊重を最優先に開発を進めてください。
