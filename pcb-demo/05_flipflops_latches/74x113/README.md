# 74x113 Demo PCB

> このファイルはスクリプトにより自動生成されたスタブです。
> 回路の詳細（ピン配置・真理値表・サンプル回路）は一次資料を確認後、以下を参照して補完してください。

## IC 情報

| 項目                 | 内容               |
| -------------------- | ------------------ |
| **汎用型番**         | `74x113`  |
| **機能 (EN)**        | Dual JK flip-flop, negative-edge-triggered, set and reset    |
| **機能 (JP)**        | 2回路JKフリップフロップ（負論理エッジトリガ、セット・リセット付き） |
| **カテゴリ**         | `05_flipflops_latches`     |
| **入手済み (CMOS)**  | (なし)     |
| **入手済み (TTL)**   | SN74S113N      |
| **入手済み (Other)** | (なし)    |

## KiCAD プロジェクト構成

| ファイル                    | 役割                                             |
| --------------------------- | ------------------------------------------------ |
| `74x113.kicad_pro` | KiCAD プロジェクトファイル                       |
| `74x113.kicad_sch` | 回路図（スタブ — 要作成）                        |
| `74x113.kicad_pcb` | PCB レイアウト（50×50mm 外形済み）               |
| `74x113.kicad_sym` | カスタムシンボルスタブ（KiCAD 標準 74xx を推奨） |

## KiCAD 標準ライブラリの利用（推奨）

KiCAD 10 には 74xx シリーズのシンボル・フットプリントが標準収録されています。
カスタムシンボル (`.kicad_sym`) を自作するより、以下を優先してください。

- **シンボル**: `Add Symbol` → `74xx` ライブラリ
- **フットプリント**: `Package_DIP` / `Package_SO` など

## 関連ドキュメント

- 回路設計情報（usage）: [`usage/05_flipflops_latches/74x113/`](../../../usage/05_flipflops_latches/74x113/)
- データシート収集状況: [`datasheets/7400_series_ic_datasheet_collection_status.json`](../../../datasheets/7400_series_ic_datasheet_collection_status.json)
- 入手履歴: [`getstarting/7400_series_ic_collection_acquisition_history.json`](../../../getstarting/7400_series_ic_collection_acquisition_history.json)

## 設計チェックリスト

### 回路設計前（必須確認）

- [ ] 使用 IC の実型番・パッケージを決定（DIP-14 / DIP-16 / SOP-14 等）
- [ ] 対応データシートの一次資料でピン配置・真理値表を確認
- [ ] `usage/05_flipflops_latches/74x113/` のファクトチェックが完了している

### PCB 設計

- [ ] 電源デカップリング（0.1µF）を VCC–GND 直近に配置
- [ ] 未使用入力をプルアップ/プルダウンで固定（CMOS ファミリは特に重要）
- [ ] デモ用 LED の電流制限抵抗を計算・配置
- [ ] DIP パッケージなら 2.54mm ピッチのフットプリントを使用
- [ ] 基板外形（50×50mm）内に全部品が収まっていること
- [ ] Edge.Cuts レイヤーの外形線が閉じていること
- [ ] DRC（Design Rule Check）を実行してエラーゼロを確認

### 出力（製造前）

- [ ] Gerber ファイルを `gerber/` サブディレクトリに出力
- [ ] ドリルファイル（`.drl`）を同梱
- [ ] `kicad-cli pcb export gerbers` で CLI 出力を確認
