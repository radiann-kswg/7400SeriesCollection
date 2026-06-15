#!/usr/bin/env python3
"""
kicad_lib.py

KiCAD シンボルライブラリ (.kicad_sym) を **堅牢に** 解析するための共通モジュール。

従来 ``kicad_sch_gen.py`` が自前の正規表現でライブラリを解析していたが、
ライブラリのフォーマット変更（KiCAD のバージョンアップ）に弱かった。
本モジュールは ``sexpdata`` による正式な S-expression パースに置き換え、

  - シンボル名の列挙
  - (extends ...) の解決
  - ユニット別ピン情報の抽出
  - 「74xNN → 実シンボル」の **自動探索**（ハードコード表に依存しない）

を提供する。``lib_symbols`` への埋め込み用には、バランスの取れた括弧スライスで
元テキストをそのまま切り出す（フォーマット完全保存）。

依存: ``pip install sexpdata``
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

try:
    import sexpdata
    from sexpdata import Symbol
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "kicad_lib は sexpdata を必要とします。`pip install sexpdata` を実行してください。"
    ) from exc


# ============================================================
# S-expression ナビゲーション・ヘルパ
# ============================================================

def _head(node) -> str | None:
    """リストノードの先頭シンボル名（例: (symbol ...) → "symbol"）。"""
    if isinstance(node, list) and node and isinstance(node[0], Symbol):
        return node[0].value()
    return None


def _children(node, head: str) -> list:
    """node の直下で先頭が head の子ノードを列挙。"""
    if not isinstance(node, list):
        return []
    return [c for c in node[1:] if _head(c) == head]


def _atom(v):
    """Symbol を文字列に、それ以外はそのまま返す。"""
    return v.value() if isinstance(v, Symbol) else v


# ============================================================
# テキストレベル: バランス括弧スライス（埋め込み用に原文保存）
# ============================================================

def extract_block_text(content: str, name: str) -> str | None:
    """``(symbol "name" ...)`` ブロックを **原文のまま** 切り出す。"""
    marker = f'(symbol "{name}"'
    start = content.find(marker)
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(content[start:]):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return content[start:start + i + 1]
    return None


# ============================================================
# ライブラリのロード（キャッシュ付き）
# ============================================================

@lru_cache(maxsize=8)
def _load_text(lib_path: str) -> str | None:
    p = Path(lib_path)
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


@lru_cache(maxsize=8)
def _parse(lib_path: str):
    text = _load_text(lib_path)
    if text is None:
        return None
    return sexpdata.loads(text)


# ============================================================
# シンボル名の列挙
# ============================================================

def list_symbol_names(lib_path: str) -> list[str]:
    """ライブラリ内のトップレベルシンボル名を列挙。"""
    root = _parse(lib_path)
    if root is None:
        return []
    return [str(s[1]) for s in _children(root, "symbol")]


def find_symbol_node(lib_path: str, name: str):
    """名前でトップレベルシンボルノードを取得（無ければ None）。"""
    root = _parse(lib_path)
    if root is None:
        return None
    for s in _children(root, "symbol"):
        if str(s[1]) == name:
            return s
    return None


def resolve_extends(lib_path: str, name: str) -> str:
    """(extends "base") を解決し、最終的な基底シンボル名を返す。"""
    seen = set()
    cur = name
    while cur and cur not in seen:
        seen.add(cur)
        node = find_symbol_node(lib_path, cur)
        if node is None:
            return cur
        ext = _children(node, "extends")
        if not ext:
            return cur
        cur = str(ext[0][1])
    return cur


# ============================================================
# ピン解析（sexpdata ベース）
# ============================================================

def parse_pins_by_unit(symbol_node) -> dict[int, list[dict]]:
    """
    シンボルノードからユニット番号別にピン情報を抽出。

    戻り値: {unit:[{"num","name","x","y","type"}...]}
    body style 2 (demorgan) の重複ピンは unit:num で除去。
    """
    result: dict[int, list[dict]] = {}
    seen: set[str] = set()
    base = str(symbol_node[1]).split(":")[-1]
    pat = re.compile(r"^" + re.escape(base) + r"_(\d+)_(\d+)$")

    for sub in _children(symbol_node, "symbol"):
        m = pat.match(str(sub[1]))
        if not m:
            continue
        unit = int(m.group(1))
        for pin in _children(sub, "pin"):
            ptype = _atom(pin[1]) if len(pin) > 1 else "unspecified"
            at = _children(pin, "at")
            if not at:
                continue
            x = float(at[0][1])
            y = float(at[0][2])
            num = name = None
            for nn in _children(pin, "number"):
                num = nn[1]
            for nm in _children(pin, "name"):
                name = nm[1]
            if num is None:
                continue
            key = f"{unit}:{num}"
            if key in seen:
                continue
            seen.add(key)
            result.setdefault(unit, []).append({
                "num": num,
                "name": name if name is not None else num,
                "x": x,
                "y": y,
                "type": ptype,
            })
    return result


# ============================================================
# 74xNN → 実シンボル 自動探索
# ============================================================

# 探索するロジックファミリの優先順位（先頭ほど優先）。
# CLAUDE.md のファクトチェック方針（CMOS / TI HC 優先）に合わせつつ、
# 既存マップが LS 中心だったため LS を先頭に据える（出力の連続性確保）。
DEFAULT_FAMILY_PREF = [
    "LS", "HC", "HCT", "S", "F", "ALS", "AS",
    "AHC", "AHCT", "AC", "ACT", "LV", "LVC", "LVT",
    "ABT", "BCT", "CBT", "LCX", "VHC", "",  # "" = 7400 等プレーン
]


def _candidate_names(numeric: str, family_pref: list[str]) -> list[str]:
    """"00" 等の数値部から候補シンボル名を優先順に生成。"""
    cands = []
    for fam in family_pref:
        cands.append(f"74{fam}{numeric}")
    return cands


def discover_symbol(lib_path: str, part_number: str,
                    family_pref: list[str] | None = None) -> str | None:
    """
    "74xNN" に対応する実シンボル名を 74xx ライブラリから自動探索。

    見つからなければ None。ハードコード表に依存せず、ライブラリに実在する
    シンボルのみを返すため、ライブラリ更新で新部品が増えれば自動追従する。
    """
    m = re.match(r"^74x(\d+[A-Za-z]*)$", part_number)
    if not m:
        return None
    numeric = m.group(1)
    fam = family_pref or DEFAULT_FAMILY_PREF
    names = set(list_symbol_names(lib_path))
    if not names:
        return None
    for cand in _candidate_names(numeric, fam):
        if cand in names:
            return cand
    # フォールバック: 末尾が数値部に一致する任意ファミリ（_数字 サフィックス無視）
    rx = re.compile(r"^74[A-Z]*" + re.escape(numeric) + r"$")
    matches = sorted(n for n in names if rx.match(n))
    return matches[0] if matches else None


def find_power_unit(pins_by_unit: dict[int, list[dict]]) -> int | None:
    """power_in ピンを含むユニット番号を返す。"""
    for unit, pins in pins_by_unit.items():
        if unit == 0:
            continue
        if any(p["type"] == "power_in" for p in pins):
            return unit
    return None
