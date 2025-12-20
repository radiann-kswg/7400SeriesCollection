#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


def load_json_array(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"JSON array expected: {path}")
    return [obj for obj in data if isinstance(obj, dict)]


def save_json_array(path: str, data: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def pn_sort_key(pn: str) -> Tuple[int, str]:
    digits: List[str] = []
    for ch in reversed(pn):
        if ch.isdigit():
            digits.append(ch)
        else:
            break
    if digits:
        try:
            return (int("".join(reversed(digits))), pn)
        except ValueError:
            pass
    return (10**9, pn)


@dataclass(frozen=True)
class Category:
    key: str
    file_name: str


CATEGORIES: List[Category] = [
    Category("buffers_inverters", "01_buffers_inverters.json"),
    Category("nand_and_gates", "02_nand_and_gates.json"),
    Category("nor_or_gates", "03_nor_or_gates.json"),
    Category("xor_xnor_gates", "04_xor_xnor_gates.json"),
    Category("flipflops_latches", "05_flipflops_latches.json"),
    Category("encoders_decoders", "06_encoders_decoders.json"),
    Category("data_selectors_mux_demux", "07_data_selectors_mux_demux.json"),
    Category("counters", "08_counters.json"),
    Category("registers", "09_registers.json"),
    Category("arithmetic", "10_arithmetic.json"),
    Category("error_detection_correction",
             "11_error_detection_correction.json"),
    Category("memory_storage", "12_memory_storage.json"),
    Category("programmable_logic", "13_programmable_logic.json"),
    Category("system_controllers_timing", "14_system_controllers_timing.json"),
    Category("interfaces_links", "15_interfaces_links.json"),
    Category("analog_mixed_signal", "16_analog_mixed_signal.json"),
    Category("expanders", "17_expanders.json"),
    Category("carry_generators", "18_carry_generators.json"),
    Category("other", "99_other.json"),
]


def classify(desc_en: str, desc_jp: str) -> str:
    en = desc_en.lower()
    jp = desc_jp

    # 表記ゆれ吸収（ダッシュ/全角など）
    en = (
        en.replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
        .replace("×", "x")
        .replace("/", " ")
    )

    def has_any(haystack: str, needles: List[str]) -> bool:
        return any(n in haystack for n in needles)

    def matches_any_regex(haystack: str, patterns: List[str]) -> bool:
        return any(re.search(p, haystack) for p in patterns)

    # 優先度の高いものから判定（複合機能はここで落ちる）
    if has_any(
        en,
        [
            "encoder",
            "decoder",
            "priority encoder",
            "7-segment",
            "seven-segment",
            "7 segment",
            "segment driver",
            "display driver",
            "nixie",
            "cold-cathode",
            "cold cathode",
        ],
    ) or has_any(jp, ["デコーダ", "エンコーダ", "7セグ", "セグメント", "ニキシー", "冷陰極"]):
        return "encoders_decoders"

    if has_any(en, ["multiplexer", "demultiplexer", "selector", "data selector", "mux", "demux"]) or has_any(
        jp, ["マルチプレクサ", "デマルチプレクサ", "セレクタ"]
    ):
        return "data_selectors_mux_demux"

    if has_any(en, ["flip-flop", "flip flop", "master-slave", "master slave", "j-k", "jk", "latch", "bistable"]):
        return "flipflops_latches"

    # メモリ/ストレージ
    if has_any(
        en,
        [
            "ram",
            "rom",
            "prom",
            "fifo",
            "memory",
            "register file",
        ],
    ) or has_any(jp, ["メモリ", "RAM", "ROM", "PROM", "FIFO", "レジスタファイル"]):
        return "memory_storage"

    # プログラマブルロジック（PLA/FPLA等）
    if has_any(en, ["pla", "logic array", "field-programmable", "field programmable"]) or has_any(
        jp, ["論理アレイ", "プログラマブル", "PLA"]
    ):
        return "programmable_logic"

    # インタフェース/リンク系（物理層やバス規格名を含むもの）
    if has_any(
        en,
        [
            "ieee-488",
            "ieee 488",
            "gpib",
            "futurebus",
            "fiber-optic",
            "fiber optic",
            "data-link",
            "data link",
            "transmitter",
            "receiver",
            "ttl",
            "ecl",
            "gtl",
            "gtl+",
            "termination",
        ],
    ):
        return "interfaces_links"

    # システム制御/タイミング/メモリ制御系（controller/mapper/refresh/arbiter等）
    if has_any(
        en,
        [
            "controller",
            "refresh",
            "dram",
            "d ram",
            "d-ram",
            "mapper",
            "mapping",
            "memory cycle",
            "arbiter",
            "sequencer",
            "address generator",
            "sync generator",
            "timing generator",
            "interrupt",
            "priority controller",
            "system controller",
            "clock generator",
            "phase",
        ],
    ) or has_any(jp, ["コントローラ", "リフレッシュ", "メモリ", "マッパ", "割込み", "優先度", "シーケンサ", "同期"]):
        return "system_controllers_timing"

    # レジスタ/トランシーバ（メモリに該当しないもの）
    if has_any(
        en,
        [
            "shift register",
            "universal shift",
            "storage register",
            "register",
            "transceiver",
            "bus transceiver",
            "latched transceiver",
            "latchable transceiver",
            "bus driver",
            "buffered latch",
            "read-back",
            "readback",
            "pipeline",
            "port controller",
            "latchable",
        ],
    ):
        return "registers"

    if has_any(en, ["counter", "divider", "frequency divider", "timer", "rate multiplier", "count-down", "countdown"]):
        return "counters"

    # アナログ/混載
    if has_any(
        en,
        [
            "adc",
            "a/d",
            "analog",
            "voltage comparator",
            "comparator",
            "vco",
            "voltage-controlled oscillator",
            "voltage controlled oscillator",
            "crystal-controlled oscillator",
            "crystal controlled oscillator",
            "multivibrator",
            "monostable",
            "phase comparator",
            "digital pll",
        ],
    ) or has_any(jp, ["A/D", "ADC", "アナログ", "電圧", "発振", "VCO", "マルチバイブレータ", "単安定", "位相比較"]):
        return "analog_mixed_signal"

    # エキスパンダ類
    # NOTE: gateカテゴリの "expandable" に引っ張られないよう、
    # "expander" もしくは明確な "expandable control element" などに限定して判定。
    if matches_any_regex(en, [r"\bexpander\b"]) or has_any(
        jp, ["エキスパンダ", "拡張器"]
    ) or has_any(en, ["expandable control element", "expandable control elements"]):
        return "expanders"

    # キャリー・ジェネレータ類
    # NOTE: "carry" は ALU/adder 等にも頻出するため、"carry generator" 系の表現に限定。
    if has_any(
        en,
        [
            "carry generator",
            "lookahead carry",
            "look-ahead carry",
            "look ahead carry",
        ],
    ) or has_any(
        jp,
        [
            "キャリー・ジェネレータ",
            "キャリージェネレータ",
            "先行キャリ",
            "キャリー生成",
            "キャリ生成",
        ],
    ):
        return "carry_generators"

    # 誤り検出/訂正
    if has_any(
        en,
        [
            "edac",
            "ecc",
            "error detection",
            "error correction",
            "cyclic redundancy",
            "crc",
            "parity",
            "syndrome",
            "check",
            "polynomial",
        ],
    ) or has_any(jp, ["誤り", "訂正", "CRC", "パリティ", "シンドローム", "チェック"]):
        return "error_detection_correction"

    if has_any(
        en,
        [
            "alu",
            "arithmetic logic unit",
            "adder",
            "subtractor",
            "multiplier",
            "divider",
            "comparator",
            "converter",
            "accumulator",
            "shifter",
            "barrel shifter",
            "two's complement",
            "twos complement",
            "processor element",
            "processor slice",
        ],
    ) or has_any(jp, ["演算", "加算", "減算", "比較", "変換", "乗算", "除算", "シフタ", "補数"]):
        return "arithmetic"

    if has_any(
        en,
        [
            "inverter",
            "buffer",
            "line driver",
            "driver",
            "clock driver",
            "level translator",
        ],
    ):
        return "buffers_inverters"

    # ゲート類
    # NOTE: 'xor gate' が 'or gate' に部分一致して誤分類されるのを防ぐため、
    # ゲート判定は単語境界を使った正規表現を用いる。
    if matches_any_regex(en, [r"\bxor\b", r"\bxnor\b"]) or has_any(en, ["exclusive-or", "exclusive-nor"]):
        return "xor_xnor_gates"

    if matches_any_regex(en, [r"\bnand\b", r"\band\s+gate\b"]) or has_any(en, ["and-or-invert", "and-or"]):
        return "nand_and_gates"

    if matches_any_regex(en, [r"\bnor\b", r"\bor\s+gate\b"]):
        return "nor_or_gates"

    # JPヒント（ENが短い/特殊な場合）
    if has_any(jp, ["インバータ", "バッファ", "ドライバ"]):
        return "buffers_inverters"
    if has_any(jp, ["NAND", "AND", "インバート"]):
        return "nand_and_gates"
    if has_any(jp, ["NOR", "OR"]):
        return "nor_or_gates"
    if has_any(jp, ["XOR", "XNOR"]):
        return "xor_xnor_gates"
    if has_any(jp, ["フリップ", "ラッチ"]):
        return "flipflops_latches"
    if has_any(jp, ["デコーダ", "エンコーダ", "7セグ", "ニキシー"]):
        return "encoders_decoders"
    if has_any(jp, ["マルチプレクサ", "デマルチプレクサ", "セレクタ"]):
        return "data_selectors_mux_demux"
    if has_any(jp, ["カウンタ", "分周"]):
        return "counters"
    if has_any(jp, ["レジスタ", "トランシーバ", "シフト"]):
        return "registers"
    if has_any(jp, ["演算", "加算", "比較", "パリティ", "CRC", "変換"]):
        return "arithmetic"

    return "other"


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    overview_path = os.path.join(
        repo_root, "overview", "7400_series_ic_overview.json")

    out_dir = os.path.join(repo_root, "overview", "categories")
    os.makedirs(out_dir, exist_ok=True)

    items = load_json_array(overview_path)

    buckets: Dict[str, List[Dict[str, Any]]] = {c.key: [] for c in CATEGORIES}

    for obj in items:
        pn = obj.get("PartNumber")
        if not isinstance(pn, str):
            continue
        desc = obj.get("Description")
        desc_jp = obj.get("Description_JP")
        if not isinstance(desc, str):
            desc = ""
        if not isinstance(desc_jp, str):
            desc_jp = ""

        cat = classify(desc, desc_jp)
        if cat not in buckets:
            cat = "other"
        # overview には Category を持たせるが、categories/*.json はスキーマ上不要なので除去する。
        clean_obj = dict(obj)
        clean_obj.pop("Category", None)
        buckets[cat].append(clean_obj)

    for c in CATEGORIES:
        arr = buckets[c.key]
        arr.sort(key=lambda o: pn_sort_key(str(o.get("PartNumber", ""))))
        save_json_array(os.path.join(out_dir, c.file_name), arr)
        print(f"[INFO] Wrote {c.key}: {c.file_name} ({len(arr)} items)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
