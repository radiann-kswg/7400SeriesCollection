# 2026-11-28 7400sCCP8 動作確認用の混載パネル 4 枚（PCB 回路制作 その５）

「7400 IC PCB回路制作 その４」（2026-09-25、D27・D28）の続き。自作 CPU 7400sCCP8（7400SeriesProcessor）の動作確認用に、7400sCCP8 で使う型番を同カテゴリ 4 個ずつ 2×2 混載パネルにし、1 回の発注にまとめる（REQUIREMENTS D33）。

## 型番の選定

7400SeriesProcessor の `hw/system.json`（v0.3）の 74 シリーズのうち、次をすべて満たすものから選んだ。

- DIP-20 以下（ソケットに入る）
- 電源ピンが角ピン（R11 に当たらない）
- クロック入力が無い、または接点 1・11（R10 に当たらない）
- 双方向ピンが無い（D19）
- 入手履歴にあり、一次資料が手元にある

| パネル | カテゴリ | 左上 A | 右上 B | 左下 C | 右下 D |
|---|---|---|---|---|---|
| data_selectors | 07_data_selectors_mux_demux | 74x157 | 74x257 | 74x151 | 74x153 |
| octal_buffers | 01_buffers_inverters | 74x240 | 74x541 | 74x540 | 74x241 |
| decoders | 06_encoders_decoders | 74x138 | 74x139 | 74x155 | 74x156 |
| multi_input_gates | 02_nand_and_gates | 74x11 | 74x30 | 74x132 | 74x20 |

74x155・74x20 は 7400sCCP8 では使わない（74x154 が DIP-24 で載らないため、同カテゴリの 4 個目として入れた）。ユーザーは 4 パネルすべてを選んだ。

対象外: 74x74 / 109 / 161 / 193 / 393（R10）、74x93（R11）、74x154 / 181（DIP-24）、74x245（D19）。

## pinspec（新規 16 件）

一次資料のピン配置図（TOP VIEW）を目視し、表がある資料は Pin Functions 表と相互確認した。

- TI SN74HC: 157（SCLS113F）/ 257（SCLS224B）/ 151（SCLS110F）/ 153（SCLS112E）/ 541（SCLS305E）/ 540（SCLS007F）/ 241（SCLS300E）/ 138（SCLS107G）/ 139（SCLS108E）/ 11（SCLS084E）/ 132（SCLS034H）。信頼度 95%
- 東芝 TC74HC240,244AP/AF,241AP/AF（2014-03-01）p.2: 74x240（所蔵の 74HC240AP は東芝製）。信頼度 95%
- TI SN74LS155A,SN74LS156（SDLS057）p.1: 74x155・74x156（出力形式は Choice of Outputs と論理記号）。信頼度 92%
- Philips 74HC/HCT30（December 1990）p.3: 74x30。信頼度 95%
- TI SN74LS20（SDLS079）p.1: 74x20（N パッケージの配置。W パッケージは別配置）。信頼度 95%
- 所蔵が XBLW 製の 157・138・139・132 は、XBLW の資料 p.4 とも一致を確認。SN74HC30N（XBLW）は XBLW・TI の資料が無く Philips で照合（所蔵品の資料での照合は未了）

判断:

- SCLS113F（74x157）の Pin Functions 表の TYPE 欄は誤り（1Y=I、2A=O など）。図・説明欄・XBLW の資料に従った
- 74x138 / 139 / 155 の出力は負論理なので active_low（赤 LED、点灯 = 選ばれた出力。D18）。TI の 138 の図は上線なしだが、機能表と XBLW の資料は active LOW
- 74x156 は open_collector（D29）。overview の説明「BCD to decimal decoder」は一次資料と合わないので silk_desc / silk_desc_jp を書いた（D32）。overview 本体の修正はユーザー判断
- 74x240 / 540 / 151 の W の反転出力は補出力として active_low を付けない（D18。74x04 と同じ扱い）
- 74x241 の 2OE（19 ピン）は正論理
- 74x30 の 9・10・13、74x20 の 3・11 は NC

## 生成と検証

```powershell
# .temp/gen_tiles_20261128.ps1（generate_specimen_tile.py → kicad-cli erc / drc --schematic-parity → export_bom.cmd）
powershell -NoProfile -ExecutionPolicy Bypass -File .temp\gen_tiles_20261128.ps1 74x157 74x257 ...
# .temp/build_panel_20261128.ps1（build_mixed_panel.py → drc → export pos → CPL 整形と BOM 照合 → gerbers / drill → ZIP → pcb render）
powershell -NoProfile -ExecutionPolicy Bypass -File .temp\build_panel_20261128.ps1 data_selectors 74x157 74x257 74x151 74x153
```

- 16 タイル: ERC 0 errors / 0 warnings、DRC violations 0 / unconnected 0 / footprint errors 0（`--severity-all --schematic-parity`）
- 4 パネル: DRC 0。BOM↔CPL は 116 / 148 / 116 / 90 件で完全一致、全件 Top、BOM 5 行
- 既存の追跡ファイル（`Specimen.pretty` など）に差分なし
- panel_top.png を 4 枚とも目視（シルクの型番・説明・ピン名）
- クロックセルが無いので Extended 部品は C3008585 の 1 種（$3）

## レビュー（ユーザー依頼。partsplan:circuit-review の手順、kicad-happy、pinspec の機械照合）

使ったもの:

- pinspec 16 件と KiCad 10 標準シンボル（74xx.kicad_sym、74LS 系）のピン番号・方向の突き合わせ（`.temp/xcheck_pinspec_20261128.py`）: 15 件一致。74x156 だけ差異（KiCad の 74LS156 は 74LS155 の派生で出力をトーテムポール扱い）。TI の資料の Open-Collector が正しいと判断し pinspec はそのまま
- kicad-happy（analyze_schematic / analyze_pcb --full / cross_analysis / analyze_emc / analyze_gerbers）を 74x156・74x541 のタイルと decoders パネルのガーバーに実行
  - LR-001（LED に電流制限抵抗なし）× 18: 誤検出。全 LED が Rk 4.7kΩ と直列であることをネットで確認（74x156 は +5V→Dk→Rk→ピン、74x541 はピン→Rk→Dk→GND）
  - PS-002 / GP-001（+5V プレーンの分断・参照面の欠け）: 電源プレーンの無い 2 層・静的信号の基板では想定どおり
  - PM-002（TH2 が基板端から 0.8mm）: D27 で意図したツーリングホール
  - TE-001（テストポイントなし）: 展示用タイルでは対象外
  - ガーバー: 所見 0 件
  - 実行しなかったもの: analyze_thermal（スクリプトの import エラー。発熱部品が無いので影響なし）、SPICE（シミュレータ未導入。RC など対象回路も無い）、ライフサイクル監査（API キーなし）

所見（REQUIREMENTS に R12・R13 として記録）:

1. R12（major・条件付き）: TTL 品を挿すと LED 表示が弱い。§2 の LED 電流は「出力 H ≈ 5V・Vf ≈ 2.0V」の前提だが、TTL の VOH は min 2.7V / typ 3.4V（SN74LS155A、TI SDLS057 p.6）、無印 74155 は min 2.4V。白 LED C2290 の Vf は 2.6〜3.1V（5mA）。白 LED は VOH typ で約 0.2mA、min でほぼ 0。プルアップの赤 LED は出力 H でも 5V − VOH がかかり、VOH min なら約 0.1〜0.2mA（点灯時の 1/3 程度）。今回の型番で所蔵に TTL 品があるのは 157 / 257 / 151 / 153 / 240 / 241 / 155 / 156 / 139 / 11 / 30 / 132 / 20。既存タイルにも当てはまる
2. R13（major・計算で確認）: 74x157 に 74S157 を挿すと ~{A}/B・~{G} の L が保証外。SN74S157 の IIL は ~{A}/B・~{G} が最大 −4mA（TI 1985 The TTL Data Book Vol. 2、PDF 646 ページ）。4mA × 220Ω = 0.88V > VIL(max) 0.8V
3. 確認して問題なしとしたもの: 入力の L（Rd 220Ω）は 74155 の IIL −1.6mA で 0.35V、74S132 / 74S20 / 74H30 の −2mA で 0.44V で VIL 内。TTL 出力の H に対する LED 負荷（約 0.2mA）は IOH −400µA 内。74x156（OC）の点灯時シンク電流 約 0.6mA は IOL 内。オフ時の漏れ（'LS156 の IOH 最大 100µA）で薄く光る可能性は D29 の既知事項

## 変更点

- `pcb-demo/_carrier/pinspec/` に 16 件
- `pcb-demo/_carrier/tiles/` に 16 タイル（回路図・基板・BOM・erc.rpt・drc.rpt）
- `pcb-demo/_carrier/panels/` に 4 パネル（パネル基板・BOM・CPL・Gerber ZIP・panel_top.png・ORDER.md）
- `pcb-demo/REQUIREMENTS.md` v0.14: D33、R12、R13

## 残課題

- R12: テスト発注その 1 のタイルに TTL 品を挿して LED の見え方を確かめる。対策（Rled の値・LED の色）の要否はユーザー判断
- R13: 74x157 タイルの 74S157 の扱い（HC / F 品に限る運用か、外部で GND に落とすか）はユーザー判断。DM74S157N の IIL は未確認
- 4 パネルの ORDER.md の未チェック項目（V-cut、銅箔と基板端、最小パターン幅、CPL 回転、Gerber ビューア、在庫、E・F 節）と JLCONE での実見積もり（混載パネルの見積もりは未取得）。4 パネル同時発注の予算はユーザー判断
- 74x156 の overview の説明（BCD to decimal decoder）の修正はユーザー判断
- SN74HC30N（XBLW）の所蔵品の資料での照合
- タイル BOM の出力手順 `.temp/export_bom.cmd`、生成・パネル用の `.temp/*_20261128.*` は Git 管理外の一時ファイル
- commit / push は未実施（ユーザー指示待ち）
