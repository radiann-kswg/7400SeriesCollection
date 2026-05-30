#!/usr/bin/env python3
"""
kicad_sch_gen.py

KiCAD 8 形式 (.kicad_sch version 20231120) の実回路図を生成するモジュール。
KiCAD 標準ライブラリからシンボル定義を取得し、シンボル配置・ネットラベル・
電源シンボルを含む有効な回路図を生成する。

生成できない部品の場合は None を返し、呼び出し元がテキストアノテーション
形式にフォールバックする。
"""

import re
import uuid as _uuid_mod
from pathlib import Path

# ============================================================
# KiCAD ライブラリパス
# ============================================================
KICAD_LIB_DIR = Path(r"C:\Program Files\KiCad\10.0\share\kicad\symbols")

# ============================================================
# 部品番号 → KiCADライブラリシンボル マッピング
# "74xNN" -> (lib_filename_without_ext, base_symbol_name)
# 実際のKiCADライブラリ (74xx.kicad_sym) に存在するシンボルのみ登録
# ============================================================
PART_TO_KICAD_SYM: dict[str, tuple[str, str]] = {
    # ── バッファ・インバータ ──────────────────────────────────────
    "74x04":  ("74xx", "74LS04"),
    "74x05":  ("74xx", "74LS05"),
    "74x06":  ("74xx", "74LS06"),
    "74x07":  ("74xx", "74LS07"),
    "74x14":  ("74xx", "74LS14"),
    "74x125": ("74xx", "74LS125"),
    "74x126": ("74xx", "74LS126"),
    # ── NANDゲート ───────────────────────────────────────────────
    "74x00":  ("74xx", "74LS00"),
    "74x10":  ("74xx", "74LS10"),
    "74x20":  ("74xx", "74LS20"),
    "74x30":  ("74xx", "74LS30"),
    "74x133": ("74xx", "74LS133"),
    # ── NORゲート ───────────────────────────────────────────────
    "74x02":  ("74xx", "74LS02"),
    "74x27":  ("74xx", "74LS27"),
    # ── ANDゲート ───────────────────────────────────────────────
    "74x08":  ("74xx", "74LS08"),
    "74x11":  ("74xx", "74LS11"),
    # ── ORゲート ────────────────────────────────────────────────
    "74x32":  ("74xx", "74LS32"),
    # ── XOR / XNOR ──────────────────────────────────────────────
    "74x86":  ("74xx", "74LS86"),
    "74x266": ("74xx", "74LS266"),
    # ── フリップフロップ ──────────────────────────────────────────
    "74x74":  ("74xx", "74LS74"),
    "74x76":  ("74xx", "74LS76"),
    "74x112": ("74xx", "74LS112"),
    # ── ラッチ・レジスタ ──────────────────────────────────────────
    "74x75":  ("74xx", "74LS75"),
    "74x373": ("74xx", "74LS373"),
    "74x374": ("74xx", "74LS374"),
    # ── マルチプレクサ ────────────────────────────────────────────
    "74x151": ("74xx", "74LS151"),
    "74x153": ("74xx", "74LS153"),
    "74x157": ("74xx", "74LS157"),
    "74x158": ("74xx", "74LS158"),
    # ── デマルチプレクサ・デコーダ ─────────────────────────────────
    "74x138": ("74xx", "74LS138"),
    "74x139": ("74xx", "74LS139"),
    "74x154": ("74xx", "74LS154"),
    "74x155": ("74xx", "74LS155"),
    "74x156": ("74xx", "74LS156"),
    # ── カウンタ ─────────────────────────────────────────────────
    "74x90":  ("74xx", "74LS90"),
    "74x93":  ("74xx", "74LS93"),
    "74x160": ("74xx", "74LS160"),
    "74x161": ("74xx", "74LS161"),
    "74x163": ("74xx", "74LS163"),
    "74x192": ("74xx", "74LS192"),
    "74x193": ("74xx", "74LS193"),
    # ── 算術演算 ─────────────────────────────────────────────────
    "74x283": ("74xx", "74LS283"),
    "74x181": ("74xx", "74LS181"),
    # ── シフトレジスタ ────────────────────────────────────────────
    "74x164": ("74xx", "74LS164"),
    "74x165": ("74xx", "74LS165"),
    "74x166": ("74xx", "74LS166"),
    "74x194": ("74xx", "74LS194"),
    "74x595": ("74xx", "74LS595"),
}

# ============================================================
# ユーティリティ
# ============================================================

def _new_uuid() -> str:
    return str(_uuid_mod.uuid4())


def _snap(v: float, grid: float = 1.27) -> float:
    """最近傍グリッド値にスナップ（KiCAD 100mil/2.54mm グリッド）"""
    return round(round(v / grid) * grid, 4)


def _coord(v: float) -> str:
    """座標を KiCAD S-expression 用文字列に変換"""
    return f"{v:.4f}".rstrip("0").rstrip(".")


# ============================================================
# KiCAD ライブラリパーサ
# ============================================================

def _extract_block(content: str, name: str) -> str | None:
    """S-expression から指定名の最初のブロックを抽出する。"""
    marker = f'(symbol "{name}"'
    start = content.find(marker)
    if start == -1:
        return None
    depth, end = 0, start
    for i, ch in enumerate(content[start:]):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = start + i + 1
                break
    return content[start:end]


def _load_lib(lib_name: str) -> str | None:
    """ライブラリファイルを読み込む。存在しない場合は None を返す。"""
    path = KICAD_LIB_DIR / f"{lib_name}.kicad_sym"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def extract_sym_for_embed(lib_name: str, sym_name: str) -> str | None:
    """
    ライブラリからシンボル定義を取得し、lib_symbols 埋め込み用に
    外側の名前を "{lib_name}:{sym_name}" に変換して返す。

    (extends ...) を持つシンボル（例: 7400 → 74LS00）の場合は
    基底シンボルに遡って完全定義を返す。
    """
    lib_content = _load_lib(lib_name)
    if lib_content is None:
        return None

    sym_def = _extract_block(lib_content, sym_name)
    if sym_def is None:
        return None

    # extends を解決: 継承先が基底定義を持つ
    extends_m = re.search(r'\(extends\s+"([^"]+)"\)', sym_def)
    if extends_m:
        base_name = extends_m.group(1)
        base_def = _extract_block(lib_content, base_name)
        if base_def:
            sym_def = base_def
            sym_name = base_name  # 埋め込み名を基底に変更

    # 外側の名前を "lib:sym" 形式に変換（先頭の1箇所のみ）
    embed_id = f"{lib_name}:{sym_name}"
    return sym_def.replace(f'(symbol "{sym_name}"', f'(symbol "{embed_id}"', 1)


def parse_pins_by_unit(sym_def: str, sym_name: str) -> dict[int, list[dict]]:
    """
    シンボル定義からユニット番号ごとのピン情報を抽出する。

    戻り値: {unit_num: [{"num": str, "name": str, "x": float, "y": float,
                         "type": str}, ...]}
    unit_num 0 = 全ユニット共通（通常は描画要素のみ）
    """
    result: dict[int, list[dict]] = {}
    _seen_pins: set[str] = set()  # 重複除去 (demorgan body styleで同ピンが2度出現する)

    # サブシンボル "{sym_name}_N_M" のブロックを走査
    sub_pat = re.compile(r'\(symbol\s+"' + re.escape(sym_name) + r'_(\d+)_(\d+)"')
    for m_sub in sub_pat.finditer(sym_def):
        unit_num = int(m_sub.group(1))
        # body style: 1 = normal, 2 = demorgan, 0 = 全スタイル共通
        # ピンは1度だけ登録すれば良いのでstyle 2は重複チェックで弾く

        # サブブロックの範囲を取得
        s = m_sub.start()
        depth, e = 0, s
        for i, ch in enumerate(sym_def[s:]):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    e = s + i + 1
                    break
        block = sym_def[s:e]

        # ブロック内のピンを抽出
        for m_pin in re.finditer(
            r'\(pin\s+(\S+)\s+\S+\s+\(at\s+([\d.\-]+)\s+([\d.\-]+)',
            block,
        ):
            pin_type = m_pin.group(1)
            px = float(m_pin.group(2))
            py = float(m_pin.group(3))

            # ピン番号と名前を探す
            pin_tail = block[m_pin.start() : m_pin.start() + 600]
            num_m = re.search(r'\(number\s+"([^"]*)"', pin_tail)
            name_m = re.search(r'\(name\s+"([^"]*)"', pin_tail)
            if not num_m:
                continue

            pnum = num_m.group(1)
            pname = name_m.group(1) if name_m else pnum

            dedup_key = f"{unit_num}:{pnum}"
            if dedup_key in _seen_pins:
                continue
            _seen_pins.add(dedup_key)

            if unit_num not in result:
                result[unit_num] = []
            result[unit_num].append({
                "num": pnum,
                "name": pname,
                "x": px,
                "y": py,
                "type": pin_type,
            })

    return result


def find_power_unit(pins_by_unit: dict[int, list[dict]]) -> int | None:
    """電源ピン (power_in) を含むユニット番号を返す。"""
    for unit_num, pins in pins_by_unit.items():
        if unit_num == 0:
            continue
        if any(p["type"] == "power_in" for p in pins):
            return unit_num
    return None


# ============================================================
# 座標計算
# ============================================================

def pin_abs(sym_x: float, sym_y: float, pin_local_x: float, pin_local_y: float,
            rotation: int = 0) -> tuple[float, float]:
    """
    シンボルのローカル座標系（Y軸上向き）からスキーマティックの絶対座標（Y軸下向き）に変換。

    rotation=0 の場合:
        abs_x = sym_x + pin_local_x
        abs_y = sym_y - pin_local_y   (Y軸反転)
    """
    if rotation == 0:
        return (_snap(sym_x + pin_local_x), _snap(sym_y - pin_local_y))
    # 90°単位の回転のみ対応
    import math
    rad = math.radians(-rotation)  # KiCAD は CCW が正
    cos_r = round(math.cos(rad))
    sin_r = round(math.sin(rad))
    lx, ly = pin_local_x, -pin_local_y  # Y軸反転してから回転
    rx = lx * cos_r - ly * sin_r
    ry = lx * sin_r + ly * cos_r
    return (_snap(sym_x + rx), _snap(sym_y + ry))


# ============================================================
# S-expression 要素生成
# ============================================================

def _sym_instance(
    lib_id: str,
    x: float, y: float,
    unit: int,
    ref: str,
    value: str,
    datasheet: str,
    pin_nums: list[str],
    sch_uuid: str,
    project_name: str,
    rotation: int = 0,
    pwr_ref_suffix: str = "",
) -> str:
    """シンボルインスタンスの S-expression を生成。"""
    u = _uuid_mod.uuid4
    sym_uuid = _new_uuid()
    ref_uuid = _new_uuid()
    val_uuid = _new_uuid()

    ref_display = f"#PWR{pwr_ref_suffix}" if pwr_ref_suffix else ref

    props = (
        f'    (property "Reference" "{ref_display}"\n'
        f'      (at {_coord(x)} {_coord(y - 5)} 0)\n'
        f'      (effects (font (size 1.27 1.27)))\n'
        f'    )\n'
        f'    (property "Value" "{value}"\n'
        f'      (at {_coord(x)} {_coord(y - 3.5)} 0)\n'
        f'      (effects (font (size 1.27 1.27)))\n'
        f'    )\n'
        f'    (property "Footprint" ""\n'
        f'      (at {_coord(x)} {_coord(y)} 0)\n'
        f'      (effects (font (size 1.27 1.27)) (hide yes))\n'
        f'    )\n'
        f'    (property "Datasheet" "{datasheet}"\n'
        f'      (at {_coord(x)} {_coord(y)} 0)\n'
        f'      (effects (font (size 1.27 1.27)) (hide yes))\n'
        f'    )\n'
    )

    pins_s = "".join(
        f'    (pin "{pn}"\n      (uuid "{_new_uuid()}")\n    )\n'
        for pn in pin_nums
    )

    instances_s = (
        f'    (instances\n'
        f'      (project "{project_name}"\n'
        f'        (path "/{sch_uuid}"\n'
        f'          (reference "{ref_display}")\n'
        f'          (unit {unit})\n'
        f'        )\n'
        f'      )\n'
        f'    )\n'
    )

    return (
        f'  (symbol\n'
        f'    (lib_id "{lib_id}")\n'
        f'    (at {_coord(x)} {_coord(y)} {rotation})\n'
        f'    (unit {unit})\n'
        f'    (exclude_from_sim no)\n'
        f'    (in_bom yes)\n'
        f'    (on_board yes)\n'
        f'    (dnp no)\n'
        f'    (fields_autoplaced yes)\n'
        f'    (uuid "{sym_uuid}")\n'
        + props + pins_s + instances_s +
        f'  )\n'
    )


def _power_sym_instance(
    sym_name: str,
    x: float, y: float,
    ref_num: int,
    sch_uuid: str,
    project_name: str,
    rotation: int = 0,
) -> str:
    """power:VCC / power:GND シンボルインスタンスを生成。"""
    return _sym_instance(
        lib_id=f"power:{sym_name}",
        x=x, y=y,
        unit=1,
        ref="#PWR",
        value=sym_name,
        datasheet="",
        pin_nums=["1"],
        sch_uuid=sch_uuid,
        project_name=project_name,
        rotation=rotation,
        pwr_ref_suffix=f"{ref_num:04d}",
    )


def _net_label(name: str, x: float, y: float, angle: int = 0) -> str:
    """ネットラベルの S-expression を生成。"""
    justify = "right" if angle == 0 else "left"
    return (
        f'  (label "{name}"\n'
        f'    (at {_coord(x)} {_coord(y)} {angle})\n'
        f'    (fields_autoplaced yes)\n'
        f'    (effects (font (size 1.27 1.27)) (justify {justify} bottom))\n'
        f'    (uuid "{_new_uuid()}")\n'
        f'  )\n'
    )


def _no_connect(x: float, y: float) -> str:
    """ノーコネクトマークの S-expression を生成。"""
    return (
        f'  (no_connect\n'
        f'    (at {_coord(x)} {_coord(y)})\n'
        f'    (uuid "{_new_uuid()}")\n'
        f'  )\n'
    )


def _wire(x1: float, y1: float, x2: float, y2: float) -> str:
    """ワイヤーの S-expression を生成。"""
    return (
        f'  (wire\n'
        f'    (pts (xy {_coord(x1)} {_coord(y1)}) (xy {_coord(x2)} {_coord(y2)}))\n'
        f'    (stroke (width 0) (type default))\n'
        f'    (uuid "{_new_uuid()}")\n'
        f'  )\n'
    )


def _sch_text(text: str, x: float, y: float, size: float = 1.27) -> str:
    """テキスト注記の S-expression を生成。"""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return (
        f'  (text "{escaped}"\n'
        f'    (exclude_from_sim no)\n'
        f'    (at {_coord(x)} {_coord(y)} 0)\n'
        f'    (effects (font (size {size} {size})) (justify left bottom))\n'
        f'    (uuid "{_new_uuid()}")\n'
        f'  )\n'
    )


# ============================================================
# レイアウト定義
# ============================================================

# 表示する最大ユニット数（それ以上はノーコネクトで省略）
_MAX_DISPLAY_GATE_UNITS = 4
_GATE_UNIT_SPACING_X = 40.64  # 16 × 2.54mm ≒ 0.64in 間隔


def _layout_units(
    gate_units: list[int],
    power_unit: int | None,
    pins_by_unit: dict[int, list[dict]],
    origin_x: float,
    origin_y: float,
) -> list[dict]:
    """
    各ユニットの配置座標を計算して返す。
    戻り値: [{"unit": N, "x": X, "y": Y, "is_power": bool}, ...]
    """
    layout = []
    for i, u in enumerate(gate_units[:_MAX_DISPLAY_GATE_UNITS]):
        layout.append({
            "unit": u,
            "x": origin_x + i * _GATE_UNIT_SPACING_X,
            "y": origin_y,
            "is_power": False,
        })
    if power_unit is not None:
        # 電源ユニットはゲートの下に配置
        layout.append({
            "unit": power_unit,
            "x": origin_x,
            "y": origin_y + 55,
            "is_power": True,
        })
    return layout


# ============================================================
# メイン: 実回路図生成
# ============================================================

def build_real_kicad_sch(
    part_number: str,
    replacements: dict,
) -> str | None:
    """
    KiCAD 8 形式の実回路図を生成して返す。
    シンボルが未登録または取得失敗の場合は None を返す。

    replacements には make_replacements() の戻り値を渡す。
    """

    # 1. シンボル検索
    if part_number not in PART_TO_KICAD_SYM:
        return None
    lib_name, sym_name = PART_TO_KICAD_SYM[part_number]

    lib_content = _load_lib(lib_name)
    if lib_content is None:
        return None

    # 2. シンボル定義を取得（extends を解決して基底シンボルを使用）
    raw_def = _extract_block(lib_content, sym_name)
    if raw_def is None:
        return None

    extends_m = re.search(r'\(extends\s+"([^"]+)"\)', raw_def)
    base_sym_name = extends_m.group(1) if extends_m else sym_name
    if extends_m:
        raw_def = _extract_block(lib_content, base_sym_name)
        if raw_def is None:
            return None

    embed_lib_id = f"{lib_name}:{base_sym_name}"

    # 3. ピン情報を解析
    pins_by_unit = parse_pins_by_unit(raw_def, base_sym_name)
    if not pins_by_unit:
        return None

    power_unit = find_power_unit(pins_by_unit)
    gate_units = sorted(
        u for u in pins_by_unit if u != 0 and u != power_unit
    )
    if not gate_units:
        return None

    # 4. 電源シンボル定義を取得
    power_lib = _load_lib("power")
    vcc_embed = (extract_sym_for_embed("power", "VCC") or "") if power_lib else ""
    gnd_embed = (extract_sym_for_embed("power", "GND") or "") if power_lib else ""

    # 5. シンボル定義を lib_symbols 埋め込み用に変換
    ic_embed = raw_def.replace(
        f'(symbol "{base_sym_name}"', f'(symbol "{embed_lib_id}"', 1
    )

    # 6. メタ情報
    description = replacements.get("{{DESCRIPTION}}", "")
    description_jp = replacements.get("{{DESCRIPTION_JP}}", "")
    category = replacements.get("{{CATEGORY}}", "99_other")
    all_owned = replacements.get("{{ALL_OWNED_PARTS}}", "")
    today = replacements.get("{{DATE}}", "2026-01-01")
    project_name = part_number

    sch_uuid = _new_uuid()

    # 7. タイトルブロック
    title_block = (
        f'  (title_block\n'
        f'    (title "{part_number} Demo Circuit")\n'
        f'    (date "{today}")\n'
        f'    (rev "0.1")\n'
        f'    (company "7400 Series Collection")\n'
        f'    (comment 1 "{description}")\n'
        f'    (comment 2 "{description_jp}")\n'
        f'    (comment 3 "Category: {category}")\n'
        f'    (comment 4 "IC: {all_owned}")\n'
        f'  )\n'
    )

    # 8. ユニットレイアウト
    origin_x = 76.2   # ~3in
    origin_y = 88.9   # ~3.5in (A4縦中央付近)
    layout = _layout_units(gate_units, power_unit, pins_by_unit, origin_x, origin_y)

    # 9. シンボルインスタンスとネットラベル・ノーコネクトを生成
    body_parts: list[str] = []
    pwr_ref_counter = 1
    is_first_gate = True

    # データシート URL (overview から取得できないのでデフォルトTI URL)
    datasheet = f"http://www.ti.com/lit/gpn/sn74ls{part_number.replace('74x', '').lower()}"

    for layout_entry in layout:
        unit = layout_entry["unit"]
        sx, sy = layout_entry["x"], layout_entry["y"]
        is_power = layout_entry["is_power"]

        pins_in_unit = pins_by_unit.get(unit, [])
        pin_nums = [p["num"] for p in pins_in_unit]

        if is_power:
            # 電源ユニット: シンボルインスタンスのみ配置（VCC/GNDは後述）
            body_parts.append(_sym_instance(
                lib_id=embed_lib_id,
                x=sx, y=sy,
                unit=unit,
                ref="U1",
                value=base_sym_name,
                datasheet=datasheet,
                pin_nums=pin_nums,
                sch_uuid=sch_uuid,
                project_name=project_name,
            ))
        else:
            # ゲートユニット
            body_parts.append(_sym_instance(
                lib_id=embed_lib_id,
                x=sx, y=sy,
                unit=unit,
                ref="U1",
                value=base_sym_name,
                datasheet=datasheet,
                pin_nums=pin_nums,
                sch_uuid=sch_uuid,
                project_name=project_name,
            ))

            if is_first_gate:
                # デモゲート: 信号ピンにネットラベルを付ける
                # 入力ピンを位置順 (y 降順 = 上から A, B, C ...) でソートして命名
                input_pins = [p for p in pins_in_unit if p["type"] == "input"]
                output_pins = [p for p in pins_in_unit if p["type"] == "output"]
                inout_pins = [p for p in pins_in_unit if p["type"] == "bidirectional"]
                # 上位ピン（y値が大きい）から順に A, B, C...
                input_pins_sorted = sorted(input_pins, key=lambda p: -p["y"])
                output_pins_sorted = sorted(output_pins, key=lambda p: -p["y"])
                input_letters = "ABCDEFGH"
                output_letters = "YZWV"

                def _pin_label(pin_obj, idx: int, letter_seq: str, prefix: str) -> str:
                    raw = pin_obj["name"]
                    if raw and raw not in ("~", ""):
                        return f"{prefix}_{raw}"
                    letter = letter_seq[idx] if idx < len(letter_seq) else str(idx + 1)
                    return f"{prefix}_{letter}"

                for i, pin in enumerate(input_pins_sorted):
                    ax, ay = pin_abs(sx, sy, pin["x"], pin["y"])
                    label = _pin_label(pin, i, input_letters, "IN")
                    body_parts.append(_net_label(label, ax, ay, angle=180))

                for i, pin in enumerate(output_pins_sorted):
                    ax, ay = pin_abs(sx, sy, pin["x"], pin["y"])
                    label = _pin_label(pin, i, output_letters, "OUT")
                    body_parts.append(_net_label(label, ax, ay, angle=0))

                for pin in inout_pins:
                    ax, ay = pin_abs(sx, sy, pin["x"], pin["y"])
                    pname = pin["name"] if pin["name"] and pin["name"] != "~" else pin["num"]
                    body_parts.append(_net_label(f"IO_{pname}", ax, ay, angle=0))

                # power_in 以外で上記に分類されないピン（enable, clock等）
                other_pins = [
                    p for p in pins_in_unit
                    if p["type"] not in ("input", "output", "bidirectional", "power_in", "power_out")
                ]
                for pin in other_pins:
                    ax, ay = pin_abs(sx, sy, pin["x"], pin["y"])
                    pname = pin["name"] if pin["name"] and pin["name"] != "~" else pin["num"]
                    body_parts.append(_net_label(f"SIG_{pname}", ax, ay, angle=180))
                is_first_gate = False
            else:
                # 未使用ゲート: 全ピンにノーコネクト
                for pin in pins_in_unit:
                    ax, ay = pin_abs(sx, sy, pin["x"], pin["y"])
                    body_parts.append(_no_connect(ax, ay))

    # 10. 電源シンボル（VCC / GND）を電源ユニットのピン位置に配置
    power_layout = next((e for e in layout if e["is_power"]), None)
    if power_layout and power_unit is not None:
        px, py = power_layout["x"], power_layout["y"]
        for pin in pins_by_unit.get(power_unit, []):
            ax, ay = pin_abs(px, py, pin["x"], pin["y"])
            pname_upper = pin["name"].upper()
            if "VCC" in pname_upper or "VDD" in pname_upper or pin["type"] == "power_in" and pin["y"] > 0:
                body_parts.append(_power_sym_instance("VCC", ax, ay, pwr_ref_counter, sch_uuid, project_name))
                pwr_ref_counter += 1
            elif "GND" in pname_upper or "VSS" in pname_upper or pin["type"] == "power_in" and pin["y"] < 0:
                body_parts.append(_power_sym_instance("GND", ax, ay, pwr_ref_counter, sch_uuid, project_name))
                pwr_ref_counter += 1

    # 11. 説明テキスト注記
    note_text = (
        f"Demo: {part_number} ({description_jp})\n"
        f"IC: {all_owned}\n"
        f"NOTE: unused gate inputs must be tied to VCC or GND in final design."
    )
    body_parts.append(_sch_text(note_text, 10, 20, size=1.27))

    # 12. 全体を組み立て
    lib_sym_section = "  (lib_symbols\n"
    for embed in [ic_embed, vcc_embed, gnd_embed]:
        if embed:
            # 各行に4スペースインデントを追加
            for line in embed.splitlines(keepends=True):
                lib_sym_section += "    " + line
            lib_sym_section += "\n"
    lib_sym_section += "  )\n"

    body_s = "".join(body_parts)

    sch_content = (
        f"(kicad_sch\n"
        f"  (version 20231120)\n"
        f"  (generator \"kicad_sch_gen\")\n"
        f"  (generator_version \"1.0\")\n"
        f"  (uuid \"{sch_uuid}\")\n"
        f"  (paper \"A4\")\n"
        + title_block
        + lib_sym_section
        + body_s
        + f"  (sheet_instances\n"
        f"    (path \"/\"\n"
        f"      (page \"1\")\n"
        f"    )\n"
        f"  )\n"
        f")\n"
    )

    return sch_content
