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
