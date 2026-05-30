# 2026-05-30 auto_check_factcheck.py 実装

## 目的

`usage/{category}/{74xNN}/{74xNN}.md` の「ファクトチェック（一次資料）」チェックリストを、
`datasheets/` 配下のデータシート情報から自動確認するスクリプトを実装する。

## 変更点

### 新規追加

- `scripts/auto_check_factcheck.py`

### 変更ファイル

- `usage/` 配下の 161 ファイル（チートシート `.md`）
  - 対象: 入手履歴がある 74xNN のチートシートのみ

## 自動確認できる項目（このスクリプトが対象）

| チェック項目                         | 確認条件                                                                                     |
| ------------------------------------ | -------------------------------------------------------------------------------------------- |
| `[x] 対象の実型番を決める`           | `getstarting/7400_series_ic_collection_acquisition_history.json` に実型番が存在              |
| `[x] データシート参照先`（新規追加） | `datasheets/_download/` に PDF が存在、または `datasheet_sources.json` に確認済み URL がある |

## 自動確認できない項目（ユーザー確認必要）

- `[ ] ピン配置`
- `[ ] 真理値表/機能表`
- `[ ] 絶対最大定格/推奨動作条件`
- `[ ] 電気特性`
- `[ ] 未使用入力/未使用出力の扱い`

## 実行コマンド

```powershell
# dry-run（変更なし・確認のみ）
python3 scripts/auto_check_factcheck.py --dry-run

# 特定型番のみ
python3 scripts/auto_check_factcheck.py --part 74x06

# 全ファイルに適用
python3 scripts/auto_check_factcheck.py
```

## 実行結果（2026-05-30）

```
Processed  : 715
Updated    : 161 (初回実行)
No data    : 553
```

冪等性確認：2回目以降は Updated: 0。

## 出力例（74x86）

```markdown
- [x] **対象の実型番を決める**（入手履歴より自動確認 2026-05-30）
  - CMOS系: `SN74HC86N`
  - TTL系: `HD74LS86P`
- [x] **データシート参照先**（自動確認 2026-05-30）
  - PDF: `datasheets/_download/TI(TexasInstruments)/SN74HC/SN74HC86.PDF`
  - URL (SN74HC86N (TI(TexasInstruments))): https://www.ti.com/lit/ds/symlink/sn74hc86.pdf
- [ ] **ピン配置**（DIP/SOIC/TSSOP など）
- [ ] **真理値表/機能表**（イネーブル極性含む）
      ...
```

## 残課題

- ピン配置・真理値表・電気特性の自動抽出は、PDF からのテキスト抽出（PyMuPDF 等）が必要
  - 「推測で書かない」方針に従い、このスクリプトでは対象外としている
- URL の到達性確認は `scripts/check_datasheet_sources.py` で別途行う
