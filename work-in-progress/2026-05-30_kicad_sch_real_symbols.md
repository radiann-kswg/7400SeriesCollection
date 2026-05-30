# 2026-05-30 実シンボル回路図生成機能の実装

## 目的

`pcb-demo/` 配下の `.kicad_sch` を「テキストアノテーション方式」から
「KiCAD標準ライブラリシンボルを使った実回路図」に刷新する。

## 変更点（触った主要ファイル）

### 新規作成

- `scripts/kicad_sch_gen.py`
  - KiCAD 8形式 (version 20231120) の実回路図を生成するモジュール
  - `build_real_kicad_sch(part_number, replacements) -> str | None` がメインAPI
  - KiCAD 10 ライブラリ (`C:\Program Files\KiCad\10.0\share\kicad\symbols\`) から
    シンボル定義を読み込み、lib_symbols に埋め込む
  - ピン解析: `parse_pins_by_unit()` でサブシンボル `{sym}_N_M` からユニット別ピン情報を抽出
  - 座標変換: ライブラリ Y-up → スキーマティック Y-down (`abs_y = sym_y - local_y`)
  - 配置レイアウト:
    - ゲートユニット1: デモゲート（IN_A/IN_B等のネットラベル付き）
    - ゲートユニット2〜4: ノーコネクトマーク付き
    - 電源ユニット: VCC/GND power シンボル自動配置

- `.temp/debug_pins.py`: ピン解析デバッグスクリプト（作業用）
- `.temp/check_pin_names.py`: ライブラリピン名確認スクリプト（作業用）

### 変更

- `scripts/generate_pcb_demo_projects.py`
  - インポートブロックに `kicad_sch_gen` の遅延インポートを追加（ImportError 対応）
  - `.kicad_sch` 生成部分を 3段階フォールバックに変更:
    1. `kicad_sch_gen.build_real_kicad_sch()` → 実シンボル回路図（優先）
    2. `build_sch_from_demo()` → テキスト注釈版（fallback）
    3. テンプレートスタブ（最終fallback）

## 対応部品 (PART_TO_KICAD_SYM)

以下 47 種類が実シンボル回路図に対応:

```
バッファ/インバータ: 74x04, 74x05, 74x06, 74x07, 74x14, 74x125, 74x126
NAND: 74x00, 74x10, 74x20, 74x30, 74x133
NOR: 74x02, 74x27
AND: 74x08, 74x11
OR: 74x32
XOR: 74x86, 74x266
フリップフロップ: 74x74, 74x76, 74x112
ラッチ/レジスタ: 74x75, 74x373, 74x374
MUX: 74x151, 74x153, 74x157, 74x158
デコーダ: 74x138, 74x139, 74x154, 74x155, 74x156
カウンタ: 74x90, 74x93, 74x160, 74x161, 74x163, 74x192, 74x193
算術: 74x283, 74x181
シフトレジスタ: 74x164, 74x165, 74x166, 74x194, 74x595
```

入手済み部品のうち上記に含まれないもの（例: 74x141, 74x04系特殊品等）は
テキスト注釈版またはテンプレートスタブにフォールバック。

## 技術的知見

### KiCAD 座標系

- ライブラリシンボル: Y-up（数学標準）
- スキーマティック絶対座標: Y-down（画面下方向が+Y）
- 変換: `abs_x = sym_x + local_x`, `abs_y = sym_y - local_y`

### KiCAD 10 ライブラリのピン形式

- 74LS00 等のゲート IC はピン名 `""` (空文字列) を使用
- ピン名が空の場合は位置順に A, B, C... / Y, Z... で命名
- 電源ピンは `(name "GND"/"VCC")` で識別可能

### サブシンボル命名規則

- `{sym_name}_{unit}_{body_style}`
- unit=1〜N: 個別ゲート/機能ユニット、body_style 0/1/2
- 電源ユニットは最大番号のユニット（power_in 型ピンを含む）

### lib_symbols 埋め込み

- ライブラリから抽出したシンボル定義の外側 `(symbol "74LS00" ...)` を
  `(symbol "74xx:74LS00" ...)` に変換（先頭1箇所のみ replace）
- 内部サブシンボル名（`74LS00_1_1` 等）はそのまま保持

## 実行コマンド（再現手順）

```powershell
# 全部品を再生成（既存上書き）
python3 scripts/generate_pcb_demo_projects.py --apply --overwrite

# 特定部品のみ
python3 scripts/generate_pcb_demo_projects.py --apply --overwrite --part 74x00

# KiCAD CLI でSVG出力検証
&"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe" sch export svg --output .temp/test_sch_export pcb-demo/02_nand_and_gates/74x00/74x00.kicad_sch
```

## 検証結果

- 74x00 (Quad 2-input NAND): KiCAD CLI SVG出力成功 (317KB)
  - IN_A, IN_B, OUT_Y ネットラベル ✓
  - VCC/GND 電源シンボル ✓
  - 全4ゲートユニット + 電源ユニット配置 ✓
- バッチ検証（全164件）: 実行済み（結果は next session 参照）

## 残課題

- [ ] 全164件のバッチKiCAD CLI検証完了確認
- [ ] 各ICをKiCADアプリで実際に開いてビジュアル確認
- [ ] `PART_TO_KICAD_SYM` に未登録の入手済み部品（74x141等）への対応
  - 74x141 は KiCAD標準ライブラリに存在するか要確認（`74xx.kicad_sym` で検索）
- [ ] `.temp/batch_svg/` の一時ファイル削除（作業完了後）
- [ ] `.temp/debug_pins.py`, `.temp/check_pin_names.py` の削除（作業完了後）
