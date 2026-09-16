#!/usr/bin/env python3
"""
generate_specimen_tile.py — Specimen Tile（共通キャリア）の回路図と基板を型番ごとに生成する。

仕様: pcb-demo/REQUIREMENTS.md / pcb-demo/_carrier/README.md
- 回路は全型番共通。型番で変わるのは「電源接点・未実装セル（DNP）・シルク」だけ。
- ピン数・VCC/GND・各ピンの方向は pcb-demo/_carrier/pinspec/{型番}.json（データシート目視で確認済み）から読む。
  無い型番は生成しない。角ピン決め打ちはしない。
- リファレンス: 接点 k ごとに SWk / R(20+k)=Rd 220 / Rk=Rled 4.7k / Dk、ソケット U1 のパッド k。
  クロック入力（pinspec attr=clock）は SWk/R(20+k) の代わりに SWTk（タクトスイッチ）/ RCk（10k プルアップ）/
  CKk（1uF）/ UGk（74LVC1G14 シュミットトリガ）を使うクロック整形回路になる（D17）。
- 接点の種類: 入力・双方向 = スイッチ + LED、出力（output / tri_state）= LED のみ（SWk・R(20+k) は DNP）、
  未使用・NC・open_collector = 全部 DNP（OC 出力は H 側へ引けないので LED を点けられない）。
  出力 LED は白、ただし active_low 属性を持つ出力は赤+プルアップ配線（点灯=アクティブ）にする（D18/D22）。

実行（KiCAD 同梱 Python。pcbnew が必要）:
  & 'C:\\Program Files\\KiCad\\10.0\\bin\\python.exe' scripts/generate_specimen_tile.py 74x00 74x244 74x273
出力:
  pcb-demo/_carrier/tiles/{型番}/{型番}_tile.kicad_{pro,sch,pcb} と fp-lib-table
  pcb-demo/_carrier/Specimen.pretty/（タイル専用フットプリント）
"""
import datetime
import json
import re
import sys
import textwrap
import uuid
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import kicad_sch_gen as sg  # noqa: E402  シンボル埋め込み・ピン座標の既存ヘルパ

KICAD_FP = Path(r"C:\Program Files\KiCad\10.0\share\kicad\footprints")
CARRIER = ROOT / "pcb-demo" / "_carrier"
SPEC_LIB = CARRIER / "Specimen.pretty"
SW_FP = "SW_SPDT_Shouhan_MSS12C02LS"
FP_TABLE = ('(fp_lib_table\n  (version 7)\n'
            '  (lib (name "Specimen")(type "KiCad")(uri "${KIPRJMOD}/../../Specimen.pretty")'
            '(options "")(descr "Specimen Tile footprints"))\n)\n')

# 種別 -> (シンボル, フットプリント, 値, LCSC 部品番号)。LCSC 番号なし = 手はんだ（BOM/CPL から除外）
PARTS = {
    "SW": ("Switch:SW_SPDT", f"Specimen:{SW_FP}", "MSS12C02LS-BB2.0", "C3008585"),
    "RD": ("Device:R", "Resistor_SMD:R_0603_1608Metric", "220", "C22962"),
    "RL": ("Device:R", "Resistor_SMD:R_0603_1608Metric", "4.7k", "C23162"),
    "D": ("Device:LED", "LED_SMD:LED_0603_1608Metric", "RED", "C2286"),
    "DW": ("Device:LED", "LED_SMD:LED_0603_1608Metric", "WHITE", "C2290"),
    "C": ("Device:C", "Capacitor_SMD:C_0603_1608Metric", "100nF", "C14663"),
    "U": ("Connector_Generic:Conn_02x10_Counter_Clockwise", "Package_DIP:DIP-20_W7.62mm_Socket", "DIP20_Socket_300mil", ""),
    "J": ("Connector_Generic:Conn_01x02", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "5V_IN", ""),
    # クロック整形回路（D17）
    "SWT": ("Switch:SW_Push", "Button_Switch_SMD:SW_SPST_EVQP2_ShortPushTravel_H2.1mm", "EVQP2R02M", "C79161"),
    "RCK": ("Device:R", "Resistor_SMD:R_0603_1608Metric", "10k", "C25804"),
    "CCK": ("Device:C", "Capacitor_SMD:C_0603_1608Metric", "1uF", "C106248"),
    "UG": ("74xGxx:74LVC1G14", "Package_TO_SOT_SMD:SOT-23-5", "SN74LVC1G14DBVR", "C7835"),
}
MPN = {  # LCSC 部品ページで確認（2026-09-16）
    "SW": ("SHOU HAN", "MSS12C02LS-BB2.0"),
    "RD": ("UNI-ROYAL", "0603WAF2200T5E"),
    "RL": ("UNI-ROYAL", "0603WAF4701T5E"),
    "D": ("Hubei KENTO", "KT-0603R"),
    "DW": ("Hubei KENTO", "KT-0603W"),
    "C": ("YAGEO", "CC0603KRX7R9BB104"),
    "SWT": ("Panasonic", "EVQP2R02M"),
    "RCK": ("UNI-ROYAL", "0603WAF1002T5E"),
    "CCK": ("YAGEO", "CC0603KRX7R7BB105"),
    "UG": ("Texas Instruments", "SN74LVC1G14DBVR"),
}

# 基板 [mm]。原点は左上、y は下向き
W = H = 50.0
XC = 25.0
PITCH = 4.6                           # I/O 列ピッチ（接点 1..10 は下側、20..11 は上側に左から並ぶ）
ROW = {"top": 21.19, "bot": 28.81}    # ソケットのパッド行
YS = 6.0                              # 上側スイッチ中心（下側は H - YS）
RAIL, BUS_Y = 1.0, 24.175             # +5V 外周レール / ソケット下を通る電源バス
SIG, PWR, GNDW = 0.25, 0.5, 0.3

# I/O セルの局所座標 (u, v)。v はスイッチ → ソケット方向。スイッチのパッド列は u = SW_PAD_U 側
# SHOU HAN純正図面(C3008585)確認済みのSW_SPDT_Shouhan_MSS12C02LSパッド1/2/3のローカルY座標（2026-09-16, REQUIREMENTS R8）
SW_PAD_U = -1.8
CLK_BYPASS_U = -3.0  # D17/D24: クロックセルの +5V バイパスレーン(SWT本体を迂回)の u 座標
CELL_POS = {"SW": (0, 0), "D": (-1.6, 6.1), "DW": (-1.6, 6.1), "RL": (-1.6, 9.2), "RD": (0, 9.2)}
CELL_TRACKS = [  # (ネット, 幅, 点列)
    # SHOU HAN純正図面確認後の端子パッド拡大(0.6x1.3->0.8x1.6)に伴い、SHパッド・位置決め穴とのクリアランスを
    # 確保するため経路を調整(2026-09-16, REQUIREMENTS R8)。+5VはGNDと同じ u=-2.1 側へ迂回してSHパッドを回避
    ("+5V", PWR, [(SW_PAD_U, -2.25), (-2.1, -2.25), (-2.1, -5.0)]),
    ("GND", GNDW, [(SW_PAD_U, 2.25), (-2.1, 3.3), (-2.1, 4.813), (-1.6, 5.313)]),
    ("SWC", SIG, [(SW_PAD_U, 0.75), (-0.82, 0.75), (-0.82, 0.65), (0.9, 0.65), (0.9, 2.6), (0, 2.82), (0, 8.375)]),  # 位置決め穴とパッド3(GND)を避けて本体右側を迂回
    ("LA", SIG, [(-1.6, 6.887), (-1.6, 8.375)]),
    ("P", SIG, [(-1.6, 10.025), (0, 10.025)]),
]
CELL_VIA = (-2.1, 3.3)  # GND
P_START = (0, 10.025)   # 通常セルの P ネット最終区間（ソケットへ）の起点。クロックセルは別値を使う

# active_low 出力セル用（D18）: D(LED)をプルアップ配線に反転。GND↔+5Vの行き先を入れ替え、
# 新規の +5V・LA 迂回トレースは u=-2.7/-3.3 に分けて SW_SPDT 本体(パッド u 範囲 -2.2〜-1.4)を避ける。
# SW/R(20+k) は DNP のまま(パッド自体は存在するが未実装)。エッジ列以外での隣接セル干渉は未検証(残課題)。
CELL_TRACKS_ACTIVE_LOW = [
    ("+5V", PWR, [(SW_PAD_U, -2.25), (-2.1, -2.25), (-2.1, -5.0)]),
    ("GND", GNDW, [(SW_PAD_U, 2.25), (-2.1, 3.3)]),
    ("SWC", SIG, [(SW_PAD_U, 0.75), (-0.82, 0.75), (-0.82, 0.65), (0.9, 0.65), (0.9, 2.6), (0, 2.82), (0, 8.375)]),
    ("+5V", PWR, [(SW_PAD_U, -2.25), (-2.7, -2.25), (-2.7, 6.887), (-1.6, 6.887)]),  # D pin2(A)へ+5Vを延長(反転配線)
    ("LA", SIG, [(-1.6, 5.313), (-3.3, 5.313), (-3.3, 8.375), (-1.6, 8.375)]),  # D pin1(旧GND位置)からR pin1へ、SW本体とその他の迂回を避ける
    ("P", SIG, [(-1.6, 10.025), (0, 10.025)]),
]


def mm(v):
    return pcbnew.FromMM(v)


def V(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def load_fp(lib_path, name):
    # pcbnew.FootprintLoad() はパス推定に失敗することがあり、PCB_IO を使い回すと戻り値の型が壊れるため毎回作る
    return pcbnew.PCB_IO_KICAD_SEXPR().FootprintLoad(str(lib_path), name)


def fields(kind):
    """BOM 用の追加フィールド（手はんだ部品は無し）"""
    if not PARTS[kind][3]:
        return []
    maker, mpn = MPN[kind]
    return [("LCSC Part #", PARTS[kind][3]), ("MPN", mpn), ("Manufacturer", maker)]


def uid(part, ref):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"specimen-tile/{part}/{ref}"))


def load_part(part):
    f = CARRIER / "pinspec" / f"{part}.json"
    if not f.exists():
        sys.exit(f"{part}: {f.relative_to(ROOT)} が無い（データシートで各ピンの方向を確認してから作る）")
    spec = json.loads(f.read_text(encoding="utf-8"))
    n = spec["package_pins"]
    pins = {int(k): v for k, v in spec["pins"].items()}
    if n not in (14, 16, 20) or sorted(pins) != list(range(1, n + 1)):
        sys.exit(f"{part}: pinspec が DIP-14/16/20 として不完全（{n} 本）")
    vcc = [i for i, v in pins.items() if v["dir"] == "power"]
    gnd = [i for i, v in pins.items() if v["dir"] == "ground"]
    if len(vcc) != 1 or len(gnd) != 1:
        sys.exit(f"{part}: power / ground を 1 本ずつに特定できない")
    bidir = [v["name"] for v in pins.values() if v["dir"] == "bidirectional"]
    if bidir:
        # D19: 双方向ピンの回路方式は Phase 4 まで未設計。誤った回路のまま生成しないよう停止する
        sys.exit(f"{part}: bidirectional ピン {bidir} を検出（D19 により生成を停止）。回路方式が未設計のため pinspec の確認だけでは生成できない")

    def contact(i):  # ピン 1 側へ端寄せして挿す（REQUIREMENTS §2.4）
        return i if i <= n // 2 else i + 20 - n

    ov = json.loads((ROOT / "overview" / "7400_series_ic_overview.json").read_text(encoding="utf-8"))
    o = next(x for x in ov if x["PartNumber"] == part)
    return dict(part=part, n=n, vcc=contact(vcc[0]), gnd=contact(gnd[0]),
                names={contact(i): v["name"] for i, v in pins.items()},
                dirs={contact(i): v["dir"] for i, v in pins.items()},
                attrs={contact(i): v.get("attr", []) for i, v in pins.items()},
                desc=o["Description"], desc_jp=o.get("Description_JP", ""), cat=o["Category"])


def cells(p):
    """電源以外の接点 k -> "io"（スイッチ+LED）/ "clk"（クロック整形回路+LED, D17）/
    "out"（LEDのみ）/ "dnp"（未実装）"""
    out = {}
    for k in range(1, 21):
        if k in (p["vcc"], p["gnd"]):
            continue
        d, a = p["dirs"].get(k), p["attrs"].get(k, [])
        if d == "input" and "clock" in a:
            out[k] = "clk"
        elif d in ("input", "bidirectional"):
            out[k] = "io"
        elif d in ("output", "tri_state"):
            out[k] = "out"
        else:
            out[k] = "dnp"
    return out


def clear_pins(p):
    """電源投入時の初期化に使う active_low ピン名（属性 clear。CLR 等。D21）"""
    return [p["names"][k] for k, a in p["attrs"].items() if "clear" in a]


def components(p):
    """[(ref, 種別, ピン番号→ネット, DNP)]"""
    u1 = {str(k): {p["vcc"]: "+5V", p["gnd"]: "GND"}.get(k, f"P{k}") for k in range(1, 21)}
    out = [("U1", "U", u1, False),
           ("J1", "J", {"1": "+5V", "2": "GND"}, False),
           ("C1", "C", {"1": "+5V", "2": "GND"}, False)]
    for k, kind in cells(p).items():
        if kind == "clk":
            # タクトスイッチ + RC ローパス + 74LVC1G14 シュミットトリガ（D17）。LED 表示(Rk/Dk)は通常配線のまま
            out += [(f"SWT{k}", "SWT", {"1": "GND", "2": f"CLKR{k}"}, False),
                    (f"RC{k}", "RCK", {"1": "+5V", "2": f"CLKR{k}"}, False),
                    (f"CK{k}", "CCK", {"1": f"CLKR{k}", "2": "GND"}, False),
                    (f"UG{k}", "UG", {"2": f"CLKR{k}", "3": "GND", "4": f"P{k}", "5": "+5V"}, False),
                    (f"R{k}", "RL", {"1": f"P{k}", "2": f"LA{k}"}, False),
                    (f"D{k}", "D", {"1": "GND", "2": f"LA{k}"}, False)]
            continue
        active_low = "active_low" in p["attrs"].get(k, [])
        d_kind, d_nets = "D", {"1": "GND", "2": f"LA{k}"}
        if kind == "out":
            if active_low:
                d_nets = {"1": f"LA{k}", "2": "+5V"}  # 点灯=アクティブ(P_k=L)になるようプルアップに反転（D18）
            else:
                d_kind = "DW"  # 通常出力は白（D22）
        out += [(f"SW{k}", "SW", {"1": "+5V", "2": f"SWC{k}", "3": "GND"}, kind != "io"),
                (f"R{20 + k}", "RD", {"1": f"SWC{k}", "2": f"P{k}"}, kind != "io"),
                (f"R{k}", "RL", {"1": f"LA{k}", "2": f"P{k}"}, kind == "dnp"),
                (f"D{k}", d_kind, d_nets, kind == "dnp")]
    return out


def frame(k):
    """接点 k の I/O 列。g(u, v) が局所座標 → 基板座標"""
    top = k > 10
    j = 20 - k if top else k - 1
    xc = XC + (j - 4.5) * PITCH
    s, t, y0 = (-1, 1, YS) if top else (1, -1, H - YS)
    lane = 19.0 - 0.5 * min(j, 9 - j)  # 外側の列ほどソケット寄りのレーン（交差しない順）
    return dict(xc=xc, xpad=XC + (j - 4.5) * 2.54, ypad=ROW["top" if top else "bot"],
                rot=-90 if top else 90, lane=lane if top else H - lane,
                g=lambda u, v: (xc + s * u, y0 + t * v))


# ---------------------------------------------------------------- 回路図

def sym_text(lib_id, x, y, ref, value, fp, u, sheet, project, pins, extra=(), dnp=False, in_bom=True):
    c, yn = sg._coord, (lambda b: "yes" if b else "no")
    props = [("Reference", ref, 0, -3.81), ("Value", value, 0, 3.81), ("Footprint", fp, 1, 0), ("Datasheet", "", 1, 0)]
    props += [(k, v, 1, 0) for k, v in extra]
    s = [f'  (symbol (lib_id "{lib_id}") (at {c(x)} {c(y)} 0) (unit 1)',
         f'    (exclude_from_sim no) (in_bom {yn(in_bom)}) (on_board yes) (dnp {yn(dnp)})',
         f'    (uuid "{u}")']
    s += [f'    (property "{k}" "{v}" (at {c(x + 2.54)} {c(y + dy)} 0) (effects (font (size 1.27 1.27)){" (hide yes)" if h else ""}))'
          for k, v, h, dy in props]
    s += [f'    (pin "{n}" (uuid "{uuid.uuid5(uuid.UUID(u), n)}"))' for n in pins]
    s += [f'    (instances (project "{project}" (path "/{sheet}" (reference "{ref}") (unit 1))))', "  )"]
    return "\n".join(s) + "\n"


def write_sch(p, comps, path):
    G = 1.27
    lib_ids = sorted({v[0] for v in PARTS.values()} | {"power:+5V", "power:GND", "power:PWR_FLAG"})
    embeds, pins = {}, {}
    for lib_id in lib_ids:
        lib, name = lib_id.split(":")
        e = sg.extract_sym_for_embed(lib, name)
        assert e and f'(symbol "{lib_id}"' in e, f"シンボルが見つからない/派生シンボル: {lib_id}"
        embeds[lib_id] = e
        pins[lib_id] = {q["num"]: (q["x"], q["y"]) for ps in sg.parse_pins_by_unit(e, name).values() for q in ps}

    part, sheet, project = p["part"], uid(p["part"], "sheet"), path.stem
    body, pwr = [], [0]

    def power(net, x, y, flag=False):
        pwr[0] += 1
        lib_id = "power:PWR_FLAG" if flag else f"power:{net}"
        ref = f"#FLG{pwr[0]:02d}" if flag else f"#PWR{pwr[0]:02d}"
        body.append(sym_text(lib_id, x, y, ref, "PWR_FLAG" if flag else net, "", str(uuid.uuid4()), sheet, project, ["1"]))

    def place(ref, kind, x, y, nets, dnp):
        lib_id, fp, value, lcsc = PARTS[kind]
        body.append(sym_text(lib_id, x, y, ref, value, fp, uid(part, ref), sheet, project, list(pins[lib_id]),
                             extra=fields(kind), dnp=dnp, in_bom=bool(lcsc)))
        for num, (px, py) in pins[lib_id].items():
            if num not in nets:
                continue  # 未接続ピン（例: 74LVC1G14 の NC）にはネットラベルを付けない
            ax, ay = sg.pin_abs(x, y, px, py)
            if nets[num] in ("+5V", "GND"):
                power(nets[num], ax, ay)
            else:
                body.append(sg._net_label(nets[num], ax, ay))
        return {num: sg.pin_abs(x, y, px, py) for num, (px, py) in pins[lib_id].items()}

    fixed = {"U1": (48, 118), "J1": (32, 176), "C1": (56, 176)}
    offs = {"SW": 0, "RD": 12, "RL": 20, "D": 30, "DW": 30}
    clk_offs = {"SWT": 0, "RCK": 10, "CCK": 18, "UG": 26}  # 専用行（offs は 48 幅の列に収まらないため別枠、D24）
    clk_idx = {}
    for ref, kind, nets, dnp in comps:
        if ref in fixed:
            gx, gy = fixed[ref]
        elif kind in clk_offs:
            k = int(re.sub(r"\D", "", ref))
            clk_idx.setdefault(k, len(clk_idx))
            gx, gy = 88 + clk_idx[k] * 40 + clk_offs[kind], 220
        else:
            k = int(re.sub(r"\D", "", ref)) - (20 if kind == "RD" else 0)
            gx, gy = 88 + (k - 1) % 5 * 48 + offs[kind], 32 + (k - 1) // 5 * 48
        at = place(ref, kind, gx * G, gy * G, nets, dnp)
        if ref == "J1":  # 外部給電なので PWR_FLAG を立てる
            power("+5V", *at["1"], flag=True)
            power("GND", *at["2"], flag=True)

    note = (f"{part} Specimen Tile v0.1 ({p['desc']})\\n"
            f"DIP-{p['n']}: VCC = contact {p['vcc']}, GND = contact {p['gnd']}\\n"
            "Cell k: SWk selects +5V/GND -> R(20+k) 220R -> contact k -> Rk 4.7k -> Dk -> GND\\n"
            "Output contacts (per pinspec): SWk and R(20+k) are DNP, LED only (white; active_low = red + inverted)\\n"
            "Clock contacts (attr=clock): tact SWTk + RCk/CKk RC + UGk 74LVC1G14 Schmitt trigger -> contact k\\n"
            "Spec: pcb-demo/_carrier/README.md")
    body.append(f'  (text "{note}" (exclude_from_sim no) (at 25.4 20.32 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "{uuid.uuid4()}"))\n')

    esc = lambda s: s.replace('"', '\\"')  # noqa: E731
    head = (f'(kicad_sch\n  (version 20231120)\n  (generator "generate_specimen_tile")\n  (generator_version "1.0")\n'
            f'  (uuid "{sheet}")\n  (paper "A3")\n'
            f'  (title_block (title "{part} Specimen Tile") (date "{datetime.date.today()}") (rev "0.1")'
            f' (company "7400 Series Collection") (comment 1 "{esc(p["desc"])}") (comment 2 "{esc(p["desc_jp"])}")'
            f' (comment 3 "Category: {p["cat"]}") (comment 4 "pcb-demo/_carrier/README.md"))\n')
    libs = "  (lib_symbols\n" + "".join(textwrap.indent(embeds[i], "    ") + "\n" for i in lib_ids) + "  )\n"
    tail = '  (sheet_instances (path "/" (page "1")))\n)\n'
    path.write_text(head + libs + "".join(body) + tail, encoding="utf-8")


# ---------------------------------------------------------------- 基板

def make_switch_fp():
    """MSK12C02（横レバー）を土台に、SHOU HAN純正図面(C3008585)で確認済みの端子パッド・穴寸法に置き換える。
    4隅SHパッド・外形/courtyardは未照合のためMSK12C02のランドをそのまま流用（2026-09-16、REQUIREMENTS R8）。"""
    # ponytail: SHパッド・外形はMSK12C02と同一と仮定。現物サンプルで最終照合するまで発注不可（ORDER_CHECKLIST A）
    # pcbnew で図形を消して保存すると SWIG の型情報が壊れ、以降の FootprintLoad() が失敗するのでテキストで加工する
    old = "SW_SPDT_Shouhan_MSK12C02"
    src = (KICAD_FP / "Button_Switch_SMD.pretty" / f"{old}.kicad_mod").read_text(encoding="utf-8")
    out, i = [], 0
    while (m := re.search(r"\((fp_line|fp_rect|fp_poly|fp_arc|fp_circle|fp_text)\s", src[i:])):
        j = i + m.start()
        depth, k = 0, j
        for k in range(j, len(src)):
            depth += {"(": 1, ")": -1}.get(src[k], 0)
            if depth == 0:
                break
        out.append(src[i:j].rstrip(" \t"))
        i = k + 1
    body = "".join(out) + src[i:]
    body = re.sub(r'\(descr "[^"]*"\)', '(descr "SPDT SMD slide switch, top actuated, SHOU HAN MSS12C02LS (LCSC C3008585). '
                  'Switch-terminal pads (1/2/3) and NPTH holes re-derived from SHOU HAN drawing C3008585 and user-confirmed 2026-09-16. '
                  'SH corner pads and body outline still inherited from SW_SPDT_Shouhan_MSK12C02 (cross-checked against the drawing but not independently re-derived)")', body)
    body = body.replace(f'"{old}"', f'"{SW_FP}"')
    # SHOU HAN純正図面(C3008585)で確認した端子パッド・NPTH穴の寸法に置き換える（2026-09-16, REQUIREMENTS R8）
    for at_old, at_new in [
        ("(at -1.5 0)\n\t\t(size 0.85 0.85)\n\t\t(drill 0.85)", "(at -1.5 0)\n\t\t(size 0.8 0.8)\n\t\t(drill 0.8)"),
        ("(at 1.5 0)\n\t\t(size 0.85 0.85)\n\t\t(drill 0.85)", "(at 1.5 0)\n\t\t(size 0.8 0.8)\n\t\t(drill 0.8)"),
        ("(at -2.25 -1.95)\n\t\t(size 0.6 1.3)", "(at -2.25 -1.8)\n\t\t(size 0.8 1.6)"),
        ("(at 0.75 -1.95)\n\t\t(size 0.6 1.3)", "(at 0.75 -1.8)\n\t\t(size 0.8 1.6)"),
        ("(at 2.25 -1.95)\n\t\t(size 0.6 1.3)", "(at 2.25 -1.8)\n\t\t(size 0.8 1.6)"),
    ]:
        assert at_old in body, f"switch fp pad pattern not found: {at_old!r}"
        body = body.replace(at_old, at_new)
    rects = "".join(
        f'\t(fp_rect (start {x0} {y0}) (end {x1} {y1}) (stroke (width {w}) (type solid)) (fill no)'
        f' (layer "{layer}") (uuid "{uuid.uuid5(uuid.NAMESPACE_URL, SW_FP + layer)}"))\n'
        for layer, (x0, y0, x1, y1), w in [("F.CrtYd", (-4.5, -2.85, 4.5, 1.7), 0.05),
                                            ("F.Fab", (-3.35, -1.4, 3.35, 1.4), 0.1)])
    body = re.sub(r"\n+\)\s*$", "\n" + rects + ")\n", body)
    SPEC_LIB.mkdir(parents=True, exist_ok=True)
    (SPEC_LIB / f"{SW_FP}.kicad_mod").write_text(body, encoding="utf-8")


def write_pcb(p, comps, path):
    board = pcbnew.NewBoard(str(path))
    nets = {}

    def net(name):
        name = name if name in ("+5V", "GND") else f"/{name}"  # 回路図のローカルラベルはシート名付き
        if name not in nets:
            nets[name] = pcbnew.NETINFO_ITEM(board, name)
            board.Add(nets[name])
        return nets[name]

    def track(pts, name, w, layer=pcbnew.F_Cu):
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(V(*a))
            t.SetEnd(V(*b))
            t.SetWidth(mm(w))
            t.SetLayer(layer)
            t.SetNet(net(name))
            board.Add(t)

    def via(x, y, name):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(V(x, y))
        v.SetWidth(mm(0.6))
        v.SetDrill(mm(0.3))
        v.SetNet(net(name))
        board.Add(v)

    def text(s, x, y, size, left=False, layer=pcbnew.F_SilkS):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(s)
        t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(0.15))
        if left:
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        if layer == pcbnew.B_SilkS:
            t.SetMirrored(True)
        t.SetPosition(V(x, y))
        board.Add(t)

    def pad_xy(fp, num):
        pos = next(q for q in fp.Pads() if q.GetNumber() == num).GetPosition()
        return round(pcbnew.ToMM(pos.x), 3), round(pcbnew.ToMM(pos.y), 3)

    def expect(fp, num, want):
        got = pad_xy(fp, num)
        assert abs(got[0] - want[0]) < 0.01 and abs(got[1] - want[1]) < 0.01, (fp.GetReference(), num, got, want)

    fps = {}
    for ref, kind, pad_nets, dnp in comps:
        lib_id, fpid, value, lcsc = PARTS[kind]
        lib, name = fpid.split(":")
        fp = load_fp(str(SPEC_LIB if lib == "Specimen" else KICAD_FP / f"{lib}.pretty"), name)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.Reference().SetVisible(False)
        for key, val in fields(kind):
            fp.SetField(key, val)
            fp.GetField(key).SetVisible(False)
        if not lcsc:
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        fp.SetDNP(dnp)
        fp.SetPath(pcbnew.KIID_PATH(f"/{uid(p['part'], ref)}"))
        fp.SetSheetname("/")
        fp.SetSheetfile(path.with_suffix(".kicad_sch").name)
        board.Add(fp)
        for pad in fp.Pads():
            if pad.GetNumber() in pad_nets:
                pad.SetNet(net(pad_nets[pad.GetNumber()]))
        fps[ref] = (fp, kind)

    # ソケット: ピン 1 を左下、1..10 を下段、11..20 を上段に
    u1 = fps["U1"][0]
    u1.SetOrientationDegrees(90)
    u1.SetPosition(V(XC - 11.43, ROW["bot"]))
    expect(u1, "11", (XC + 11.43, ROW["top"]))

    cell_kind = cells(p)
    for k, kind in cell_kind.items():
        f = frame(k)
        g = f["g"]
        if kind == "clk":
            place_clock_cell(k, f, fps, track, via)
            continue
        for ref in (f"SW{k}", f"R{20 + k}", f"R{k}", f"D{k}"):
            fp, comp_kind = fps[ref]
            fp.SetOrientationDegrees(f["rot"])
            fp.SetPosition(V(*g(*CELL_POS[comp_kind])))
        expect(fps[f"SW{k}"][0], "1", g(SW_PAD_U, -2.25))
        expect(fps[f"D{k}"][0], "1", g(-1.6, 6.1 - 0.787))
        active_low = kind == "out" and "active_low" in p["attrs"].get(k, [])
        name = {"+5V": "+5V", "GND": "GND", "SWC": f"SWC{k}", "LA": f"LA{k}", "P": f"P{k}"}
        for tkind, w, pts in (CELL_TRACKS_ACTIVE_LOW if active_low else CELL_TRACKS):
            track([g(*q) for q in pts], name[tkind], w)
        via(*g(*CELL_VIA), "GND")
        track([g(*P_START), (f["xc"], f["lane"]), (f["xpad"], f["lane"]), (f["xpad"], f["ypad"])], f"P{k}", SIG)

    # +5V: 外周レール（上・下・左）と、ソケット下を通って VCC 接点へ行くバス
    top = max([frame(k)["g"](SW_PAD_U, 0)[0] for k in cell_kind if k > 10] +
              [frame(k)["g"](CLK_BYPASS_U, 0)[0] for k in cell_kind if k > 10 and cell_kind[k] == "clk"])  # クロックセルはバイパスレーンがレールに乗るように(D24)
    bot = max([frame(k)["g"](SW_PAD_U, 0)[0] for k in cell_kind if k <= 10] +
              [frame(k)["g"](CLK_BYPASS_U, 0)[0] for k in cell_kind if k <= 10 and cell_kind[k] == "clk"])
    track([(top, RAIL), (RAIL, RAIL), (RAIL, H - RAIL), (bot, H - RAIL)], "+5V", PWR)
    j1, c1 = fps["J1"][0], fps["C1"][0]
    j1.SetPosition(V(J1_X, BUS_Y))  # D23: 左取付穴の実測コートヤードとのクリアランスのため右へ移動
    c1.SetOrientationDegrees(-90)
    c1.SetPosition(V(11.2, 25.0))  # D23: J1 が右へ移動した分、干渉を避けてさらに右へ
    c1p1, c1p2 = pad_xy(c1, "1"), pad_xy(c1, "2")
    assert c1p1[1] < c1p2[1], "C1 の向きが想定と逆"
    vx, vy = pad_xy(u1, str(p["vcc"]))
    # +5V バス: 左取付穴(MTG1, D23)の keepout を避けて迂回してからソケット VCC / C1 へ
    track([(RAIL, BUS_Y), (MTG_L_X - MTG_KEEPOUT, BUS_Y), (MTG_L_X - MTG_KEEPOUT, BUS_Y - 1.8),
           (MTG_L_X + MTG_KEEPOUT, BUS_Y - 1.8), (MTG_L_X + MTG_KEEPOUT, BUS_Y), (vx, BUS_Y), (vx, vy)], "+5V", PWR)
    track([(c1p1[0], BUS_Y), c1p1], "+5V", PWR)
    track([c1p2, (c1p2[0], c1p2[1] + 1.0)], "GND", GNDW)
    via(c1p2[0], c1p2[1] + 1.0, "GND")

    # 外形と裏面 GND ベタ
    edge = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECT)
    edge.SetStart(V(0, 0))
    edge.SetEnd(V(W, H))
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetWidth(mm(0.1))
    board.Add(edge)
    zone = pcbnew.ZONE(board)
    zone.SetLayer(pcbnew.B_Cu)
    zone.SetNet(net("GND"))
    zone.SetMinThickness(mm(0.25))
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in [(0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)]:
        outline.Append(mm(x), mm(y))
    board.Add(zone)

    # D23: 左右中央の M2（2.2mm 非メッキ）取付穴。参照は重複エラー回避のため MTG1/MTG2（非表示）
    for i, mx in enumerate((MTG_L_X, MTG_R_X), 1):
        hole = load_fp(str(KICAD_FP / "MountingHole.pretty"), "MountingHole_2.2mm_M2")
        hole.SetReference(f"MTG{i}")
        hole.Reference().SetVisible(False)
        hole.SetAttributes(hole.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        hole.SetPosition(V(mx, H / 2))
        board.Add(hole)
        # 取付穴まわりは GND ベタを打ち抜かないよう B.Cu にキープアウト（hole_clearance 対策）
        ko = pcbnew.ZONE(board)
        ko.SetIsRuleArea(True)
        ko.SetLayer(pcbnew.B_Cu)
        ko.SetDoNotAllowZoneFills(True)
        ko.SetDoNotAllowVias(True)
        ko.SetDoNotAllowPads(False)       # 取付穴自身の NPTH パッドは禁止しない(D24)
        ko.SetDoNotAllowTracks(False)
        ko.SetDoNotAllowFootprints(False)
        ko_outline = ko.Outline()
        ko_outline.NewOutline()
        for kx, ky in [(mx - MTG_KEEPOUT, H / 2 - MTG_KEEPOUT), (mx + MTG_KEEPOUT, H / 2 - MTG_KEEPOUT),
                       (mx + MTG_KEEPOUT, H / 2 + MTG_KEEPOUT), (mx - MTG_KEEPOUT, H / 2 + MTG_KEEPOUT)]:
            ko_outline.Append(mm(kx), mm(ky))
        board.Add(ko)

    # シルク: 各列のピン名、型番・機能名、給電表示。裏面にカテゴリ・版・ライセンス
    for k in range(1, 21):
        label = {p["vcc"]: "VCC", p["gnd"]: "GND"}.get(k, p["names"].get(k, ""))
        if label:
            text(label, frame(k)["xc"], RAIL if k > 10 else H - RAIL, 0.8)
    text(p["part"], 43.8, 21.2, 1.6)
    en, jp = textwrap.wrap(p["desc"], 16), textwrap.wrap(p["desc_jp"], 10)  # D24: 幅は復元(行数超過=Y方向対策)
    for i, line in enumerate(en + jp):  # ソケット右の余白（x 38.6〜49.5）。和文は字面が高いので 0.4 空ける
        text(line, 38.6, 23.0 + 1.2 * i + 0.4 * (i >= len(en)), 0.8, left=True)
    text("+5V", 5.5, 22.0, 0.8)
    text("GND", 5.5, 28.9, 0.8)
    back = [f"7400 Specimen Tile v0.1  {p['part']}", p["cat"], "MIT License"]
    clr = clear_pins(p)
    if clr:
        back.append(f"Power-on: clear via {'/'.join(clr)}")  # D24: 長すぎて J1 に達するため短縮(詳細は D21)
    for i, s in enumerate(back):
        text(s, XC, 22.9 + 1.4 * i, 0.9, layer=pcbnew.B_SilkS)  # 裏面はソケットのパッド行の間に(D24: 4行時も収まる寸法に調整)

    tb = board.GetTitleBlock()
    tb.SetTitle(f"{p['part']} Specimen Tile")
    tb.SetRevision("0.1")
    tb.SetDate(str(datetime.date.today()))
    tb.SetCompany("7400 Series Collection")
    tb.SetComment(0, p["desc"])
    tb.SetComment(1, p["desc_jp"])

    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(path), board)


# D23: 取付穴中心 x（左右中央）と J1 の新しい x（左取付穴を避ける）
MTG_L_X, MTG_R_X, MTG_KEEPOUT = 3.5, 46.5, 1.55
J1_X = 8.3  # D23: 実測コートヤードで左取付穴と0.5mm以上の余裕を確保


def place_clock_cell(k, f, fps, track, via):
    """クロック整形回路セル（D17）: タクトスイッチ SWTk + 10k/1uF の RC ローパス(RCk/CKk) +
    74LVC1G14 シュミットトリガ(UGk) -> 接点 k。LED 表示(Rk/Dk)は通常セルと同じ配線のまま接点 k を表示する。
    CCK/D は 180 度余分に回転させ、パッド1/2の v 位置を入れ替えて隣とのスタッキングを線形にしている。
    6 部品を v 方向に単純に積むと深さがソケット手前(v≈15.2)を超えるため、RCK/CCK・RL/D はそれぞれ同じ v で
    u をずらして横並びにしている（通常セルの Rd/Rled と同じ手法）。SWT・CCK は隣接する通常セル（j-1 列、
    本例では k+1=SW12 側）のスイッチと実測コートヤードが干渉するため、u を実測値ベースでシフトして回避した。
    電源(+5V)は SWT 本体を迂回する専用レーン u=-3.0 を通す。座標は .temp/diag_crtyd.py（実測コートヤード）・
    .temp/diag_cell11.py（実測配置後のコートヤード）で検証済み。ここでは接点 k が I/O 列の端（74x273 の
    CLK、j=9）で片側にしか隣接セルが無い前提。両側に隣接セルがある内側の列（Phase 2）では反対側の余白も
    別途検証が必要（残課題）。
    """
    g = f["g"]
    pos = {"SWT": (-0.65, 0), "RCK": (-1.6, 5.35), "CCK": (0.6, 5.35),
           "UG": (0, 9.2), "RL": (-1.6, 13.05), "D": (1.6, 13.05)}
    refs = {"SWT": f"SWT{k}", "RCK": f"RC{k}", "CCK": f"CK{k}", "UG": f"UG{k}", "RL": f"R{k}", "D": f"D{k}"}
    for part, ref in refs.items():
        fp, _ = fps[ref]
        fp.SetOrientationDegrees(f["rot"] + (180 if part in ("CCK", "D") else 0))
        fp.SetPosition(V(*g(*pos[part])))

    def pad(part, num):
        fp = fps[refs[part]][0]
        pp = next(q for q in fp.Pads() if q.GetNumber() == num).GetPosition()
        return round(pcbnew.ToMM(pp.x), 3), round(pcbnew.ToMM(pp.y), 3)

    # 実パッド位置を自己検査（180度反転させた CCK/D は符号が変わる点に注意）
    def expect(part, num, want):
        got = pad(part, num)
        assert abs(got[0] - want[0]) < 0.01 and abs(got[1] - want[1]) < 0.01, (refs[part], num, got, want)

    expect("SWT", "1", g(-1.5, -2.575))
    expect("SWT", "2", g(0.2, -2.575))
    expect("RCK", "1", g(-1.6, 4.525))
    expect("RCK", "2", g(-1.6, 6.175))
    expect("CCK", "1", g(0.6, 6.125))   # 180度回転で pin1/2 の v が通常(∓0.775)と逆転
    expect("CCK", "2", g(0.6, 4.575))
    expect("UG", "2", g(0, 8.063))
    expect("UG", "3", g(0.95, 8.063))
    expect("UG", "4", g(0.95, 10.337))
    expect("UG", "5", g(-0.95, 10.337))
    expect("RL", "1", g(-1.6, 12.225))
    expect("RL", "2", g(-1.6, 13.875))
    expect("D", "1", g(1.6, 13.837))    # 180度回転で pin1/2 の v が通常(∓0.787)と逆転
    expect("D", "2", g(1.6, 12.263))

    swt1, swt2 = pad("SWT", "1"), pad("SWT", "2")
    swt1b, swt2b = g(-1.5, 2.575), g(0.2, 2.575)  # D24: SWT は同ピン番号のパッドが v 符号違いで2枚実在
    rc1, rc2 = pad("RCK", "1"), pad("RCK", "2")
    ck1, ck2 = pad("CCK", "1"), pad("CCK", "2")
    ug2, ug3, ug4, ug5 = pad("UG", "2"), pad("UG", "3"), pad("UG", "4"), pad("UG", "5")
    rl1, rl2 = pad("RL", "1"), pad("RL", "2")
    d1, d2 = pad("D", "1"), pad("D", "2")

    # SWT の2個目の物理パッドにも到達(D24)
    track([swt1, swt1b], "GND", GNDW)
    track([swt2, swt2b], f"CLKR{k}", SIG)

    # CLKR: タクトスイッチ2/RC分圧点/シュミット入力を RCK.pin2 に集約。swt2 は CCK/RCK 間の隙間(u=-0.5)を
    # 経由し RCK.pin1 をかすめないようにする。ug2 は ck1 経由(UGのNC=pin1回避、D24)
    x_gap = g(-0.5, 0)[0]
    track([swt2, (x_gap, swt2[1]), (x_gap, rc2[1]), rc2], f"CLKR{k}", SIG)
    track([ck1, rc2], f"CLKR{k}", SIG)
    track([ug2, ck1], f"CLKR{k}", SIG)

    # +5V: 外周レール起点(g(0,-5.0)、通常セルと同じY)から SWT を避け u=CLK_BYPASS_U 経由で RCK.pin1 -> UG.pin5
    # 旧 rail_pt(通常セルの SWk パッド流用)はレール本線まで届かず未結線だったため撤回(D24)
    x_by = g(CLK_BYPASS_U, 0)[0]
    top_y = g(0, -5.0)[1]
    track([(x_by, top_y), (x_by, rc1[1]), rc1], "+5V", PWR)
    track([rc1, (x_by, rc1[1]), (x_by, ug5[1]), ug5], "+5V", PWR)

    # GND: 各所に個別 via（裏面 GND ベタへ）
    for src, dx, dy in ((swt1, 0, 0.6), (ck2, 0.4, 0), (ug3, 0, 0.55), (d1, 0, 0.55)):
        stub = (round(src[0] + dx, 3), round(src[1] + dy, 3))
        track([src, stub], "GND", GNDW)
        via(*stub, "GND")

    # P: UG出力 -> RL -> ソケット。UG.pin4/5 は同じ盤面Yを共有するため y_mid で迂回し +5V(ug5)配線との
    # tracks_crossing を回避。UG は回転で実効の幅・高さが入れ替わるため pin5 の実効下端(~17.0)を避けて
    # 17.4 とする(D24)。レーン合流部も同じ Y で D11 を迂回してから socket レーンへ戻す
    y_mid = g(0, 11.4)[1]
    lane_x = d1[0] - 2.0  # D24: D11 パッド左端(実効半幅込み)から余裕を見て迂回
    track([ug4, (ug4[0], y_mid), (rl1[0], y_mid), rl1], f"P{k}", SIG)
    track([rl1, (f["xc"], f["lane"]), (f["xc"], y_mid), (lane_x, y_mid),
           (lane_x, f["lane"]), (f["xpad"], f["lane"]), (f["xpad"], f["ypad"])], f"P{k}", SIG)

    # LA: RL -> D(LED)。F.Cu は UG11/R11/D11 のパッドが密集し迂回余地が無いため、短いビア2本で
    # 裏面(B.Cu、GND ベタとは別ネットにつき自動でクリアランス確保)を経由する(D24)
    la1 = (round(rl2[0] + 1.1, 3), rl2[1])
    la2 = (round(d1[0] - 1.1, 3), d2[1])
    track([rl2, la1], f"LA{k}", SIG)
    via(*la1, f"LA{k}")
    track([la1, la2], f"LA{k}", SIG, layer=pcbnew.B_Cu)
    via(*la2, f"LA{k}")
    track([la2, d2], f"LA{k}", SIG)


def write_pro(path):
    src = path if path.exists() else ROOT / "pcb-demo" / "_templates" / "template.kicad_pro"
    pro = json.loads(src.read_text(encoding="utf-8"))
    pro.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {}).update(
        min_clearance=0.2, min_track_width=0.25, min_via_diameter=0.6, min_through_hole_diameter=0.3,
        min_hole_clearance=0.25, min_hole_to_hole=0.5, min_copper_edge_clearance=0.5)
    classes = pro.setdefault("net_settings", {}).setdefault("classes", [{"name": "Default"}])
    classes[0].update(clearance=0.2, track_width=0.25, via_diameter=0.6, via_drill=0.3)
    pro.setdefault("meta", {})["filename"] = path.name
    path.write_text(json.dumps(pro, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    parts = sys.argv[1:]
    if not parts:
        sys.exit(__doc__)
    make_switch_fp()
    for part in parts:
        p = load_part(part)
        out = CARRIER / "tiles" / part
        out.mkdir(parents=True, exist_ok=True)
        stem = out / f"{part}_tile"
        comps = components(p)
        write_sch(p, comps, stem.with_suffix(".kicad_sch"))
        write_pcb(p, comps, stem.with_suffix(".kicad_pcb"))
        write_pro(stem.with_suffix(".kicad_pro"))
        (out / "fp-lib-table").write_text(FP_TABLE, encoding="utf-8")
        c = list(cells(p).values())
        print(f"{part}: DIP-{p['n']} VCC=接点{p['vcc']} GND=接点{p['gnd']} "
              f"入力セル {c.count('io')} / クロックセル {c.count('clk')} / 出力セル(LEDのみ) {c.count('out')} / "
              f"DNP {c.count('dnp')} -> {stem.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
