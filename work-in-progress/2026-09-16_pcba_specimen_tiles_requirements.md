# 2026-09-16 Specimen Tiles（PCBA 化）要件定義とリポジトリ整備

## 目的

収集した 7400 シリーズ IC を「本物の元素を封入した周期表」と同じコンセプトで展示する基板を、
JLCPCB から PCBA 発注できる状態にするための **要件定義・リポジトリ設定・ドキュメント整備**。
設計・作図・発注そのものは本作業のスコープ外（Phase 1 以降）。

## 事前調査で判明した事実

| 項目 | 実態 |
|---|---|
| 既存 `pcb-demo/` | 162 型番分の KiCAD プロジェクトが存在するが、中身は IC シンボル + VCC/GND のみ。**配線 0 本・LED/抵抗なし・Footprint プロパティ空・`.kicad_pcb` は外形線のみ** |
| KiCAD 標準シンボル | 所持 162 型番中 119 件（73%）が解決可能。43 件は該当シンボル無し |
| ピン配置の一次資料確定 | `usage/**/01_basic_function_demo.md` 162 件中、ピン表があるのは **27 件のみ** |
| パッケージ分布（解決済 120 件） | DIP-14: 45 / DIP-16: 59 / DIP-20: 14 / DIP-24: 2。**300mil 20 ピンソケット 1 種で 118/120 = 98% をカバー** |
| 電源ピン非標準 | 74x73 (4/11), 74x75 (5/12), 74x90 (5/10), 74x93 (5/10) |
| GitHub リモート | `radiann-kswg/7400SeriesCollection` は **private**（fork 0 / star 0） |
| 私物情報の広がり | 購入先・コメントは `getstarting/*.json` のみ。所持メーカー型番リストは生成物 487 ファイルに焼き込み済み |
| `getstarting/` 依存 | スクリプト 13 本が参照。ディレクトリ移動は全部破壊するが、`.gitignore` + `git rm --cached` なら 0 本 |
| ツールチェーン | KiCAD 10.0 + `kicad-cli` + `sexpdata` OK。Java 未導入 |
| KiCAD MCP | `~/.claude.json` に `kicad` として登録済み（kicad-mcp v2.7.0 / 233 ツール / JLCPCB 部品検索・Gerber/CPL/BOM 出力・ERC/DRC・Freerouting） |

## 決定事項

グリルセッション（3 ラウンド）で D1〜D12 を確定。詳細は `pcb-demo/REQUIREMENTS.md` §1。要点:

- 手持ちの現物 DIP IC をソケットに挿す方式（JLCPCB は SMD 周辺回路のみ実装）
- 回路トポロジは全タイル共通。型番差分は**電源ピン配線・未実装セル・シルクの 3 点だけ**
- JLCPCB Economic 組立 + ソケットは手はんだ
- 33×50mm タイル / 100×100mm パネルに 6 枚 / パイロット 12 型番 / 予算 30,000 円
- `getstarting/` は git 追跡外。公開時に新規リポジトリへスカッシュ移行
- ライセンスは MIT 継続（ハードウェア設計データも MIT と明記）

### 仕様策定中に見つかった設計上の問題

要件定義 D10 の当初案「SPST スイッチ + 10kΩ プルダウン」は **TTL ファミリで成立しない**。
74LS の入力は L のとき最大 0.4mA を吐き出すため、10kΩ では入力が 4V まで浮き VIL(max) 0.8V を超える。
**SPDT スイッチ + 1kΩ 直列**に変更し、CMOS / TTL 両対応とした（計算根拠は `pcb-demo/_carrier/README.md` §2.2）。
副次的にプルダウン抵抗 18 本が不要になり部品点数も減った。

## 変更点（触ったファイル）

| ファイル | 操作 | 備考 |
|---|---|---|
| `pcb-demo/REQUIREMENTS.md` | **新規** | 要件定義書。決定事項・設計/製造/検証要件・コスト管理・段階計画・非目標・リスク・ツール役割分担 |
| `pcb-demo/_carrier/README.md` | **新規** | 共通キャリア設計仕様。回路方式と動作点計算・部品構成・命名規則・型番別生成規則・禁止事項 |
| `pcb-demo/ORDER_CHECKLIST.md` | **新規** | JLCPCB 発注ゲート（A 設計データ / B 検証 / C 部品 / D 製造データ / E 発注 / F 発注後） |
| `.gitignore` | 変更 | `getstarting/`、`pcb-demo/**/gerber/`、`*-backups/`、`*.kicad_prl` を追加 |
| `getstarting/*.json` 5 件 | **追跡解除** | `git rm --cached`。ファイルはローカルに残置 |
| `pcb-demo/**/*.kicad_prl` 162 件 | **追跡解除** | AGENTS.md の既存方針（除外推奨）を実施 |
| `README.md` | 変更 | ライセンス節に「ハードウェア設計データも MIT」を明記 / `getstarting/` が git 管理外である旨 / PCBA 節を追加 |
| `AGENTS.md` | 変更 | ディレクトリ構造更新 / 「PCBA 化プロジェクト」節 / 「KiCAD MCP Server」節 / 禁止事項に 9 を追加 |
| `.github/copilot-instructions.md` | 変更 | AGENTS.md と同内容をミラー（CLAUDE.md の規定による） |

## 実行コマンド（再現手順）

```bash
# 私物データの追跡解除（ファイルは残る）
git rm --cached -r getstarting/

# KiCAD ローカル状態ファイルの追跡解除
git rm --cached $(git ls-files 'pcb-demo/**/*.kicad_prl')
```

調査に使ったコマンド:

```bash
python scripts/audit_kicad_coverage.py          # 実シンボル化カバレッジ（119/162）
grep -rl "| Pin | Name |" usage --include=01_basic_function_demo.md | wc -l   # 27
```

## 検証結果

- `git status`: 削除 167 件（`getstarting/` 5 + `.kicad_prl` 162）、変更 1 件（`.gitignore`）、新規 3 ファイル
- `getstarting/*.json` 5 件がローカルに残存していることを確認済み（スクリプト 13 本は無改修で動作）
- ドキュメント間の相互リンク（REQUIREMENTS ↔ _carrier ↔ ORDER_CHECKLIST ↔ README ↔ AGENTS）を確認

**未検証**: 回路・基板は 1 枚も作図していない。動作点計算は机上のみで実測していない。見積もりは未取得。

## 残課題

- **Phase 1**: 共通キャリア 1 枚を KiCAD MCP で作図し、ERC/DRC 0・実装密度確認・LCSC 部品確定・実見積もり取得
- **SPDT スイッチの単価**次第で廉価案（SPST + プルダウン、TTL 非対応）への縮退を判断する
- **抵抗アレイ化**の可否（Basic 部品で 4 素子 4.7kΩ / 1kΩ があるか）
- **パネライズの手段が未確定**。KiCAD MCP に専用ツールが見当たらない
- **LED 輝度**が 0.62mA で足りるかは実物確認が必要。不足なら `Rled` を下げて動作点を再計算する
- 所持 162 型番中 135 型番の **VCC/GND が一次資料未確認**。ファクトチェック手順で順次消化
- KiCAD MCP は**登録後に開始したセッションでのみ利用可能**。本作業のセッションでは未ロードだった
- コミットは未実施（ユーザー判断に委ねる）
