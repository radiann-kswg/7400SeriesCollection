#!/usr/bin/env python3
"""
check_demo_pin_tables.py

usage/{カテゴリ}/{型番}/01_*.md（デモ資料）のピン表と、そこから作った
pcb-demo/{カテゴリ}/{型番}/{型番}.kicad_sch の【ピン配置】注記を検査する。

既定は読み取り専用。PDF からの機械抽出で起きた誤り（Issue #1）を再発させないため、
次を検出する。

  E-RANGE   ピン数が DIP の標準ピン数でない / pinspec の package_pins と違う
  E-MISS    ピン番号の欠け
  E-DUP     ピン番号の重複
  E-NAME    ピン名として不自然な語（FK, I, O, Feedback, Active-Low など、X/X 形式）
  E-SAME    電源・NC 以外で同じピン名が複数ある（OE, OE, OE など）
  E-SPEC    pinspec（pcb-demo/_carrier/pinspec/{型番}.json）と名前・反転表記が違う
  E-KICAD   KiCad の【ピン配置】注記がデモ資料のピン表と違う
  I-UNCHK   ピン表の注記に一次資料での照合記録がない（情報のみ、終了コードに影響しない）

反転表記: デモ資料では Low アクティブの信号名を `/` で始める（例 /CLR, /1OE, /1Q）。
pinspec 側は `~{1Q}` または attr の `active_low` を反転とみなす。

使い方:
  python scripts/check_demo_pin_tables.py                    # 全件を検査
  python scripts/check_demo_pin_tables.py --part 74x164      # 型番を指定
  python scripts/check_demo_pin_tables.py --show-info        # I-UNCHK も表示
  python scripts/check_demo_pin_tables.py --sync-kicad       # E-KICAD の書き換え内容を表示（書き込まない）
  python scripts/check_demo_pin_tables.py --sync-kicad --apply  # 【ピン配置】注記だけを書き換える

終了コード: 0 = エラーなし、1 = エラーあり
標準ライブラリのみで動く（generate_pcb_demo_projects.py の整形関数を再利用する）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import generate_pcb_demo_projects as gen  # noqa: E402

USAGE_DIR = BASE_DIR / "usage"
PCB_DEMO_DIR = BASE_DIR / "pcb-demo"
PINSPEC_DIR = PCB_DEMO_DIR / "_carrier" / "pinspec"

DIP_SIZES = {8, 14, 16, 18, 20, 22, 24, 28, 40}
# 機械抽出で紛れ込みやすい語（パッケージ名・表の見出し・I/O 種別・説明文）
BAD_NAMES = {
    "FK", "I", "O", "I/O", "IO", "FEEDBACK", "ACTIVE-LOW", "ACTIVE-HIGH",
    "ACTIVE", "LOW", "HIGH", "INPUT", "OUTPUT", "PIN", "NAME", "NO.", "TYPE", "DESCRIPTION",
}
SHARED_NAMES = {"VCC", "GND", "NC"}
VERIFIED_RE = re.compile(r"照合")
KICAD_PIN_RE = re.compile(r'\(text "【ピン配置】\\n((?:[^"\\]|\\.)*)"')


def norm(name: str) -> tuple[str, bool]:
    """(基底名, 反転) を返す。`/X`・`~{X}` を反転とみなす。"""
    s = name.strip().replace(" ", "")
    inv = False
    if s.startswith("~{") and s.endswith("}"):
        s, inv = s[2:-1], True
    elif s.startswith("/") and len(s) > 1:
        s, inv = s[1:], True
    return s.upper(), inv


def spec_name(pin: dict) -> tuple[str, bool]:
    base, inv = norm(pin.get("name") or "")
    attr = pin.get("attr") or []
    return base, inv or ("active_low" in attr)


def unescape_sch(s: str) -> str:
    return s.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")


def find_demo_files(part: str | None) -> list[tuple[str, str, Path]]:
    out = []
    for d in sorted(USAGE_DIR.glob("*/*/")):
        cat, pn = d.parent.name, d.name
        if part and pn != part:
            continue
        mds = sorted(d.glob("01_*.md"))
        if mds:
            out.append((cat, pn, mds[0]))
    return out


def pin_section_text(md_text: str) -> str:
    m = re.search(r"^## ピン配置.*?(?=^## |\Z)", md_text, re.M | re.S)
    return m.group(0) if m else ""


def check_part(cat: str, pn: str, md: Path) -> tuple[list[str], list[str], dict | None]:
    errors: list[str] = []
    infos: list[str] = []
    info = gen.parse_demo_md(md)
    pins = info["pins"]
    sync = None

    if pins:
        nums = [int(p["pin"]) for p in pins]
        n = max(nums)
        spec_path = PINSPEC_DIR / f"{pn}.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8")) if spec_path.exists() else None

        expected = spec["package_pins"] if spec else None
        if expected and n != expected:
            errors.append(f"E-RANGE ピン番号の最大 {n} が pinspec の package_pins {expected} と違う")
        elif n not in DIP_SIZES:
            errors.append(f"E-RANGE ピン番号の最大 {n} は DIP の標準ピン数ではない")
        total = expected or n
        out_of_range = sorted({x for x in nums if x < 1 or x > total})
        if out_of_range:
            errors.append(f"E-RANGE 範囲外のピン番号 {out_of_range}")
        miss = [i for i in range(1, total + 1) if i not in nums]
        if miss:
            errors.append(f"E-MISS 欠けているピン番号 {miss}")
        dup = sorted({x for x in nums if nums.count(x) > 1})
        if dup:
            errors.append(f"E-DUP 重複しているピン番号 {dup}")

        bases = []
        for p in pins:
            raw = p["name"]
            base, inv = norm(raw)
            parts = [norm(x)[0] for x in raw.split("/") if x]
            if not base or base in BAD_NAMES or base.startswith("ACTIVE"):
                errors.append(f"E-NAME {p['pin']}番「{raw}」はピン名ではない可能性が高い")
            elif len(parts) == 2 and parts[0] == parts[1]:
                errors.append(f"E-NAME {p['pin']}番「{raw}」は同じ名前の重ね書き（X/X）")
            bases.append((base, inv))
        # 反転の有無も区別する（1Q と /1Q は別の信号）
        same = sorted({("/" if i else "") + b for b, i in bases if b and b not in SHARED_NAMES and bases.count((b, i)) > 1})
        if same:
            errors.append(f"E-SAME 同じピン名が複数ある {same}")

        if spec:
            for p in pins:
                sp = spec["pins"].get(str(p["pin"]))
                if not sp:
                    continue
                if norm(p["name"]) != spec_name(sp):
                    want = ("/" if spec_name(sp)[1] else "") + spec_name(sp)[0]
                    errors.append(f"E-SPEC {p['pin']}番「{p['name']}」≠ pinspec「{want}」")

        if not VERIFIED_RE.search(pin_section_text(md.read_text(encoding="utf-8"))):
            infos.append("I-UNCHK ピン表に一次資料での照合記録がない（機械抽出のまま）")

    sch = PCB_DEMO_DIR / cat / pn / f"{pn}.kicad_sch"
    if sch.exists():
        text = sch.read_text(encoding="utf-8")
        m = KICAD_PIN_RE.search(text)
        if m:  # テキスト注釈版の回路図のみ（実シンボル回路図は KiCad ライブラリのピン名を使う）
            want = gen.format_pin_text(pins, cat, pn)
            have = unescape_sch(m.group(1))
            if have != want:
                errors.append("E-KICAD 【ピン配置】注記がデモ資料のピン表と違う")
                sync = {"path": sch, "span": m.span(1), "have": have, "want": want}
    return errors, infos, sync


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--part", help="汎用型番（例 74x164）")
    ap.add_argument("--show-info", action="store_true", help="I-UNCHK（照合記録なし）も表示する")
    ap.add_argument("--sync-kicad", action="store_true", help="E-KICAD の書き換え内容を表示する")
    ap.add_argument("--apply", action="store_true", help="--sync-kicad と併用時、【ピン配置】注記だけを書き換える")
    args = ap.parse_args()

    n_err = n_info = n_table = 0
    syncs = []
    for cat, pn, md in find_demo_files(args.part):
        errors, infos, sync = check_part(cat, pn, md)
        if gen.parse_demo_md(md)["pins"]:
            n_table += 1
        if sync:
            syncs.append(sync)
        shown = errors + (infos if args.show_info else [])
        if shown:
            print(f"[{pn}] {md.relative_to(BASE_DIR).as_posix()}")
            for e in shown:
                print(f"  {e}")
        n_err += len(errors)
        n_info += len(infos)

    print(f"\nピン表のある資料 {n_table} 件 / エラー {n_err} 件 / 照合記録なし {n_info} 件")

    if args.sync_kicad:
        for s in syncs:
            rel = s["path"].relative_to(BASE_DIR).as_posix()
            print(f"\n--- {rel}\n  現在: {s['have']!r}\n  修正: {s['want']!r}")
            if args.apply:
                raw = s["path"].read_bytes().decode("utf-8")
                # 改行コードを保ったまま注記の文字列部分だけを置き換える
                m = KICAD_PIN_RE.search(raw)
                new = raw[: m.start(1)] + gen._esc_sch(s["want"]) + raw[m.end(1):]
                s["path"].write_bytes(new.encode("utf-8"))
                print("  → 書き換えました")
        if syncs and not args.apply:
            print("\n（--apply を付けると【ピン配置】注記だけを書き換えます）")

    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
