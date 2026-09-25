# 7400 IC PCB回路制作 その３ — 中断時点の引き継ぎ（2026-09-25）

Halvan との接続が切れたため未適用の作業が1件あります。接続が戻ったらこのファイルの
「適用する変更」を実行してください。**新しいタスクで再開する場合もこの内容だけで足ります。**

---

## 1. Halvan に保存済み・検証まで完了しているもの

`D:\VisualStudio Code Userfile\7400SeriesCollection` に反映済み。

| 内容 | 状態 |
|---|---|
| ツーリングホール Ø1.152mm NPTH ×2 を全タイルに追加（`ToolingHole_1.152mm`、座標 (2.5, 2.5) と (48.5, 48.5)） | 4タイルとも **DRC違反 0** |
| 和文シルクの行またぎ解消（`wrap_cjk()` を新設。ASCII英数字の連なりを割らない折り返し、幅9） | 完了 |
| 説明シルクが右固定穴に隠れる問題の解消（右M2を一旦削除し説明を右余白へ） | 完了 |
| `pcb-demo/_carrier/pinspec/{74x08,74x10,74x21}.json` 新規作成（TI SN74HC データシート目視、信頼度95%） | 完了 |
| `scripts/build_mixed_panel.py` 新規（KiKit APIで異種4型番の2×2混載パネル生成 + BOMマージ） | 完了 |
| commons_gates パネル一式（Gerber / BOM / CPL / ZIP） | BOM↔CPL **96件完全一致**、シルク脱落なし |

### 実物基板（JLCONEテスト発注 その１）の確認結果

- 74x00 / 74x244 / 74x273 の3枚とも、**スイッチの実装位置・個数・種類は設計どおり**（BOMのSWk番号と全列一致）
- 実物にある**小さな穴2個（左上・右下）は JLCPCB が PCBA 用に追加したツーリングホール**。
  発注した 74x00 のドリルデータ全79穴を精査し、2.2mm穴は (3.5, 25) / (46.5, 25) の
  左右中央2個のみで、左上付近に設計上の穴は無いことを確認済み。写真でも銅ランド・はんだの無い
  素通し穴（Ø約1.1〜1.3mm、隣のビア0.3mmより明確に大）で、JLCPCB標準 Ø1.152mm と一致。
  → これが上記ツーリングホールを自前で持つことにした理由（位置をJLCPCB任せにしない）。

---

## 2. 適用する変更（未適用・ユーザー決定済み）

**方針**: 額装用 M2 を左右対称ペアにする。そのために説明シルクを
「上段セルとソケットの間の横帯（y16.8〜20.2mm）」へ全幅・中央寄せで移す。

四隅への配置は不可（右上=接点11・右下=接点10・左下=接点1 のセル用フットプリントが
DNP分も含め実在しパッドが残るため）。空いている隅は左上のみで、回転対称ペアは成立しない。

### 適用手順

```bash
cd "$HOME/mnt/7400SeriesCollection"
python3 apply_d27c.py     # 下記スクリプトを保存して実行
```

```python
# apply_d27c.py
p = "scripts/generate_specimen_tile.py"
s = open(p, encoding="utf-8", newline="").read()

oldA = ('    # D27(c): 額装用 M2 固定穴。右中央(46.5,25)は説明シルクと干渉するため現状は左中央のみ\r\n'
        '    npth("MTG1", "MountingHole_2.2mm_M2", MTG_L_X, H / 2, MTG_KEEPOUT)\r\n')
newA = ('    # D27(c): 額装用 M2 固定穴。説明を横帯へ逃がしたので右中央を復活し左右対称ペアにする\r\n'
        '    npth("MTG1", "MountingHole_2.2mm_M2", MTG_L_X, H / 2, MTG_KEEPOUT)\r\n'
        '    npth("MTG2", "MountingHole_2.2mm_M2", MTG_R_X, H / 2, MTG_KEEPOUT)\r\n')
assert oldA in s, "A not found"
s = s.replace(oldA, newA, 1)

oldB = ('    # D27: MTG2 を省いた右余白(x38.6〜48)に、基板端をはみ出さない可読幅で左寄せ。\r\n'
        '    en, jp = textwrap.wrap(p["desc"], 14), wrap_cjk(p["desc_jp"], 9)  # 和文は NAND 等を割らない\r\n'
        '    for i, line in enumerate(en + jp):\r\n'
        '        text(line, 38.6, 23.0 + 1.2 * i + 0.4 * (i >= len(en)), 0.8, left=True)\r\n')
newB = ('    # D27: 説明は上段セルとソケットの間の横帯(y16.8〜20.2)へ全幅・中央寄せ。右中央を空けて\r\n'
        '    #      額装用 M2 を左右対称に置くため。帯はマスク下の配線の上なのでシルクを重ねてよい。\r\n'
        '    en, jp = textwrap.wrap(p["desc"], 62), wrap_cjk(p["desc_jp"], 34)\r\n'
        '    assert len(en) + len(jp) <= 3, (p["part"], "説明が横帯に収まらない", en, jp)\r\n'
        '    for i, line in enumerate(en + jp):\r\n'
        '        text(line, XC, 17.3 + 1.25 * i, 0.8)\r\n')
assert oldB in s, "B not found"
s = s.replace(oldB, newB, 1)

open(p, "w", encoding="utf-8", newline="").write(s)
print("patched: MTG2 restored, desc -> band")
```

### 適用後に流す検証（Windows / Desktop Commander）

```powershell
cd 'D:\VisualStudio Code Userfile\7400SeriesCollection'
& 'C:\Program Files\KiCad\10.0\bin\python.exe' scripts\generate_specimen_tile.py 74x00 74x08 74x10 74x21
$cli='C:\Program Files\KiCad\10.0\bin\kicad-cli.exe'
foreach($p in @('74x00','74x08','74x10','74x21')){
  & $cli sch erc --severity-all "pcb-demo\_carrier\tiles\$p\${p}_tile.kicad_sch"
  & $cli pcb drc --severity-all --schematic-parity "pcb-demo\_carrier\tiles\$p\${p}_tile.kicad_pcb"
}
& 'C:\Program Files\KiCad\10.0\bin\python.exe' scripts\build_mixed_panel.py --name commons_gates 74x00 74x08 74x10 74x21
```

その後、パネルの Gerber / CPL / BOM を再出力し、レンダリングで目視確認する。

> **注意**: タイルBOMの再出力では `--ref-range-delimiter ""` が必須（範囲圧縮 `R21-R25` が
> 出るとCPLと突合が合わなくなる）。PowerShell は空文字引数を落とすので `cmd /c` 経由で渡すこと。

---

## 3. 残タスク

- [ ] 上記パッチ適用 → 4タイル再生成 → ERC/DRC → パネル再構築 → レンダリング目視
- [ ] `REQUIREMENTS.md` に D27 を記録（説明シルクの横帯移動 / M2左右対称 / ツーリングホール自前化）
- [ ] `pcb-demo/_carrier/panels/commons_gates/ORDER.md` を作成（`ORDER_CHECKLIST.md` からコピー）
- [ ] `work-in-progress/2026-09-25_*.md` に作業ログ
- [ ] JLCONE で実見積もり（異種面付けは「Different Design」扱いで設計数ぶん追加料金。
      Economic組立が異種面付けパネルを受けるかは要確認）

commit / push はユーザー指示があるまで行わないこと。
