# 2026-06-15 KiCAD 回路図生成の自動化強化

## 目的

「最小デモ回路図を KiCAD で自動生成する」際に残っていた手動作業を、既存アセット・
パッケージで可能な限り排除する。具体的には次の 4 点:

1. ERC 検証の自動化（GUI で開いて目視確認する工程の排除）
2. 自前正規表現パーサの堅牢化（`sexpdata` ベースへ）
3. 対応部品のライブラリ自動探索化（ハードコード 47 種 → 入手済み全型番へ拡張）
4. PCB 下流（配置〜配線〜Gerber）のパイプライン化

## 変更点（触ったファイル）

- 追加 `scripts/kicad_lib.py`: `.kicad_sym` を sexpdata で解析する共通モジュール。
  シンボル列挙 / `extends` 解決 / ユニット別ピン抽出 / `74xNN`→実シンボルの自動探索
  (`discover_symbol`) / フットプリント選択補助。**依存: `pip install sexpdata`**。
- 変更 `scripts/kicad_sch_gen.py`:
  - 先頭で `kicad_lib` を遅延 import（失敗時は従来正規表現にフォールバック）。
  - `PART_TO_KICAD_SYM` を「オーバーライド表」に格上げ。未登録型番は
    `kicad_lib.discover_symbol` が `74xx.kicad_sym` を走査して自動解決。
  - ピン解析を sexpdata 優先に（`parse_pins_by_unit` は正規表現版も残置しフォールバック）。
  - `pick_footprint()` を追加し、ピン数から DIP フットプリントを自動割当
    （`(property "Footprint" ...)` に反映）。
- 追加 `scripts/verify_kicad_sch.py`: `kicad-cli sch erc` で生成済み `.kicad_sch` を
  ヘッドレス一括検証。実シンボル回路図のみ対象化(`--only-real`)・JSON レポート保存可。
- 追加 `scripts/audit_kicad_coverage.py`: 入手済み全型番の実シンボル化可否
  （override / discover / none）を一覧・CSV 出力。
- 追加 `scripts/generate_pcb_layout.py`: 回路図→PCB の下流パイプライン
  （erc / netlist / place / route / drc / gerber のステージ制）。
  kicad-cli ステージは通常 python、place/route は **KiCAD 同梱 python**(`import pcbnew`)、
  route は Freerouting(`java -jar freerouting.jar`)が必要。
- 変更 `.vscode/tasks.json`: ERC 検証 / カバレッジ監査 / PCB パイプライン(2種)のタスク追加。
- 変更 `AGENTS.md`, `.github/copilot-instructions.md`: 上記スクリプト・依存・手順を反映。

## 実行コマンド（再現手順 / Windows 実機）

```powershell
pip install sexpdata
# 1) カバレッジ確認（74xx.kicad_sym 実在型番の数）
python scripts/audit_kicad_coverage.py --csv coverage.csv
# 2) 回路図を（自動探索込みで）再生成
python scripts/generate_pcb_demo_projects.py --apply --overwrite
# 3) ERC ヘッドレス検証
python scripts/verify_kicad_sch.py --only-real
# 4) PCB 下流（netlist まで＝通常 python）
python scripts/generate_pcb_layout.py --stages erc,netlist
# 5) 配置〜Gerber（KiCAD 同梱 python + Freerouting）
& 'C:\Program Files\KiCad\10.0\bin\python.exe' scripts/generate_pcb_layout.py `
    --part 74x00 --freerouting-jar C:\tools\freerouting.jar
```

## 検証結果（Linux サンドボックスで実施した範囲）

- sexpdata パーサ vs 旧正規表現パーサ: 生成済み 20 回路図の埋め込み実シンボルで
  ユニット構成・ピン番号集合が **20/20 完全一致**。
- 自動探索 `discover_symbol`: 合成ライブラリで動作確認（候補生成＋フォールバック正規表現）。
  非標準型番（74x1000 等）は正しく未解決→テキスト版へフォールバック。
- 生成器 E2E（フィクスチャから組んだ簡易 74xx/power ライブラリ使用）:
  override / discover 両経路で **有効な S 式**を生成、74x00 は旧コミット版と同一構成
  （部品5＋電源2 / netlbl3 / nc9）。フットプリントは 74x00→DIP-14, 74x112/139→DIP-16 を自動付与。
- `verify_kicad_sch.py` / `generate_pcb_layout.py` の純 Python 部
  （対象収集・フィルタ・ステージ判定・netlist 正規表現）動作確認済み。

> 注: KiCAD 本体（`kicad-cli` / `pcbnew`）と実 `74xx.kicad_sym` は Windows 側のみ。
> ERC 実行・自動探索の実カバレッジ・pcbnew 配置・Freerouting 配線は **Windows 実機での検証が必要**。

## 残課題

- `audit_kicad_coverage.py` を Windows で実行し、自動探索後の実カバレッジ（118 未対応の
  うち何件が解決するか）を確定する。`PART_TO_KICAD_SYM` の curated 選択（ファミリ優先）を
  必要に応じて調整。
- `generate_pcb_layout.py` の place/route ステージ（pcbnew の `FootprintLoad` /
  `ExportSpecctraDSN` / `ImportSpecctraSES` のシグネチャ）を KiCAD 10 同梱 python で実検証。
  バージョン差があれば吸収する。
- デカップリング 100nF をネットリスト／配置に自動投入する処理は未実装（現状 IC のみ配置）。
- 一次資料未確認の型番を実シンボル化する場合も、ピン配置の最終確認はファクトチェック完了が前提。
