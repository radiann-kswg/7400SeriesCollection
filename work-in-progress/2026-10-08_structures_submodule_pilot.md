# 2026-10-08 回路構造資料 7400SeriesStructures の新設とサブモジュール導入（パイロット）

7400 シリーズの電気電子回路構造（ファミリ別のトランジスタレベル構造＋ゲートレベルの「構造の型」）を別リポジトリ `7400SeriesStructures` にまとめ、本リポジトリへ `structures/` サブモジュールとして同梱する。設計は grilling 形式のインタビュー（Q1〜Q13）で確定。

## 決定事項（インタビューより）
- 粒度: (a) ファミリ別の物理構造 ＋ (d) 構造の型 をベースに、(b)(c) 型番別のゲートレベル構造は `parts/` で補足
- 別リポジトリにする理由: 他リポジトリからの再利用、ライセンス／公開範囲の分離、Collection の肥大化回避、独立した読み物としての公開
- 対象ファミリ: 標準 TTL ＋ 手持ちにあるファミリ（H / S / LS / ALS / AS / F / HC / HCU / HCT / AHC / ACT / ABT）を優先、次に AC / LV / LVC 等
- 図: KiCAD `.kicad_sch` を正本、`kicad-cli sch export svg --exclude-drawing-sheet --no-background-color` で SVG を書き出してコミット。1 図 1 ファイル、標準に無いシンボルだけ `lib/structures.kicad_sym`
- 言語・ライセンス・公開: 日本語 / MIT / public。Structures から `getstarting/` は参照しない
- 出典: families はデータシート・アプリケーションノートを出典に描き直し（DocID/Rev/頁併記）。patterns は一般論と明記し、型番との結び付けは本リポジトリの照合済みチートシートを参照
- 運用: 単独の作業コピー `D:\VisualStudio Code Userfile\7400SeriesStructures` で編集 → push → 本リポジトリのポインタ更新。サブモジュール内で直接編集しない

## 実施
1. GitHub に `radiann-kswg/7400SeriesStructures`（public、空）を作成し clone
2. スケルトン: README / LICENSE / AGENTS.md / .gitignore / `scripts/export_svg.py` / `lib/structures.kicad_sym`（Q_NPN_2E マルチエミッタ、Q_NPN_Schottky、NAND2、NOT）
3. パイロット図 9 枚を生成（KiCAD 8 互換形式 20231120、KiCAD 10 の kicad-cli で SVG 化を確認）
   - `families/ttl_std/`: nand_gate / output_totem_pole / output_open_collector / output_three_state
   - `families/cmos_hc/`: nand_gate / input_protection
   - `patterns/05_flipflops_latches/`: sr_latch_nand / d_latch / d_flipflop_edge
4. 解説: `families/ttl_std/README.md`、`families/cmos_hc/README.md`、`patterns/05_flipflops_latches/README.md`、`parts/74x00.md`、各 index README
5. 一次資料照合: 標準 TTL の抵抗値（4 kΩ / 1.6 kΩ / 130 Ω / 1 kΩ）は TI SDLS029C（SN7404、2004-01 改訂）p.4 "schematics (each gate)" を目視確認（信頼度 97%）。現行 SN7400 データシート SDLS025D（2017-05）にはトランジスタ回路図が無いことも確認
6. ERC: 9 枚とも `pin_not_driven` / `power_pin_not_driven`（外部入力・PWR_FLAG 無し）以外のエラー無し。Markdown のリンク切れ 0
7. 本リポジトリ側: `AGENTS.md` / `.github/copilot-instructions.md` に「回路構造資料（structures/ サブモジュール）」節を追加、`README.md` のツリーと `usage/index.md` に導線を追加

## 未実施（ユーザー指示待ち）
- Structures の初回 commit / push（パイロット確認後に指示）
- その後に本リポジトリで `git submodule add https://github.com/radiann-kswg/7400SeriesStructures.git structures` と commit
- `generate_usage_cheatsheets.py` の雛形への `structures/parts/` リンク追加は `parts/` が増えてから

## メモ
- 図の初回生成には Structures の `.temp/gen_sch.py`（Git 管理外のブートストラップ）を使った。以後の修正は KiCAD で `.kicad_sch` を直接編集し、`scripts/export_svg.py` で SVG を再生成する
- KiCAD 10 の `Device` ライブラリではトランジスタ名が `Q_NPN` / `Q_NMOS` / `Q_PMOS`（`_BCE` / `_GSD` 接尾辞無し）
- 回転した部品のプロパティ文字を水平に保つには property の角度を `(360 − 回転) % 360` にし、90° 回転のときだけ justify を左右反転する必要があった
- `.temp/` に sn7400.pdf とレンダリング PNG が残っている（VM から削除できないため。Git 管理外）
