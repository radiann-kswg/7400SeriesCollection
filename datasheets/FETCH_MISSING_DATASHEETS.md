# 未収集データシートの一括取得 — `scripts/fetch_missing_datasheets.py`

入手済み 7400 シリーズ IC のうち、`7400_series_ic_datasheet_collection_status.json` で
`(収集予定:…)` になっている型番について、**メーカー公式サイト**からデータシート PDF を取得し、
既存の収録物にならって `datasheets/_download/{メーカー}/.../{型番}.PDF` へ格納します。

> このリポジトリの方針上、PDF 本体は `.gitignore` 済み（`datasheets/_download/`）。
> 公開時の再現性は `datasheet_sources.json` の URL / DocID / Rev / 参照日 / sha256 で担保します。

## 取得元（公式ドメインのみ）

| メーカー | パターン | 対象数 | 確度 |
|---|---|---:|---|
| TI | `ti.com/lit/ds/symlink/<stem>.pdf`（47 件は検証済み URL、残りは規則生成＋54/74・rev 候補でフォールバック） | 72 | 高 |
| Renesas | `renesas.com/en/document/dst/<stem>-datasheet`（PDF を直接返すことを確認済み） | 13 | 高 |
| NXP(Nexperia) | `assets.nexperia.com/documents/data-sheet/74HC_HCT<n>.pdf` 等（パターン確認済み） | 2 | 高 |
| onsemi(Fairchild) | `onsemi.com/download/data-sheet/pdf/<stem>-d.pdf` 等 | 14 | 中〜低（FAST/MC74F 系は廃止でホスト無しの可能性） |
| Toshiba | 公式 PDF は `docget.jsp?did=<数値>` で機械推測不可 → **要手動**（製品ページ参照を出力） | 3 | 手動 |

> ※ サードパーティのデータシート転載サイトは使用しません（規範順守）。
> ダウンロードは `%PDF` シグネチャと Content-Type で検証し、本物の PDF のみ保存します。
> 偽 URL は保存されず FAIL として一覧化されるため、壊れたファイルは残りません。

## 使い方

このスクリプトは **ネットワーク制限のないローカル環境（あなたの PC）** での実行を想定しています。

```bash
# 1) まず計画だけ確認（DLしない）
python3 scripts/fetch_missing_datasheets.py --dry-run

# 2) 実際に取得（_download 配下へ保存）
python3 scripts/fetch_missing_datasheets.py

# 3) 取得と同時に収集状況 / datasheet_sources.json を更新
python3 scripts/fetch_missing_datasheets.py --update

# メーカー絞り込み・件数制限（試運転）
python3 scripts/fetch_missing_datasheets.py --manufacturer TI --max 5 --update
python3 scripts/fetch_missing_datasheets.py --manufacturer Renesas --update
python3 scripts/fetch_missing_datasheets.py --part 74x240
```

主なオプション: `--dry-run` / `--update`（status と sources を反映）/ `--manufacturer` /
`--part` / `--max N` / `--timeout` / `--retries` / `--sleep`（既定 1 秒）。
レポートは `.temp/datasheet_fetch/fetch_missing_report.json`（Git 管理外）に出力されます。

## 動作

- 既存 PDF はトークン索引で照合し、`CD74HC533,CD74HC563.PDF` のような複合ファイルも「収集済み」と認識してスキップします。
- 各型番について候補 URL を順に試し、最初に得られた有効 PDF を採用します（TI はファイル名を採用した symlink 名に合わせます）。
- `--update` 時のみ `collection_status.json` を `(収集予定)→メーカー名` に更新し、`datasheet_sources.json` に
  `FinalUrl / ContentLength / Sha256 / CheckedAt / LastAccessed` を記録します（**検証済みの実 URL のみ**）。

## 想定収率の目安

105 件中、TI(72)・Renesas(13)・NXP(2) は概ね取得見込み、onsemi(14) は一部、Toshiba(3) は手動。
おおよそ 75〜90 件程度が自動取得できる見込みです（実値は実行時のメーカー公開状況に依存）。
取得できなかった分は FAIL/MANUAL としてレポートに残るので、個別対応の手掛かりになります。
