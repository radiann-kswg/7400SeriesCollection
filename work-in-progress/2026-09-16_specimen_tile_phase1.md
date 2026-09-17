# 2026-09-16 Specimen Tiles Phase 1 着手（代表 3 型番のタイル生成）

## 目的

`pcb-demo/REQUIREMENTS.md` Phase 1 として、共通キャリアを代表型番で作図し、ERC/DRC 0・実装密度・LCSC 部品を確認する。
代表型番はユーザー指定で **74x00（DIP-14）/ 74x244・74x273（DIP-20）** の 3 つ。

## 決定事項（ユーザー確認済み）

| 項目 | 決定 |
|---|---|
| 作図手段 | Cowork からは KiCAD MCP が使えない（Claude Code の `~/.claude.json` にのみ登録）ため、KiCAD 同梱 Python（pcbnew）で動く生成スクリプトで代替 |
| SPDT スイッチ | **SHOU HAN MSS12C02LS-BB2.0（LCSC C3008585, Extended）**。上面操作・6.65×2.75mm・500+ で $0.0669 |
| 抵抗 | **個別 0603**（配置が混まなければ個別、混む場合のみ 4 素子アレイ）。今回の配置では混まないので個別 |

## LCSC 部品（2026-09-16 時点。発注直前に在庫・価格を再確認）

| 用途 | LCSC | MPN | 区分 |
|---|---|---|---|
| Rd 1kΩ 0603 | C21190 | UNI-ROYAL 0603WAF1001T5E | Basic |
| Rled 4.7kΩ 0603 | C23162 | UNI-ROYAL 0603WAF4701T5E | Basic |
| LED 赤 0603 | C2286 | Hubei KENTO KT-0603R | Basic |
| C1 100nF 0603 | C14663 | YAGEO CC0603KRX7R9BB104 | Basic |
| SPDT | C3008585 | SHOU HAN MSS12C02LS-BB2.0 | Extended |
| （参考）抵抗アレイ 1k / 4.7k | C20197 / C1980 | UNI-ROYAL 4D03WGJ0102T5E / 4D03WGJ0472T5E | Basic |

- スイッチは Basic / Preferred が存在しない。CAS-120TA（C2921534）は単価 $0.43〜0.52 でパイロット予算を超えるため不採用。
- DTS04GE（C3294670）は SPDT ではなく三態（+ / 0 / −）DIP スイッチ。中立で入力が浮くので不採用。
- C2286 の光度は 145〜300 mcd @20mA（データシートのテキスト抽出。0.6mA での明るさは未確認）。

## 設計上の判断

### タイル外形 33×50mm は成立しない → 50×50mm に変更（**D9 変更をユーザー承認済み**: 100×100mm パネルに 2×2 = 4 枚）

MSS12C02LS のランド込み外形は約 8.4×4.1mm。18 個を操作可能な間隔で並べ、LED・抵抗 36 本・ソケットと合わせると 33mm 幅に収まらない（横方向に最低約 40mm 必要）。
50×50mm なら下記の規則配置で自動配線なしに収まった。100×100mm パネルには 2×2 = 4 枚（6 枚面付けなら 150×100mm）。

### レイアウト（`scripts/generate_specimen_tile.py`）

- ソケット U1 は横置き（ピン 1 左下）。接点 1〜10 の I/O 列を下側、20〜11 を上側に 4.6mm ピッチで並べる
- 1 列 = 外周側から スイッチ（縦置き）→ LED / Rled / Rd（縦置き 0603）→ ソケットへの引き出し
- 引き出し線は外側の列ほどソケット寄りのレーンを使う（0.5mm ピッチ、交差なし）
- +5V: 外周レール（上・下・左、0.5mm）＋ソケット下を通って VCC 接点へ行くバス。GND: 裏面ベタ＋ビア
- スイッチの共通端子は両側の切替端子に挟まれているため、位置決め穴を避けて本体下を通して引き出す
- 部品は上面のみ。U1・J1 は BOM/CPL 除外属性、未使用接点のセルは DNP
- シルク: 各列のピン名（VCC/GND 含む）、型番・機能名（英・和）、給電表示。裏面に版・カテゴリ・MIT

### 仕様書との差分（v0.2 で反映済み）

| 仕様書 | 今回 |
|---|---|
| 外形 33×50mm、パネル 3×2 | 50×50mm、パネル 2×2（または 150×100mm に 3×2） |
| スイッチ `SW1`–`SW5`（4 連 × 5） | 単体スイッチ `SWk`（接点番号と 1 対 1） |

## 変更点（触ったファイル）

| ファイル | 操作 |
|---|---|
| `scripts/generate_specimen_tile.py` | 新規。ピン表（`usage/**/01_basic_function_demo.md`）から VCC/GND・ピン数を読み、回路図・基板・プロジェクトを生成 |
| `pcb-demo/_carrier/Specimen.pretty/SW_SPDT_Shouhan_MSS12C02LS.kicad_mod` | 新規（生成物）。KiCAD 標準 `SW_SPDT_Shouhan_MSK12C02` のランドを流用し、courtyard を本体寸法に詰めたもの |
| `pcb-demo/_carrier/tiles/{74x00,74x244,74x273}/` | 新規（生成物）。`*_tile.kicad_{sch,pcb,pro}` と `fp-lib-table` |
| `pcb-demo/REQUIREMENTS.md` | v0.2。D9 を 50×50mm / 2×2 に変更、D13（スイッチ）・D14（抵抗）追加、R2 解決、R8（スイッチのランド未照合）追加 |
| `pcb-demo/_carrier/README.md` | v0.2。部品の LCSC 番号、`SWk` 命名、寸法・配置規約、Phase 1 チェック、§9 生成手順 |
| `pcb-demo/ORDER_CHECKLIST.md` | スイッチのランド照合・回路図等価性の項目を追加 |
| `AGENTS.md` / `.github/copilot-instructions.md` | ディレクトリ構造に `_carrier/tiles/`、スクリプト一覧に `generate_specimen_tile.py` を追加 |

## 実行コマンド（再現手順・Windows）

```powershell
& 'C:\Program Files\KiCad\10.0\bin\python.exe' scripts\generate_specimen_tile.py 74x00 74x244 74x273
$cli = 'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
& $cli sch erc --severity-all pcb-demo\_carrier\tiles\74x244\74x244_tile.kicad_sch
& $cli pcb drc --severity-all --schematic-parity pcb-demo\_carrier\tiles\74x244\74x244_tile.kicad_pcb
```

## 検証結果

| 型番 | 実装セル / DNP | ERC | DRC（警告含む） | 未配線 | 回路図との等価性 |
|---|---|---:|---:|---:|---:|
| 74x00（DIP-14, VCC=接点20, GND=接点7） | 12 / 6 | 0 | 0 | 0 | 0 |
| 74x244（DIP-20, VCC=20, GND=10） | 18 / 0 | 0 | 0 | 0 | 0 |
| 74x273（DIP-20, VCC=20, GND=10） | 18 / 0 | 0 | 0 | 0 | 0 |

- 3D レンダリングで配置・シルク（和文含む）・DNP の抜けを目視確認
- kicad-happy 解析（74x244）: `LR-001`（LED の電流制限抵抗なし）は誤検出（D の陽極側に Rk 4.7kΩ が直列。抵抗の反対側が電源でなく IC ピンのため検出されない）。`PS-002`（+5V 分断）も誤検出（レールへの T 字接続を解析器が接続とみなさない。KiCAD DRC の未配線は 0）
- 生成時にスイッチ・LED・ソケット・C1 のパッド座標を assert で照合（回転方向の取り違え防止）

**未検証**: MSS12C02LS のランド寸法（LCSC のデータシートに寸法図が無い）、スイッチの H/L 方向、LED の実輝度、見積もり。

## つまずき（再発防止）

- `pcbnew.FootprintLoad()/FootprintSave()` はライブラリ形式の推定に失敗することがある → `PCB_IO_KICAD_SEXPR()` を毎回生成して使う
- pcbnew でフットプリントの図形を `Remove()` して保存すると、以降の `FootprintLoad()` が型の壊れたオブジェクトを返す → `.kicad_mod` はテキストで加工
- 回路図のローカルラベルは基板側では `/P1` のようにシート名付きのネット名になる（そろえないと等価性チェックで 126 件）
- Cowork の VM から `git status` を実行すると `.git/index.lock` が残り、Windows 側の git が止まる → VM では `git --no-optional-locks` を使う（残った場合は Windows 側で削除）

## 残課題

- MSS12C02LS の寸法図（メーカー資料）でランド・端子配置・位置決め穴を照合。照合後に H/L のシルクを追加
- パネライズ手段（R6）と実見積もり（R1）
- 残り 9 型番（パイロット）の生成。ピン表があれば同じコマンドで生成できる
- BOM / CPL の JLCPCB 形式出力（Phase 1 ⑤。承認後）

## 追加要望: 出力接点は LED のみ（2026-09-16、実施済み）

ユーザー方針: **基板生成の前段で各ピンの方向をデータシートで確認する工程を入れる**。IC の機能に合った回路にするため。

### やったこと

| ファイル | 操作 |
|---|---|
| `pcb-demo/_carrier/pinspec/{74x00,74x244,74x273}.json` | 新規。TI データシート（SCLS181H / SCLS130H / SCLS136F）の Pin Functions 表を `render_datasheet_pages.py` で PNG 化して目視。全ピンの方向・属性・参照ページ・信頼度 95% を記録 |
| `scripts/generate_specimen_tile.py` | usage のピン表ではなく pinspec を読む。セル種別: `input`/`bidirectional` = 全実装、`output`/`tri_state` = LED のみ（`SWk`・`R(20+k)` DNP）、未使用・`nc`・`open_collector` = 全部 DNP |
| `pcb-demo/REQUIREMENTS.md` | v0.3。D5 改訂、D15（ピン仕様確認工程）追加、§2.3 ②、§4.1（確認工程の手順）、Phase 2、R3 |
| `pcb-demo/_carrier/README.md` | v0.3。安全規則・§6.2 ②・禁止事項 6・§9 |
| `pcb-demo/ORDER_CHECKLIST.md` | pinspec の確認項目、出力接点 DNP の項目を追加 |
| `AGENTS.md` / `.github/copilot-instructions.md` | 守るべき要点 1・5 を改訂 |

### 目視結果（読み取り信頼度 95%: 表が明瞭、ページまたぎなし）

| 型番 | 入力 | 出力 | 特記 |
|---|---|---|---|
| 74x00 | 1,2,4,5,9,10,12,13 | 3,6,8,11 | なし |
| 74x244 | 1(1OE 負論理),2,4,6,8,11,13,15,17,19(2OE 負論理) | 3,5,7,9,12,14,16,18（3 ステート） | OE=H で Hi-Z。Rled が GND に落とすので LED は消灯するだけで浮かない |
| 74x273 | 1(CLR 負論理),3,4,7,8,11(CLK),13,14,17,18 | 2,5,6,9,12,15,16,19 | CLK をスライドスイッチで駆動。チャタリングで複数エッジが入っても D が安定なら同じ値を再ラッチするだけで実害なし |

### 再生成後の検証

| 型番 | 入力セル / 出力セル(LED のみ) / DNP | ERC | DRC | 未配線 | 等価性 |
|---|---|---:|---:|---:|---:|
| 74x00 | 8 / 4 / 6 | 0 | 0 | 0 | 0 |
| 74x244 | 10 / 8 / 0 | 0 | 0 | 0 | 0 |
| 74x273 | 10 / 8 / 0 | 0 | 0 | 0 | 0 |

スイッチは 1 タイルあたり 18 → 10 個（74x00 は 12 → 8）。

### データシートの充足

パイロット 12 型番は TI の PDF がすべて `datasheets/_download/` にある（74x04 / 14 / 86 / 74 / 393 / 164 / 157 / 595 は SN74HC、74x238 は CD74HC138,CD74HC238.PDF）。不足する型番が出たら `scripts/fetch_missing_datasheets.py --part {型番}` で公式サイトから収集する（REQUIREMENTS §4.1）。

### 共通回路で扱えないピン（今後の型番で要相談）

- オープンコレクタ出力（74x05 / 06 / 07 等）: LED を GND 側に付けても点灯しない → pinspec で `open_collector` にすると全 DNP。別方式（プルアップ + LED を VCC 側）が要るか相談
- クロック入力のチャタリング: カウンタ・シフトレジスタ（74x393 / 164 / 595 等）は複数回カウントされる。展示としてどこまで許容するか相談

## 2026-09-16 続き: Phase 1 残タスクの対応（新規セッション）

前回グリリングで整理した6項目の決定を受けて対応。残り9型番の生成（Phase 2）は別セッションに先送り。

### コミット

未コミットだった検証済み分（ERC/DRC 0）を3コミットに分割（Windows側のgitで実施。VM側の`--no-optional-locks`回避のため、コミットメッセージはVM側でUTF-8ファイルに書き出してから`git commit -F`で渡した。PowerShellのヒアストリングに直接日本語を渡すと文字化けするため不採用）。

1. `9e2128d` 仕様書（REQUIREMENTS/README/CHECKLIST/AGENTS/copilot-instructions）をv0.3化
2. `61c36bd` `generate_specimen_tile.py`と専用フットプリントを追加
3. `b7bf798` 代表3型番のタイル生成物・pinspec・作業ログを追加

`Claude outputs/74x273_tile_top.png`（3Dレンダリングのスクリーンショット）は温存対象に見当たらないためコミット対象から除外（未追跡のまま）。

### R6 パネライズ: KiKit採用

KiCad同梱python（`C:\Program Files\KiCad\10.0\bin\python.exe -m pip install kikit`）へ導入。CLIは`C:\Users\s-chi\OneDrive\Documents\KiCad\10.0\3rdparty\Python311\Scripts\kikit.exe`（PATH未登録のためフルパス指定が必要）。

74x244タイルで検証:

```powershell
$kikit = 'C:\Users\s-chi\OneDrive\Documents\KiCad\10.0\3rdparty\Python311\Scripts\kikit.exe'
& $kikit panelize -l "type: grid; rows: 2; cols: 2; hspace: 0mm; vspace: 0mm; hbackbone: 0mm; vbackbone: 0mm" -s "type: auto" -t "type: none" -c "type: vcuts" -r "type: none" -o "type: none" -f "type: none" pcb-demo\_carrier\tiles\74x244\74x244_tile.kicad_pcb <出力先>.kicad_pcb
```

- `hspace`/`vspace`を2mmにすると102.1×102.1mmになり100×100mm価格帯を外れる。**0mmで100.1×100.1mm**（V-cutは板同士の隙間を必要としない）
- 出力先プロジェクトに`Specimen`フットプリントライブラリを指す`fp-lib-table`（`${KIPRJMOD}/../../pcb-demo/_carrier/Specimen.pretty`）を追加しないと、DRCで`lib_footprint_issues`警告が72件出る（実害無し。ライブラリ未リンクの警告のみ）
- 上記対応後、DRC 0・未配線0を確認
- 異なる型番を混在させたパネル（実際のパイロット発注で使う想定）はPhase 2で検証する

### R8 MSS12C02LSランド照合: メーカー問い合わせへ切替

LCSC公式データシート（C3008585）を確認したが、本体外形（6.65×2.75×3.4mm）のみでフットプリント図・位置決め穴・H/L方向の図面が無いことを再確認（従来の調査と同じ結論）。ユーザー方針により、LCSC/JLCPCB経由でメーカー（SHOU HAN）へ図面を問い合わせる方針に変更。問い合わせ文面はユーザーへ提示済み、送信はユーザーのアカウントから行う。回答が来るまで発注しない。

### クロック入力のチャタリング: 許容で確定

REQUIREMENTS.md §4.2に記載。74x393/164/595はデバウンス回路を追加せず、実機検証で問題が出た場合のみ再検討。

### R1 実見積もり: ユーザーがJLCONEで取得

ユーザーがHalvanに導入済みのデスクトップアプリ「JLCONE」でGerber/BOM/CPLから直接取得する方針。Claude側はパネル用製造データの書き出しまでを担当。

### 残課題

- SHOU HANからの図面回答待ち（回答後、ランド照合・H/Lシルク追加）
- 実見積もり（ユーザーがJLCONEで取得）
- 残り9型番のpinspec作成・タイル生成、混在パネルの面付け（Phase 2、別セッション）

---

## 追記（同日、旧セッションQ1-Q8反映）

### クロック入力のチャタリング方針を訂正

上記「許容で確定」は撤回する。旧セッション（本Issueより前の要件定義セッション）の最終回答Q2/A2で、タクトスイッチ+RCローパス+74x1G14シュミットトリガによるクロック整形回路を試作する方針が既に確定していたことが判明した。本セッションRound 1での「許容する」という提案は、この旧セッション回答を参照しないまま行ったものだったため誤り。REQUIREMENTS.md §4.2を全面改訂しD17として記録した。RC定数・部品選定・配置は未設計（残課題）。

### 旧セッションQ1-Q8をREQUIREMENTS.mdへ反映

D16 (Rd 220Ω化) / D17 (クロック整形回路、上記) / D18 (active_lowのみLED反転) / D19 (bidirectional検出で生成停止) / D20 (74x393非連結の再確認) / D21 (自動リセット無し・CLRシルク注記) / D22 (LED赤白2色化) / D23 (M2取付穴) として追加。`_carrier/README.md`もv0.4へ更新し、Rd変更に伴う誤操作電流の再計算（220Ωで約22.7mA、Vcc+5%/R-5%最悪条件で約25.1mA、74HC絶対最大定格±25mAに対しマージンが小さい点を要注意として明記）と、`Rd`変更禁止ラインの訂正（旧: 470Ω以下禁止 → 220Ω未満禁止）を行った。

将来検討事項として、74x60/182等の拡張ロジックIC向けRaspberry Pi HAT型スタッカブル基板フォーマットをREQUIREMENTS §7.2に記録（別Phase、設計は未着手）。

### R8 スイッチフットプリント: SHOU HAN純正図面を確認

ユーザーがSHOU HAN公式の仕様書（C3008585, Rev2, 2020-06-17）を入手。LCSCのデータシート（外形寸法のみ）より詳細で、フットプリント図（ランド配置図）が含まれる。外形寸法（7.85×6.65×2.75mm）・位置決め穴（2-⌀0.8、ピッチ3mm）は複数箇所の記載が一致し読み取り信頼度約95%（CLAUDE.mdの基準で自動確認扱い）。一方、SMDパッド（スイッチ端子3点）の中心位置を示す寸法連鎖（3mm/1.5mm/0.75mm、中心線からのオフセット）は解釈が一意に定まらず信頼度約55〜60%のため、85%未満はユーザー確認という基準に従いフットプリント確定を保留し、本セッション内でユーザーに確認を依頼した。

### 残課題（更新）

- スイッチフットプリントのSMDパッド中心位置の確認（ユーザー回答待ち）→ `SW_SPDT_Shouhan_MSS12C02LS.kicad_mod`修正 → 74x00/74x244/74x273タイル再生成・ERC/DRC再検証
- クロック整形回路（タクトスイッチ+RC+1G14）の定数設計・部品選定・レイアウト
- `generate_specimen_tile.py`の改修（Rd 220Ω、LED赤白2色ロジック、bidirectional検出で停止、CLRシルク注記、M2取付穴）
- `Rd` 220ΩとLED白のLCSC部品番号選定
- SHOU HANからの図面回答待ち（メーカー確認、進行中）
- 実見積もり（ユーザーがJLCONEで取得）
- 残り9型番のpinspec作成・タイル生成、混在パネルの面付け（Phase 2、別セッション）

---

## 追記2（同日、スイッチフットプリント確定）

R8のSMDパッド中心位置について、ユーザーがSHOU HAN純正図面(C3008585)を直接確認し、寸法連鎖の解釈を確定した。
中央パッド(端子2、共通)はホール中心線(2-⌀0.8のピッチ中点)から+0.75mmの位置に幅0.8mmで配置、
そこから左へ3mmの位置に端子1、右へ1.5mmの位置に端子3(いずれも幅0.8mm)。パッド長は
「ホール中心~上端2.6mm」-「ホール中心~下端1mm」=1.6mm。

この座標は、X位置がドナーフットプリント(MSK12C02)の既存値(-2.25/0.75/2.25)とほぼ一致し、
4隅SHパッドのX位置概算(±3.65)もドナー値(±3.675)に近いことから、ドナーフットプリント自体が
機構的に近い部品だったことが裏付けられた。`SW_SPDT_Shouhan_MSS12C02LS.kicad_mod`を修正:
NPTHホール0.85→0.8(径・ドリルとも)、パッド1/2/3を0.6×1.3→0.8×1.6、Y座標-1.95→-1.8。
4隅SHパッド・F.Fab/F.CrtYd外形はドナー値のまま(概算との差0.03mm程度のため暫定妥当と判断)。

REQUIREMENTS.md R8を「ほぼ解決」に更新。現物サンプルでの最終確認・H/L向きシルク追加は未実施のため発注はまだしない。

---

## 追記3（同日、タイル再生成とDRC違反の修正）

footprint修正を反映して74x00/74x244/74x273を再生成したところ、make_switch_fp()が
スクリプト実行のたびにKiCad同梱のMSK12C02ライブラリから無条件でパッドを再構築しており、
手修正した.kicad_modの内容が再生成のたびに失われることが判明。make_switch_fp()自体に
同じパッド修正を焼き込んで解決。

その上で再生成すると、端子パッド拡大（0.6x1.3→0.8x1.6）に伴い各タイルでDRC違反54件
（全て[clearance]、SHOU HAN図面確認前の配線設計がクリアランスを消費していたため）が発生。
原因は2パターン: (1) SWC信号線が拡大した端子3(GND)パッドに0.058mmまで接近、
(2) +5V引き出し線が4隅SHパッドに0.1mmまで接近。SVGレンダリングとpcbnew経由の座標照会で
原因を特定し、CELL_TRACKSのSWC/+5V経路にジョグ点を追加して迂回。
3タイルともERC 0・DRC 0（未配線0・回路図等価性0）を確認、commit cab8060。

### 残課題（更新2）

- 4隅SHパッド・外形(F.Fab/F.CrtYd)はMSK12C02流用値のまま（現物サンプルでの最終確認は未実施）
- H/L向きシルクの追加
- クロック整形回路（タクトスイッチ+RC+1G14）の定数設計・部品選定・レイアウト
- `Rd` 220ΩとLED白のLCSC部品番号選定、bidirectional検出停止・CLRシルク注記・M2取付穴の
  generate_specimen_tile.py実装（D18-D23、まだ未着手）
- SHOU HANからの図面回答待ち（メーカー確認、進行中）
- 実見積もり（ユーザーがJLCONEで取得）
- 残り9型番のpinspec作成・タイル生成、混在パネルの面付け（Phase 2、別セッション）
---

## 追記4（同日、D17-D23 の実装とタイル再検証）

前回（追記3）時点で未着手だった D17（クロック整形回路）と D18-D23（負論理LED反転・双方向ピン検出停止・
CLR初期化シルク注記・M2取付穴・Rd 220Ω/白色LED部品選定）を `generate_specimen_tile.py` に実装した。

クロック整形回路（D17）は `attr: clock` を持つ接点にタクトスイッチ(SWT)+RC(RCK 10kΩ/CCK 1µF、時定数10ms)+
74LVC1G14シュミットトリガ(UG)のセルを追加する形で実装。部品はタクトスイッチ EVQP2R02M(C79161)、
RC抵抗10kΩ(C25804)、RCコンデンサ1µF(C106248)、UG=SN74LVC1G14DBVR(C7835)。

実装後に74x00/74x244/74x273を再生成し`kicad-cli sch erc`/`pcb drc`で検証したところ複数のDRC違反が発生し、
以下を順に特定・修正した:

- シルクフォント縮小(0.55mm)を試みたところ基板側のシルク文字高さ下限(0.8mm)に抵触。フォントサイズは元(1.2/0.4/0.8)に
  戻し、代わりに折り返し幅で調整
- `pad.GetSize()`はフットプリントのローカル(無回転)寸法を返し、±90°回転した部品(UG/RCK/CCK/RL/D等)は基板上の
  実効的な幅・高さが入れ替わることが判明。この見落としが複数のクリアランス誤判定の原因だった
- タクトスイッチ(SW_SPST_EVQP2_ShortPushTravel_H2.1mm)は電気的に同じピンに対し機構強度用の物理パッドが2箇所
  (Y座標が符号反転の関係)にあり、片方しか配線していなかったため`unconnected_items`が発生。両方に配線して解消
- 列端(j=9、74x273のCLKセル)ではP-net用の共通「レーン」配線が、クロックセル特有のD/R素子再配置(Y方向に押し下げ)と
  交差する構造的な衝突を新規に発見。レーン進入経路をD11の隙間へ迂回させて解消
- LA(R↔D間のLED電流)ネットはUG/R/Dの密集したパッド群でF.Cu上に迂回経路が取れなかったため、ビア2本でB.Cu層
  (その区間はGNDゾーンのみ)へ迂回するルートに変更して解消
- 裏面シルクのCLR初期化注記(D21)が4行目追加で他のシルクやJ1のGNDパッドと重なったため、行間・サイズと
  メッセージ文言を調整

最終的に3タイルとも **ERC 0件・DRC の error severity 0件** を確認(`grep -B2 '; error$'` で全レポート空を確認)。
以下はwarning severityのまま残し、ドキュメント化のみで許容とした(REQUIREMENTS §9 R9):

- 取付穴付近の説明文字とNPTHパッドのシルク重なり(74x00/74x244)
- 74x273の部品名ラベルとD11/R11周辺のシルク重なり
- UGのNCピンに関するネット名注記の不一致
- MTG1/MTG2のスキーマパリティ「extra footprint」通知

### 残課題（更新3）

- 4隅SHパッド・外形(F.Fab/F.CrtYd)はMSK12C02流用値のまま(現物サンプルでの最終確認は未実施)
- H/L向きシルクの追加
- クロック整形回路のRC時定数(10ms)が実機のタクトスイッチで十分かは現物実装後に確認
- 上記4件のwarning severityシルク重なりは許容済みだが、再配置の余地があれば改善余地あり
- 実見積もり(ユーザーがJLCONEで取得)
- 残り9型番のpinspec作成・タイル生成、混在パネルの面付け(Phase 2、別セッション)

## 追記5（2026-09-17、D25 入力スイッチのみ化と JLCPCB 発注データ作成）

ユーザーから、入力接点も出力接点（LEDのみ、D15）と対称にし、**入力接点をスイッチのみ**にしたい
という指示があった。入力状態はスイッチの物理位置で視認できるためLED表示は冗長という判断で、
`REQUIREMENTS.md` に **D25** として記録した。

`generate_specimen_tile.py` の `components()` 内、`Rk`（Rled）・`Dk`（LED）のDNP条件を
`kind == "dnp"` → `kind != "out"` に変更（2箇所）。`SWk`・`R(20+k)`(Rd) の条件は変更なし。
クロックセル（`attr: clock`）のLEDはD17の別回路のため対象外とし、タクトスイッチが位置で状態を
示せない点を根拠に維持した。ドキュメント同期として `REQUIREMENTS.md`（D25追加、D15行・§2.3・§5更新、
v0.7）、`_carrier/README.md`（§6.2更新、v0.6）、`AGENTS.md`・`.github/copilot-instructions.md`
（設計ルール文言を同一修正）を更新。加えて `pcb-demo/ORDER_CHECKLIST.md` に旧ルール
（「入力接点は全実装」「抵抗値が1kΩ/4.7kΩ」）を記載したままの箇所2件を発見し、D25・D16に
合わせて修正した（D24以前からの積み残し）。

74x00/74x244/74x273の3タイルを再生成し、`kicad-cli sch erc`/`pcb drc --schematic-parity`で
再検証。3タイルとも**ERC 0・DRC error 0**（severity=warningのみ、R9記載の既知パターンと一致）を確認。
さらに各タイルの`.kicad_sch`を直接パースし、`Dk`/`Rk`/`SWk`/`R(20+k)`のDNPフラグを型番ごとに
突合する検証スクリプトを実行——LED/RledはoutセルとD17クロックセル固有分のみ populated、SW/Rdは
ioセルのみ populated（変更なし）であることを確認した（74x273のLED populated数が8ではなく9件と
出たのはクロックセル固有のD11/R11分で、想定どおり）。

続けてKiKit（`panelize`、2×2グリッド、V-cut、hspace/vspace=0mm。R6で確立済みのコマンドを流用）で
3型番それぞれを独立パネル化し、`pcb-demo/_panel/{型番}/`に出力（各パネルに`Specimen.pretty`を
指す`fp-lib-table`を追加）。パネルDRC（`--severity-all`）はfootprint数がタイルの正確に4倍
（74x00: 77→308、74x244: 77→308、74x273: 79→316）であることをテキスト突合で確認し、
DRC違反件数もタイル単体の4倍（74x00: 1→4、74x244: 1→4、74x273: 5→20）で全件severity=warning・
type一致（silk_over_copper/silk_overlap、R9記載どおり）となり、パネル化による意図しない
幾何学的副作用がないことを確認した。

製造データは `kicad-happy:jlcpcb`・`kicad-happy:bom` スキルを参照して作成。BOM
（`kicad-cli sch export bom`、列名`Comment`/`Designator`/`Footprint`/`LCSC Part #`）と
CPL（`kicad-cli pcb export pos`、列`Designator`/`Mid X`/`Mid Y`/`Layer`/`Rotation`）は
**タイル1枚分**（パネルではない）から出力した。理由: KiKitがパネル化時に参照指定子をリネームせず
4コピーとも同一（例: `R1`が4箇所）のままだったため、JLCPCB公式ヘルプ記事（jlcpcb.com/help/article/
advice-for-bom-and-cpl-files-preparation）で案内されている2方式のうち、参照指定子の重複を許さない
「Complete File」方式は使えず、1ユニット分をアップロードして自動複製させる「Single Piece, please
help me repeat the data」方式を使う前提とした（ORDER.mdに明記）。BOM/CPLは`--exclude-dnp`のみで
手はんだ部品（ソケットU1・ピンヘッダJ1。生成スクリプトが元々LCSC番号なし=BOM/CPL除外に設定済み）
が自動的に除外されることを確認し、CPL行数とBOM記載designatorの集合が型番ごとに完全一致（25/37/41件）
することを自動検証した。Gerber+ドリルは**パネル**PCBから出力し`gerbers.zip`にまとめた。

BOM記載の主要部品についてLCSC在庫を確認（2026-09-17時点）: SHOU HAN MSS12C02LS(C3008585) 48,145、
Panasonic EVQP2R02M(C79161) 1,600、TI SN74LVC1G14DBVR(C7835) 342,890、いずれも十分な在庫。ただし
JLCPCB側のBasic/Extended区分はJLCPCBの部品検索ページがJS描画でこのセッションからは取得できず、
ORDER.mdに「JLCONEアップロード時に確認」と明記して持ち越した。

最後に`pcb-demo/ORDER_CHECKLIST.md`（修正版）を3パネル分コピーし`_panel/{型番}/ORDER.md`として
A〜Dを記入。E・Fはユーザー作業として未チェックのまま残した。特記事項として、SHOU HANスイッチ
（R8。4隅SHパッド・外形はMSK12C02流用のまま）について、**ユーザーが2026-09-17に「現物サンプルでの
事前確認は行わず、本パネルの実発注そのものを最終確認とする」と明示的に決定した**ことをA項目の
該当チェックボックスに記録した（意図的に未チェックのまま、理由を併記）。

### 残課題（更新4）

- SHOU HANスイッチ4隅SHパッド・外形（F.Fab/F.CrtYd）はMSK12C02流用値のまま。**2026-09-17の
  ユーザー決定により、現物サンプルでの事前確認はせず今回の実発注を最終確認とする方針**
- JLCPCBのBasic/Extended部品区分・最終在庫確認（JLCONEアップロード時にユーザーが確認）
- 実見積もり（ユーザーがHalvanのJLCONEで、`_panel/{型番}/`のGerber/BOM/CPLを使って取得。
  予算超過時はREQUIREMENTS §5の縮退案を適用）
- CPLの回転・Gerber全レイヤーの目視確認（JLCONEプレビュー時にユーザーが実施）
- 残り9型番のpinspec作成・タイル生成、混在パネルの面付け（Phase 2、別セッション）

## 追記6（2026-09-17、パネル発注データの不整合報告とパイロットの非パネル化・ディレクトリ再編）

ユーザーからJLCPCBのPCBA発注ビューア（Component Placementsタブ）のスクリーンショット2枚（74x00の
パネルGerber）とともに、「2x2個分に対しパーツが1個分しか入っていません」という報告があった。

原因を診断した結果、追記5で採用した「パネルGerber（4コピー）＋タイル1枚分のBOM/CPL」という構成が、
JLCPCBの「Single Piece, please help me repeat the data」アップロードモード（BOM/CPLの自動複製）
に依存する設計であり、この自動複製がユーザーの実際のJLCONEセッションでは機能せず、4回路中1回路に
しか部品配置が反映されなかったことが判明した。パネル化技術自体（KiKit、D9・R6）に問題はなく、
JLCPCB側のアップロード運用に起因する問題と判断した。比較のため非パネル（単タイル、50×50mm）版の
Gerberを試験生成し、パネル版（1型番=1パネル×5枚=最小ロットで20回路相当）と単タイル版
（1型番=1枚=1回路×5枚=5回路）のトレードオフを提示してユーザーに方針を確認した。

ユーザーは「1回路版で進める」ことを確定し、あわせて「ドキュメントだけでなくディレクトリ構成を含めて
再調整」を明示的に指示した。また、JLCONEの配置プレビュー（3D）で74x00_tileを確認した際の
スクリーンショット2枚を提示し、SHOU HANスイッチの配置と基板の照合を依頼した。

ディレクトリ再編: `pcb-demo/_panel/`を全面撤去した。実生成に手間がかかった`{型番}_bom.csv`・
`{型番}_cpl.csv`は`pcb-demo/_carrier/tiles/{型番}/`へ移動して保存し、パネル専用のKiCad成果物
（`{型番}_panel.kicad_pcb/pro/prl/dru`・`fp-lib-table`・gerbers.zip・gerbers/）はKiKitコマンド
1本（追記5に記載済み）で機械的に再生成可能なため削除した。3型番それぞれについて`{型番}_tile.kicad_pcb`
から直接Gerber・ドリル（`kicad-cli.exe pcb export gerbers`/`export drill`）を新規出力し、
`{型番}_tile_gerbers.zip`にまとめた。`REQUIREMENTS.md`にはこの決定を**D26**として記録した
（v0.7→v0.8。パイロット発注のパネル化見送り。パネル化技術自体はD9・R6のまま維持し、混在パネル対応
[Phase 2]とは別理由による見送りである点を明記）。`_carrier/README.md`のパネル関連の記載
（50×50mmタイルは100×100mmパネルに2×2で組める、D9）は技術的事実として現在も正しいため変更不要と判断した。

`ORDER.md`は新しい設置場所`pcb-demo/_carrier/tiles/{型番}/ORDER.md`で作り直した（旧
`_panel/{型番}/ORDER.md`は`_panel/`削除に伴い消滅）。パネル関連チェック項目（V-cut・パネル線の
直線性）を除去し、発注枚数を「3型番×5枚=15枚」に修正、Gerber/BOM/CPLがすべてタイル単位で
自己整合していることを明記した。作成直後、旧`_panel/{型番}/`基準（2階層）で書かれていた相対リンク
（REQUIREMENTS.md・README.md・work-in-progressへの`../`パス）が新しい`_carrier/tiles/{型番}/`
（3階層）に対して1段足りないことに気づき、3ファイル×3リンク=9リンク全てを修正し、実ファイルへの
解決を`[ -f ]`で検証した。

スイッチ配置・基板照合の確認: `SW_SPDT_Shouhan_MSS12C02LS.kicad_mod`原本を確認したところ、
フットプリントの`(model ...)`プロパティは現在も`SW_SPDT_Shouhan_MSK12C02.step`（ドナー部品の
3Dモデル）を指したままで、真のMSS12C02LSの3Dモデルではないことを再確認した。つまりJLCONEの配置
プレビュー（3D）に表示されているスイッチの立体形状はドナー部品の代替表示であり、現物のMSS12C02LSの
形状・寸法確認の代わりにはならない。これはR8の残課題（4隅SHパッド・外形がMSK12C02流用のまま）と
表裏一体の事実であり、ユーザーが2026-09-17に決定した「現物サンプルの事前確認は行わず、実発注
そのものを最終確認とする」という方針の対象・範囲に変更を生じさせるものではないと判断した。
CPLの回転値を74x00の`74x00_cpl.csv`で確認したところ、上側セル列のスイッチは-90°、下側セル列は
90°で、生成スクリプトの`YS`/`H-YS`（上下対称配置）ロジックに一致する180°相対回転であることを
確認した——スクリーンショットに見える上下対向配置は意図した対称レイアウトであり、配置ミスでは
ない。あわせてスクリーンショットのシルク印刷ピンラベル（上段VCC/4B/4A/4Y/3B/3A/3Y、下段
1A/1B/1Y/2A/2B/2Y/GND）を74x00の標準DIP-14データシートピン配置と突合し、一致すること
（ピン1が左下という標準DIPシルク表記どおり）を確認した。

### 残課題（更新5）

- SHOU HANスイッチ4隅SHパッド・外形（F.Fab/F.CrtYd）はMSK12C02流用値のまま。3Dモデル
  （`.step`）も同ドナー部品を指したままで、JLCONEプレビューの見た目では確認できない。
  2026-09-17のユーザー決定により、現物サンプルでの事前確認はせず今回の実発注を最終確認とする
  方針（変更なし）
- JLCPCBのBasic/Extended部品区分・最終在庫確認（JLCONEアップロード時にユーザーが確認）
- 実見積もり（ユーザーがHalvanのJLCONEで、`_carrier/tiles/{型番}/`のGerber/BOM/CPLから
  取得。予算超過時はREQUIREMENTS §5の縮退案を適用）
- CPLの回転は本セッションで74x00分を確認済み（180°相対、意図どおり）。Gerber全レイヤー・
  74x244/74x273の同様確認はJLCONEプレビュー時にユーザーが実施
- パネル化技術自体（D9・R6、KiKit）は健全と確認済みだが、D26によりパイロット発注では使用
  しない。異なる型番混在パネルの検証は元々Phase 2の課題のまま
- 残り9型番のpinspec作成・タイル生成（Phase 2、別セッション）

## 追記7（2026-09-17、JLCONEで実見積もり取得）

ユーザーがHalvanのJLCONEで74x00/74x244/74x273（`_carrier/tiles/{型番}/`のGerber/BOM/CPL、
各5枚）の見積もりを取得した。PCB代624円×3型番＋PCBA追加費（74x00 3,129円/74x244 3,221円/
74x273 5,210円）－同一Gerber割引312円＝**13,119円＋送料**（パイロット予算30,000円以内。
REQUIREMENTS §5 R1を解決として更新）。

74x273のPCBA追加費が他2型番より高いのは、`74x273_bom.csv`を確認したところ、クロックセル
（CLK/CLR）用の部品5点（RC11=10kΩ、CK11=1µF、SWT11=タクトスイッチ、UG11=シュミット
トリガ、D11=赤LED）が74x00/74x244には存在せず追加されているため（BOM行数は74x00/74x244が
5行、74x273が10行）と判断した。SHOU HAN MSS12C02LSスイッチ自体はD13で「Extended」区分と
記載済みだが3型番共通のため、この差の主因ではないと考えられる。JLCONE画面上のBasic/Extended
表示・在庫表示で個別確認できるが、金額自体はクロックセル部品の追加によるものとして自然な範囲。

REQUIREMENTS.mdのD4（予算）の根拠欄が旧「1パネルあたり」表記のまま残っていたため、D26に
合わせて「パイロット全体（3型番合計）で管理する」に修正した（記載漏れ、今回発見）。

### 残課題（更新6）

- SHOU HANスイッチ4隅SHパッド・外形・3Dモデルはドナー部品MSK12C02流用のまま。現物サンプル
  事前確認はせず今回の実発注を最終確認とする方針（変更なし）
- JLCPCBのBasic/Extended区分の個別確認・最終在庫確認はJLCONE画面でユーザーが実施可能
  （見積もり取得は完了。R1は解決）
- 発注実行そのもの（決済）はユーザー作業として残る
- Gerber全レイヤー・74x244/74x273の3Dプレビュー確認（74x00のみ本セッションで実施済み）
- 残り9型番のpinspec作成・タイル生成（Phase 2、別セッション）


