#!/usr/bin/env python3
"""
generate_specimen_tile.py — Specimen Tile（共通キャリア）の回路図と基板を型番ごとに生成する。

仕様: pcb-demo/REQUIREMENTS.md / pcb-demo/_carrier/README.md
- 回路は全型番共通。型番で変わるのは「電源接点・未実装セル（DNP）・シルク」だけ。
- ピン数・VCC/GND・各ピンの方向は pcb-demo/_carrier/pinspec/{型番}.json（データシート目視で確認済み）から読む。
  無い型番は生成しない。角ピン決め打ちはしない。
- リファレンス: 接点 k ごとに SWk / R(20+k)=Rd 1k / Rk=Rled 4.7k / Dk、ソケット U1 のパッド k。
- 接点の種類: 入力・双方向 = スイッチ + LED、出力（output / tri_state）= LED のみ（SWk・R(20+k) は DNP）、
  未使用・NC・open_collector = 全部 DNP（OC 出力は H 側へ引けないので LED を点けられない）。

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
    "RD": ("Device:R", "Resistor_SMD:R_0603_1608Metric", "1k", "C21190"),
    "RL": ("Device:R", "Resistor_SMD:R_0603_1608Metric", "4.7k", "C23162"),
    "D": ("Device:LED", "LED_SMD:LED_0603_1608Metric", "RED", "C2286"),
    "C": ("Device:C", "Capacitor_SMD:C_0603_1608Metric", "100nF", "C14663"),
    "U": ("Connector_Generic:Conn_02x10_Counter_Clockwise", "Package_DIP:DIP-20_W7.62mm_Socket", "DIP20_Socket_300mil", ""),
    "J": ("Connector_Generic:Conn_01x02", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "5V_IN", ""),
}
MPN = {  # LCSC 部品ページで確認（2026-09-16）
    "SW": ("SHOU HAN", "MSS12C02LS-BB2.0"),
    "RD": ("UNI-ROYAL", "0603WAF1001T5E"),
    "RL": ("UNI-ROYAL", "0603WAF4701T5E"),
    "D": ("Hubei KENTO", "KT-0603R"),
    "C": ("YAGEO", "CC0603KRX7R9BB104"),
}

# 基板 [mm]。原点は左上、y は下向き
W = H = 50.0
XC = 25.0
PITCH = 4.6                           # I/O 列ピッチ（接点 1..10 は下側、20..11 は上側に左から並ぶ）
ROW = {"top": 21.19, "bot": 28.81}    # ソケットのパッド行
YS = 6.0                              # 上側スイッチ中心（下側は H - YS）
RAIL, BUS_Y = 1.0, 24.175             # +5V 外周レール / ソケット下を通る電源バス
SIG, PWR, GNDW = 0.25, 0.5, 0.3

# I/O セルの局所座標 (u, v)。v はスイッチ → ソケット方向。スイッチのパッド列は u = -1.95 側
CELL_POS = {"SW": (0, 0), "D": (-1.6, 6.1), "RL": (-1.6, 9.2), "RD": (0, 9.2)}
CELL_TRACKS = [  # (ネット, 幅, 点列)
    ("+5V", PWR, [(-1.95, -2.25), (-1.95, -5.0)]),
    ("GND", GNDW, [(-1.95, 2.25), (-2.1, 3.3), (-2.1, 4.813), (-1.6, 5.313)]),
    ("SWC", SIG, [(-1.95, 0.75), (-0.82, 0.75), (-0.82, 2.0), (0, 2.82), (0, 8.375)]),  # 位置決め穴を避けて本体下を通す
    ("LA", SIG, [(-1.6, 6.887), (-1.6, 8.375)]),
    ("P", SIG, [(-1.6, 10.025), (0, 10.025)]),
]
CELL_VIA = (-2.1, 3.3)  # GND


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

    def contact(i):  # ピン 1 側へ端寄せして挿す（REQUIREMENTS §2.4）
        return i if i <= n // 2 else i + 20 - n

    ov = json.loads((ROOT / "overview" / "7400_series_ic_overview.json").read_text(encoding="utf-8"))
    o = next(x for x in ov if x["PartNumber"] == part)
    return dict(part=part, n=n, vcc=contact(vcc[0]), gnd=contact(gnd[0]),
                names={contact(i): v["name"] for i, v in pins.items()},
                dirs={contact(i): v["dir"] for i, v in pins.items()},
                desc=o["Description"], desc_jp=o.get("Description_JP", ""), cat=o["Category"])


def cells(p):
    """電源以外の接点 k -> "io"（スイッチ + LED）/ "out"（LED のみ）/ "dnp"（未実装）"""
    kind = {"input": "io", "bidirectional": "io", "output": "out", "tri_state": "out"}
    return {k: kind.get(p["dirs"].get(k), "dnp") for k in range(1, 21) if k not in (p["vcc"], p["gnd"])}


def components(p):
    """[(ref, 種別, ピン番号→ネット, DNP)]"""
    u1 = {str(k): {p["vcc"]: "+5V", p["gnd"]: "GND"}.get(k, f"P{k}") for k in range(1, 21)}
    out = [("U1", "U", u1, False),
           ("J1", "J", {"1": "+5V", "2": "GND"}, False),
           ("C1", "C", {"1": "+5V", "2": "GND"}, False)]
    for k, kind in cells(p).items():
        out += [(f"SW{k}", "SW", {"1": "+5V", "2": f"SWC{k}", "3": "GND"}, kind != "io"),
                (f"R{20 + k}", "RD", {"1": f"SWC{k}", "2": f"P{k}"}, kind != "io"),
                (f"R{k}", "RL", {"1": f"LA{k}", "2": f"P{k}"}, kind == "dnp"),
                (f"D{k}", "D", {"1": "GND", "2": f"LA{k}"}, kind == "dnp")]
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
            ax, ay = sg.pin_abs(x, y, px, py)
            if nets[num] in ("+5V", "GND"):
                power(nets[num], ax, ay)
            else:
                body.append(sg._net_label(nets[num], ax, ay))
        return {num: sg.pin_abs(x, y, px, py) for num, (px, py) in pins[lib_id].items()}

    fixed = {"U1": (48, 118), "J1": (32, 176), "C1": (56, 176)}
    offs = {"SW": 0, "RD": 12, "RL": 20, "D": 30}
    for ref, kind, nets, dnp in comps:
        if ref in fixed:
            gx, gy = fixed[ref]
        else:
            k = int(re.sub(r"\D", "", ref)) - (20 if kind == "RD" else 0)
            gx, gy = 88 + (k - 1) % 5 * 48 + offs[kind], 32 + (k - 1) // 5 * 48
        at = place(ref, kind, gx * G, gy * G, nets, dnp)
        if ref == "J1":  # 外部給電なので PWR_FLAG を立てる
            power("+5V", *at["1"], flag=True)
            power("GND", *at["2"], flag=True)

    note = (f"{part} Specimen Tile v0.1 ({p['desc']})\\n"
            f"DIP-{p['n']}: VCC = contact {p['vcc']}, GND = contact {p['gnd']}\\n"
            "Cell k: SWk selects +5V/GND -> R(20+k) 1k -> contact k -> Rk 4.7k -> Dk -> GND\\n"
            "Output contacts (per pinspec): SWk and R(20+k) are DNP, LED only\\n"
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
    """MSK12C02（横レバー）のランドを流用し、縦レバー品 MSS12C02LS 用に外形・courtyard を本体寸法へ詰める。"""
    # ponytail: ランド配置は MSK12C02 と同一と仮定。MSS12C02LS の寸法図で照合するまで発注不可（ORDER_CHECKLIST A）
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
                  'Pads copied from SW_SPDT_Shouhan_MSK12C02 - verify against the MSS12C02LS drawing")', body)
    body = body.replace(f'"{old}"', f'"{SW_FP}"')
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

    def track(pts, name, w):
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(V(*a))
            t.SetEnd(V(*b))
            t.SetWidth(mm(w))
            t.SetLayer(pcbnew.F_Cu)
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

    for k in cells(p):
        f = frame(k)
        g = f["g"]
        for ref in (f"SW{k}", f"R{20 + k}", f"R{k}", f"D{k}"):
            fp, kind = fps[ref]
            fp.SetOrientationDegrees(f["rot"])
            fp.SetPosition(V(*g(*CELL_POS[kind])))
        expect(fps[f"SW{k}"][0], "1", g(-1.95, -2.25))
        expect(fps[f"D{k}"][0], "1", g(-1.6, 6.1 - 0.787))
        name = {"+5V": "+5V", "GND": "GND", "SWC": f"SWC{k}", "LA": f"LA{k}", "P": f"P{k}"}
        for kind, w, pts in CELL_TRACKS:
            track([g(*q) for q in pts], name[kind], w)
        via(*g(*CELL_VIA), "GND")
        track([g(0, 10.025), (f["xc"], f["lane"]), (f["xpad"], f["lane"]), (f["xpad"], f["ypad"])], f"P{k}", SIG)

    # +5V: 外周レール（上・下・左）と、ソケット下を通って VCC 接点へ行くバス
    top = max(frame(k)["g"](-1.95, 0)[0] for k in cells(p) if k > 10)  # 全列のスタブがレールに乗るように
    bot = max(frame(k)["g"](-1.95, 0)[0] for k in cells(p) if k <= 10)
    track([(top, RAIL), (RAIL, RAIL), (RAIL, H - RAIL), (bot, H - RAIL)], "+5V", PWR)
    j1, c1 = fps["J1"][0], fps["C1"][0]
    j1.SetPosition(V(5.5, BUS_Y))
    c1.SetOrientationDegrees(-90)
    c1.SetPosition(V(9.5, 25.0))
    c1p1, c1p2 = pad_xy(c1, "1"), pad_xy(c1, "2")
    assert c1p1[1] < c1p2[1], "C1 の向きが想定と逆"
    vx, vy = pad_xy(u1, str(p["vcc"]))
    track([(RAIL, BUS_Y), (vx, BUS_Y), (vx, vy)], "+5V", PWR)
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

    # シルク: 各列のピン名、型番・機能名、給電表示。裏面にカテゴリ・版・ライセンス
    for k in range(1, 21):
        label = {p["vcc"]: "VCC", p["gnd"]: "GND"}.get(k, p["names"].get(k, ""))
        if label:
            text(label, frame(k)["xc"], RAIL if k > 10 else H - RAIL, 0.8)
    text(p["part"], 43.8, 21.2, 1.6)
    en, jp = textwrap.wrap(p["desc"], 16), textwrap.wrap(p["desc_jp"], 10)
    for i, line in enumerate(en + jp):  # ソケット右の余白（x 38.6〜49.5）。和文は字面が高いので 0.4 空ける
        text(line, 38.6, 23.0 + 1.2 * i + 0.4 * (i >= len(en)), 0.8, left=True)
    text("+5V", 5.5, 22.0, 0.8)
    text("GND", 5.5, 28.9, 0.8)
    for i, s in enumerate([f"7400 Specimen Tile v0.1  {p['part']}", p["cat"], "MIT License"]):
        text(s, XC, 23.5 + 1.5 * i, 1.0, layer=pcbnew.B_SilkS)  # 裏面はソケットのパッド行の間に

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
              f"入力セル {c.count('io')} / 出力セル(LEDのみ) {c.count('out')} / DNP {c.count('dnp')} -> {stem.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
