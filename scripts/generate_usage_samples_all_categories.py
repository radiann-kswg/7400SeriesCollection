#!/usr/bin/env python3
"""
generate_usage_samples_all_categories.py

全カテゴリの入手済み7400シリーズICについて、実際に動作する最小デモ回路の資料
01_basic_function_demo.md を生成します。

generate_usage_samples_owned_01_04.py の全カテゴリ対応拡張版。
カテゴリ固有の回路構成（クロック・制御ピン・出力表示）に対応した記述を生成します。

使用方法:
  python3 scripts/generate_usage_samples_all_categories.py              # dry-run
  python3 scripts/generate_usage_samples_all_categories.py --download   # PDF DLあり
  python3 scripts/generate_usage_samples_all_categories.py --force      # 既存を上書き
  python3 scripts/generate_usage_samples_all_categories.py --part 74x74 # 特定パーツ
  python3 scripts/generate_usage_samples_all_categories.py --category 05_flipflops_latches
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Optional

try:
    from pypdf import PdfReader
    _PYPDF_AVAILABLE = True
except ImportError:
    _PYPDF_AVAILABLE = False
    PdfReader = None  # type: ignore[misc,assignment]


REPO_ROOT = Path(__file__).resolve().parents[1]
OVERVIEW_JSON_PATH = REPO_ROOT / "overview" / "7400_series_ic_overview.json"
HISTORY_JSON_PATH = REPO_ROOT / "getstarting" / "7400_series_ic_collection_acquisition_history.json"
DATASHEET_SOURCES_JSON_PATH = REPO_ROOT / "datasheets" / "datasheet_sources.json"
USAGE_DIR = REPO_ROOT / "usage"
LOCAL_PDF_ROOT = REPO_ROOT / "datasheets" / "_download"
DOWNLOAD_ROOT = REPO_ROOT / ".temp" / "datasheet_fetch" / "generated_samples"

TI_SYMLINK_PREFIX = "https://www.ti.com/lit/ds/symlink/"


# ============================================================
# データ構造
# ============================================================

@dataclass(frozen=True)
class Part:
    part_number: str
    category: str
    description: str
    description_jp: str
    rarity: str


@dataclass(frozen=True)
class OwnedRecord:
    part_number: str
    exact_items: list[str]


@dataclass(frozen=True)
class Pinout:
    pin_count: int
    pin_to_name: dict[int, str]
    extracted_from: str


# ============================================================
# カテゴリ固有回路設定
# ============================================================

def _get_category_config(category: str, part: "Part") -> dict:
    """カテゴリごとのデモ回路設定を返す。"""
    desc_lower = f"{part.description} {part.description_jp}".lower()

    # 共通のデフォルト設定
    default = {
        "circuit_title": "基本動作デモ（1回路）",
        "overview_extra": "スイッチ入力で動作を切り替え、LEDで出力を観測します。",
        "input_desc": (
            "- **入力ピン**: DIPスイッチまたはジャンパでH/Lを設定\n"
            "- **制御ピン（イネーブル等）**: 一次資料で確認の上、適切な論理レベルに固定"
        ),
        "output_desc": (
            "- **出力ピン**: LED＋330Ω〜1kΩ直列抵抗で観測"
        ),
        "parts_extra": "",
        "special_notes": "- 一次資料でピン機能と動作条件を確認の上、配線してください。",
        "needs_clock": False,
    }

    configs: dict[str, dict] = {
        "05_flipflops_latches": {
            "circuit_title": "フリップフロップ/ラッチ 基本動作デモ",
            "overview_extra": "クロック信号とデータ入力でフリップフロップの記憶動作を確認します。",
            "input_desc": (
                "- **CLK（クロック）**: タクトスイッチ（チャタリング対策として0.1µFをスイッチと並列に）\n"
                "- **データ入力（D / J / K / S / R等）**: DIPスイッチまたはジャンパでH/Lを設定\n"
                "- **非同期入力（/CLR, /PRE等）**: 通常動作中はVCCに接続（High固定）"
            ),
            "output_desc": (
                "- **Q, /Q**: LED＋330Ω〜1kΩ直列抵抗でH/L状態を表示"
            ),
            "parts_extra": (
                "| タクトスイッチ（クロック用） | チャタリング対策コンデンサ込み | 1 |\n"
                "| チャタリング対策コンデンサ | 0.1µF | 1 |"
            ),
            "special_notes": (
                "- **クロックエッジ**: ポジティブエッジかネガティブエッジかを一次資料で確認してください。\n"
                "- **非同期入力の優先順位**: /CLR・/PRE はクロックより優先されます。デモ中は適切な論理レベルに固定してください。\n"
                "- **未使用FF/ラッチ**: 未使用ユニットの入力はフローティング禁止。クロックはGND、データ入力は固定H/Lに接続。\n"
                "- **ラッチ（レベルトリガ）とFF（エッジトリガ）の違い**: 動作モードを一次資料で確認してください。"
            ),
            "needs_clock": True,
        },

        "06_encoders_decoders": {
            "circuit_title": "エンコーダ/デコーダ 基本動作デモ",
            "overview_extra": "DIPスイッチでアドレス/BCD入力を設定し、デコードされた出力をLEDで確認します。",
            "input_desc": (
                "- **アドレス/データ入力（A/B/C/D, DCBA等）**: DIPスイッチでH/Lを設定\n"
                "- **イネーブル入力（/E, G1, G2, /G2A, /G2B等）**: アクティブ方向（一次資料で確認）に合わせてVCC/GNDに接続\n"
                "  - アクティブLow（/E）→ GNDに接続（有効化）\n"
                "  - アクティブHigh（G1）→ VCCに接続（有効化）"
            ),
            "output_desc": (
                "- **出力（Y0〜Yn, /Y0〜/Yn）**: 各出力にLED＋330Ω〜1kΩ直列抵抗を接続\n"
                "  - **アクティブLow出力**: カソードをIC出力ピン、アノードを抵抗経由でVCCに（選択時に点灯）\n"
                "  - **アクティブHigh出力**: アノードを抵抗経由でIC出力ピン、カソードをGNDに"
            ),
            "parts_extra": (
                "| LED（デコード出力観測用） | 任意 | 出力数分（最大16本） |\n"
                "| LED直列抵抗 | 330Ω〜1kΩ | 出力数分 |"
            ),
            "special_notes": (
                "- **アクティブLow出力に注意**: 多くのデコーダはアクティブLow（選択時に出力Low）。LEDの接続方向を出力極性に合わせてください。\n"
                "- **イネーブルピンの極性**: 一次資料で/E（アクティブLow）かG（アクティブHigh）かを確認してください。\n"
                "- **7セグメント表示器対応**: 74x47/74x247等はLED 7セグに直結可能（各セグメントに電流制限抵抗1本必要）。\n"
                "- **BCD→10進デコーダ（74x42等）**: BCD入力（DCBA）が0〜9の範囲で対応出力がLow。10〜15は全出力High（無効）。"
            ),
            "needs_clock": False,
        },

        "07_data_selectors_mux_demux": {
            "circuit_title": "データセレクタ/MUX 基本動作デモ",
            "overview_extra": "セレクト入力で選択チャネルを指定し、対応するデータ入力が出力に伝わることを確認します。",
            "input_desc": (
                "- **セレクト入力（A/B/C等）**: DIPスイッチでH/Lを設定（選択チャネルを指定）\n"
                "- **データ入力（I0〜In, D0〜Dn等）**: 一部チャネルをVCC（H）、他をGND（L）に設定して差異を観測\n"
                "- **ストローブ/イネーブル（/G, /E等）**: GNDに接続（アクティブLow→有効化）"
            ),
            "output_desc": (
                "- **出力（Y, W等）**: LED＋330Ω〜1kΩ直列抵抗で選択されたデータを表示\n"
                "- **相補出力（Y, /Y）がある場合**: 両方にLEDを接続して対比確認"
            ),
            "parts_extra": "",
            "special_notes": (
                "- **動作確認手順**: セレクト入力でチャネルを順番に切り替え、対応するデータ入力が出力に反映されることを確認。\n"
                "- **イネーブルピン**: アクティブLowのストローブをHighにすると出力がLowまたはHi-Zになります。必ずGNDに接続。\n"
                "- **3-state出力**: /OE等で出力をHi-Zにできる場合、デモ中はGNDに接続して出力有効化。\n"
                "- **74x354/74x356（MUX+レジスタ）**: CLKピンも必要。タクトスイッチで手動クロックを入力。"
            ),
            "needs_clock": False,
        },

        "08_counters": {
            "circuit_title": "バイナリ/BCD カウンタ 基本動作デモ",
            "overview_extra": "タクトスイッチでクロックを手動入力し、カウンタのバイナリ出力をLEDで表示します。",
            "input_desc": (
                "- **CLK（クロック）**: タクトスイッチ（チャタリング対策: 0.1µFをスイッチと並列）\n"
                "- **クリア入力（/CLR, MR, R等）**: 通常カウント中はVCCに接続（非同期クリア禁止）\n"
                "- **イネーブル入力（CEP, CET, ENP, ENT等）**: VCCに接続（カウンタ有効化）\n"
                "- **ロード入力（/LOAD等）**: VCCに接続（ロード無効、カウントのみ）"
            ),
            "output_desc": (
                "- **Q0〜Q3（またはQA〜QD）**: 各ビットにLED＋330Ω〜1kΩ直列抵抗を接続（バイナリ表示）\n"
                "- **RCO/TC（桁上がり出力）**: LED＋抵抗でオーバーフロー確認（任意）"
            ),
            "parts_extra": (
                "| タクトスイッチ（クロック用） | チャタリング対策コンデンサ込み | 1 |\n"
                "| チャタリング対策コンデンサ | 0.1µF | 1 |\n"
                "| LED（ビット表示用） | 任意 | 4本（Q0〜Q3分） |"
            ),
            "special_notes": (
                "- **チャタリング対策必須**: タクトスイッチ直結ではチャタリングにより1押しで複数カウントされます。0.1µFを並列推奨。\n"
                "- **クロックエッジ**: ポジティブエッジかネガティブエッジかを一次資料で確認。\n"
                "- **非同期クリア**: /CLRをGNDに一時短絡してからVCCに戻すことでカウンタをリセットできます。\n"
                "- **BCD vs バイナリ**: BCDカウンタ（74x90等）は0〜9でカウント後に0に戻ります。バイナリカウンタ（74x93等）は0〜15（4bit）。\n"
                "- **桁上がり出力（RCO/TC）**: 多段接続時に使用。デモでは任意でLED接続して確認。"
            ),
            "needs_clock": True,
        },

        "09_registers": {
            "circuit_title": "レジスタ/シフトレジスタ 基本動作デモ",
            "overview_extra": "クロック信号とデータ入力でレジスタへのデータロードまたはシフト動作を確認します。",
            "input_desc": (
                "- **CLK（クロック）**: タクトスイッチ（チャタリング対策: 0.1µFを並列）\n"
                "- **直列データ入力（SIN, DSR, DS, SER等）**: DIPスイッチまたはジャンパ\n"
                "- **並列データ入力（P0〜P7, A〜H等）**: DIPスイッチで全ビット設定\n"
                "- **モード/イネーブル（S0/S1, /OE, /SH_LD等）**: 所望の動作モードに設定（一次資料で確認）\n"
                "- **クリア入力（/CLR, /MR等）**: VCCに接続（クリア禁止）"
            ),
            "output_desc": (
                "- **Q0〜Q7（またはQA〜QH）**: 各ビットにLED＋抵抗を接続（並列出力観測）\n"
                "- **直列出力（QH', SQH等）**: 存在する場合はLEDで確認（カスケード接続テスト用）"
            ),
            "parts_extra": (
                "| タクトスイッチ（クロック用） | チャタリング対策コンデンサ込み | 1 |\n"
                "| チャタリング対策コンデンサ | 0.1µF | 1 |\n"
                "| LED（出力ビット観測） | 任意 | 出力ビット数分（最大8本） |"
            ),
            "special_notes": (
                "- **74x164（8bit SIPO）**: SIN（A, B入力AND）にデータをセットしCLKを1パルスずつ入れてシフトを確認。\n"
                "- **74x165（8bit PISO）**: /SH_LD=Lでデータをロード後、/SH_LD=Hにしてクロックで直列出力（QH）から読み出し。\n"
                "- **74x595（8bit SIPO + ストレージレジスタ）**: SER→SRCLK→RCLKの順で操作してQ0〜Q7に反映。\n"
                "- **3-state出力（/OE付き）**: /OEをGNDに接続して出力有効化。\n"
                "- **バストランシーバ系（74x242, 74x245等）**: 方向制御ピン（DIR）とイネーブル（/OE）を正しく設定。"
            ),
            "needs_clock": True,
        },

        "10_arithmetic": {
            "circuit_title": "算術演算回路 基本動作デモ",
            "overview_extra": "DIPスイッチでA・B入力を設定し、演算結果をLEDで確認します。ALUは演算機能選択ピンも設定します。",
            "input_desc": (
                "- **A入力（A0〜A3等）**: DIPスイッチでH/Lを設定（4bitの場合、A0=LSB〜A3=MSB）\n"
                "- **B入力（B0〜B3等）**: DIPスイッチでH/Lを設定\n"
                "- **機能選択（S0〜S3等）**: ALUの場合はDIPスイッチで演算機能を選択（74x181: 16演算）\n"
                "- **モード選択（M等）**: H=論理演算 / L=算術演算（一次資料で確認）\n"
                "- **桁上げ入力（Cn, CI等）**: GNDに接続（Cn=0、桁上げなし）"
            ),
            "output_desc": (
                "- **結果出力（F0〜F3, S0〜S3等）**: 各ビットにLED＋抵抗を接続\n"
                "- **桁上がり出力（Cn+4, CO等）**: LED＋抵抗でオーバーフロー確認\n"
                "- **等値出力（A=B）**: LED＋抵抗で確認（ある場合）"
            ),
            "parts_extra": (
                "| LED（演算結果表示） | 任意 | 出力ビット数＋1（桁上がり分） |"
            ),
            "special_notes": (
                "- **74x181（4bit ALU）**: M=H, S=1111でA伝達、M=L, S=1001, Cn=Hで加算(A+B)。まず加算で基本動作確認後、他の演算機能を試してください。\n"
                "- **74x283（4bit全加算器）**: Cin=GND(0)でA+Bの結果（F0〜F3とCout）が出力。非常にシンプルな動作確認が可能。\n"
                "- **74x82（2bit全加算器）**: A1, A2, B1, B2, Cn入力 → Σ1, Σ2, Cn+2出力。3bit表示のシンプルなデモ。\n"
                "- **演算確認手順**: A=0001, B=0001 を設定して結果がF=0010（2）になることを確認するとわかりやすい。"
            ),
            "needs_clock": False,
        },

        "11_error_detection_correction": {
            "circuit_title": "パリティ生成・検出 基本動作デモ",
            "overview_extra": "DIPスイッチでデータビットを設定し、パリティビット出力をLEDで確認します。",
            "input_desc": (
                "- **データ入力（I0〜I8等）**: DIPスイッチでH/Lを設定（全ビット接続必須）\n"
                "- **パリティ種別入力（P等）**: ある場合は偶数/奇数パリティを選択"
            ),
            "output_desc": (
                "- **偶数パリティ出力（ΣE, EVEN等）**: LED＋抵抗で確認\n"
                "- **奇数パリティ出力（ΣO, ODD等）**: LED＋抵抗で確認"
            ),
            "parts_extra": "",
            "special_notes": (
                "- **74x280（9bit パリティ生成・検出器）**: I0〜I8（9本）のHの個数に応じてΣE/ΣOが変化。\n"
                "  - Hの個数が偶数 → ΣE=H（偶数パリティ）、ΣO=L\n"
                "  - Hの個数が奇数 → ΣE=L、ΣO=H（奇数パリティ）\n"
                "- **確認手順**: DIPスイッチでI0〜I8をすべてL→ΣE=H確認。I0をHに→ΣO=Hに変化。"
            ),
            "needs_clock": False,
        },

        "12_memory_storage": {
            "circuit_title": "メモリ/ストレージ 基本動作デモ",
            "overview_extra": "アドレス入力でメモリアドレスを指定し、書き込み・読み出し動作をLEDで確認します。",
            "input_desc": (
                "- **アドレス入力（A0〜An等）**: DIPスイッチでアドレスを設定\n"
                "- **データ入力（D0〜Dn等）**: DIPスイッチでデータビットを設定\n"
                "- **書き込み制御（/WE, W//R等）**: 書き込み時はアクティブLow→GNDに、読み出し時はVCCに\n"
                "- **チップセレクト（/CS, /CE等）**: アクティブLowの場合はGNDに接続（有効化）\n"
                "- **出力イネーブル（/OE, /G等）**: アクティブLowの場合はGNDに接続（出力有効化）"
            ),
            "output_desc": (
                "- **データ出力（Q0〜Qn等）**: 各ビットにLED＋抵抗を接続（読み出しデータ確認）"
            ),
            "parts_extra": "",
            "special_notes": (
                "- **書き込み→読み出し手順**:\n"
                "  1. アドレスとデータをDIPスイッチで設定\n"
                "  2. /WE=Lでパルス書き込み（タクトスイッチで一時的にGNDへ）\n"
                "  3. /WE=Hに戻す（書き込み完了）\n"
                "  4. アドレスを同じ値に維持→出力LEDで読み出しデータを確認\n"
                "- **74x170（4×4レジスタファイル）**: RA0/RA1でリード、WA0/WA1でライトアドレスを独立指定。/GE=Lでリード有効、/WE=Lでライト有効。\n"
                "- **74x189（16×4bit RAM）**: A0〜A3（アドレス）、D1〜D4（データ入力）、Q1〜Q4（データ出力は反転）。/CS=Lで選択。\n"
                "- **メモリ出力の反転**: 74x189等は出力が入力の反転（/Q）の場合があります。一次資料で確認。"
            ),
            "needs_clock": False,
        },

        "13_programmable_logic": {
            "circuit_title": "プログラマブルロジック 基本動作デモ",
            "overview_extra": "プログラマブルロジックICの基本動作を確認します。初期状態（未プログラム）の動作を確認します。",
            "input_desc": (
                "- **入力（I0〜In等）**: DIPスイッチでH/Lを設定\n"
                "- **双方向ピン**: 入力として使用する場合はDIPスイッチ接続"
            ),
            "output_desc": (
                "- **出力（O0〜On等）**: LED＋抵抗で出力ロジック状態を確認"
            ),
            "parts_extra": "",
            "special_notes": (
                "- このカテゴリのICは製品固有のプログラムロジックが実装されている場合があります。一次資料で初期/購入状態のロジックを確認してください。\n"
                "- プログラマブルICを使用する場合はプログラマ（ライタ）が必要な場合があります。"
            ),
            "needs_clock": False,
        },

        "14_system_controllers_timing": {
            "circuit_title": "カウンタ/タイミング制御 基本動作デモ",
            "overview_extra": "クロック信号でカウントし、各出力をLEDで確認します。プリセット機能があるICはDIPスイッチでデータをロードします。",
            "input_desc": (
                "- **CLK（クロック）**: タクトスイッチ（チャタリング対策: 0.1µFを並列）\n"
                "- **プリセット入力（P0〜P3, D0〜D3等）**: DIPスイッチでH/Lを設定（ロードデータ）\n"
                "- **ロード/クリア入力（/LOAD, /CLR, MR等）**: 通常カウント中はVCCに接続\n"
                "- **イネーブル（ENP, ENT, /CTEN, UP, DOWN等）**: 有効化方向に接続（一次資料で確認）"
            ),
            "output_desc": (
                "- **Q0〜Q3（またはQA〜QD）**: 各ビットにLED＋抵抗を接続（バイナリ表示）\n"
                "- **桁上がり/ボロー出力（RCO, TC, /CO, /BO等）**: LED＋抵抗で確認（任意）"
            ),
            "parts_extra": (
                "| タクトスイッチ（クロック用） | チャタリング対策コンデンサ込み | 1 |\n"
                "| チャタリング対策コンデンサ | 0.1µF | 1 |\n"
                "| LED（ビット表示） | 任意 | 4〜8本 |"
            ),
            "special_notes": (
                "- **チャタリング対策必須**: 0.1µFコンデンサをタクトスイッチと並列に接続。\n"
                "- **アップ/ダウンカウンタ（74x190/191/192/193）**: D/Uピン（またはU//D）でカウント方向を選択。H=UP/L=DOWN または逆（一次資料で確認）。\n"
                "- **同期プリセット（74x163等）**: /LOAD=Lにするとクロック立ち上がりでP0〜P3のデータをロード。/LOAD=VCCでカウント動作。\n"
                "- **非同期クリア（74x161等）**: /CLR=GNDで即座にリセット。/CLR=VCCでカウント動作。\n"
                "- **BCD/バイナリ切り替え（74x190/192等）**: BCDカウンタは0〜9でカウントして戻る。"
            ),
            "needs_clock": True,
        },

        "15_interfaces_links": {
            "circuit_title": "インターフェース/バストランシーバ 基本動作デモ",
            "overview_extra": "方向制御とイネーブルを設定し、バス方向切り替えまたはバッファ動作を確認します。",
            "input_desc": (
                "- **データ入力（A0〜A7等）**: DIPスイッチまたはジャンパ\n"
                "- **方向制御（DIR等）**: DIPスイッチでH/Lを設定（一次資料でH=A→B方向を確認）\n"
                "- **出力イネーブル（/OE, /G等）**: GNDに接続（出力有効化）"
            ),
            "output_desc": (
                "- **データ出力（B0〜B7等）**: LED＋抵抗で出力状態を確認"
            ),
            "parts_extra": "",
            "special_notes": (
                "- **バス競合防止**: デモでは1チップのみ使用し、バス競合を避けてください。\n"
                "- **3-state出力**: /OEをHighにすると全出力がHi-Z（LEDが消灯）。これはバス衝突ではありません。\n"
                "- **入出力双方向**: DIR切り替えでA→BおよびB→A両方向のデータ伝達を確認してください。"
            ),
            "needs_clock": False,
        },

        "16_analog_mixed_signal": {
            "circuit_title": "アナログ/混載IC 基本動作デモ",
            "overview_extra": "モノステーブルマルチバイブレータはトリガで出力パルスを生成します。RC素子でパルス幅を目視確認可能な時間に設定します。",
            "input_desc": (
                "- **トリガ入力（A, /B等）**: タクトスイッチ\n"
                "  - /B（アクティブLow）: 通常はVCCにプルアップし、タクトスイッチでGNDに落とす\n"
                "  - A（アクティブHigh）: GNDにプルダウンし、タクトスイッチでVCCに上げる\n"
                "- **RC タイミング素子**: 外付けRとCでパルス幅を設定\n"
                "  - **目安**: Tw ≈ 0.7 × R × C（一次資料の定式で確認）\n"
                "  - **推奨値（目視用）**: R=10kΩ, C=100µF → Tw ≈ 0.7秒"
            ),
            "output_desc": (
                "- **Q出力**: LED＋330Ω〜1kΩ直列抵抗で出力パルスを目視確認\n"
                "- **/Q出力**: 逆相パルス確認用（任意）"
            ),
            "parts_extra": (
                "| 外付け抵抗（Rext） | 10kΩ〜100kΩ（タイミング用） | 1 |\n"
                "| 外付けコンデンサ（Cext） | 100µF（目視用パルス幅確保） | 1 |\n"
                "| タクトスイッチ（トリガ用） | ― | 1 |"
            ),
            "special_notes": (
                "- **74x123/74x221/74x423（デュアル単安定MV）**: 外付けR・Cでパルス幅を設定。Tw ≈ 0.7×R×C（一次資料で確認）。\n"
                "  R=10kΩ, C=100µFでTw≈0.7秒（LEDで目視可能）。\n"
                "- **再トリガ動作**: 74x123は出力パルス中に再トリガ可能。74x221は通常非再トリガ。\n"
                "- **Cext接続**: セラミックコンデンサは高周波動作向き、電解コンデンサ（極性注意）は長い遅延向き。\n"
                "- **74x124（デュアルVCO）**: Cext/Rextを固定値にしてLED点滅で発振動作を確認。周波数は制御電圧で変化。\n"
                "- **74x521/74x682/74x688（コンパレータ）**: A入力とB入力をDIPスイッチで設定して等値/大小比較出力を確認。"
            ),
            "needs_clock": False,
        },

        "17_expanders": {
            "circuit_title": "ゲート拡張（エクスパンダ） 基本動作デモ",
            "overview_extra": "エクスパンダICはベースゲートICと組み合わせることで入力を拡張します。単体では動作しません。",
            "input_desc": (
                "- **入力（X0〜Xn等）**: DIPスイッチでH/Lを設定\n"
                "- **エクスパンダ接続ピン（X, X'等）**: 対応するベースゲートICのエクスパンダ端子に接続"
            ),
            "output_desc": (
                "- **出力**: ベースゲートICの出力端子にLED＋抵抗を接続（エクスパンダ側には出力端子なし）"
            ),
            "parts_extra": (
                "| 対応するベースゲートIC（例: 74x50, 74x53等） | エクスパンダ接続用 | 1 |"
            ),
            "special_notes": (
                "- **注意**: 74x60等のエクスパンダは単独では動作しません。74x50等のエキスパンダブルゲートICと組み合わせて使います。\n"
                "- **接続方法**: エクスパンダの出力ピン（X端子）をベースゲートの対応する入力端子（エキスパンダ端子）に接続。\n"
                "- 一次資料でベースゲートICとの組み合わせ方法を確認してください。"
            ),
            "needs_clock": False,
        },

        "18_carry_generators": {
            "circuit_title": "先見桁上げ生成（キャリー・ルックアヘッド） 基本動作デモ",
            "overview_extra": "74x181（ALU）と組み合わせて、高速桁上げ生成の動作を確認します。",
            "input_desc": (
                "- **桁上げ生成/伝搬入力（G0〜G3, P0〜P3等）**: 74x181の対応する出力ピンに接続\n"
                "- **キャリー入力（Cn等）**: GNDに接続（最初の桁のキャリーなし）"
            ),
            "output_desc": (
                "- **キャリー出力（Cn+4, Cn+8等）**: LED＋抵抗で桁上がりを確認\n"
                "- **グループ桁上げ出力（G̃, P̃等）**: 上位段のキャリー生成用（LED任意）"
            ),
            "parts_extra": (
                "| 74x181（4bit ALU） | 組み合わせ推奨 | 1〜4（ビット幅に応じて） |"
            ),
            "special_notes": (
                "- **74x182**: 4個の74x181（4bit ALU）を接続して最大16bit高速加算回路を構成できます。\n"
                "- **基本接続**: 74x181のP0〜P3/G0〜G3 → 74x182の対応入力ピン。74x182のCn+x → 次段74x181のCnに接続。\n"
                "- **単体確認が難しい**: まず74x181または74x283で基本加算デモを行い、その後74x182を追加して構成してください。\n"
                "- **重要**: 74x181とピン対応を一次資料で必ず確認してから接続してください。"
            ),
            "needs_clock": False,
        },

        "99_other": {
            "circuit_title": "基本動作デモ",
            "overview_extra": "ICの基本動作を最小構成で確認します。詳細は一次資料（データシート）を参照してください。",
            "input_desc": (
                "- **入力ピン**: DIPスイッチまたはジャンパでH/Lを設定\n"
                "- **制御ピン**: 一次資料で確認の上、適切な論理レベルに固定"
            ),
            "output_desc": (
                "- **出力ピン**: LED＋330Ω〜1kΩ直列抵抗で観測"
            ),
            "parts_extra": "",
            "special_notes": "- 一次資料でピン機能と動作条件を確認の上、配線してください。",
            "needs_clock": False,
        },
    }

    cfg = configs.get(category, configs["99_other"]).copy()

    # 特定のIC機能に基づく補足（descriptionで判別）
    if "monostable" in desc_lower or "単安定" in desc_lower:
        cfg = configs.get("16_analog_mixed_signal", default).copy()
    elif "comparator" in desc_lower or "magnitude" in desc_lower or "コンパレータ" in desc_lower:
        cfg["special_notes"] += (
            "\n- **マグニチュードコンパレータ**: A>B, A=B, A<B の3出力をそれぞれLEDで確認。"
        )

    return cfg


# ============================================================
# ユーティリティ
# ============================================================

def _safe_path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except Exception:
        return str(path)


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_text(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def _normalize_token(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", text or "").upper()


def _local_exact_variants(exact_part_number: str, *, max_strips: int = 6) -> list[str]:
    base = _normalize_token(exact_part_number)
    if not base:
        return []
    variants: list[str] = [base]
    cur = base
    strips = 0
    while strips < max_strips and cur and cur[-1].isalpha():
        cur = cur[:-1]
        strips += 1
        if cur and cur not in variants:
            variants.append(cur)
    return variants


def _build_local_pdf_index(root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not root.exists():
        return index
    for pattern in ("*.pdf", "*.PDF"):
        for pdf in root.rglob(pattern):
            if not pdf.is_file():
                continue
            for raw_token in re.split(r"[\s,]+", pdf.stem):
                token = _normalize_token(raw_token)
                if token:
                    index.setdefault(token, pdf)
    return index


def _iter_parts(overview_raw: Any) -> Iterable[Part]:
    if not isinstance(overview_raw, list):
        raise ValueError("overview JSON must be a list")
    for item in overview_raw:
        if not isinstance(item, dict):
            continue
        pn = str(item.get("PartNumber", "")).strip()
        if not pn:
            continue
        category = str(item.get("Category", "99_other")).strip() or "99_other"
        yield Part(
            part_number=pn,
            category=category,
            description=str(item.get("Description", "")).strip(),
            description_jp=str(item.get("Description_JP", "")).strip(),
            rarity=str(item.get("Rarity", "")).strip(),
        )


def _load_owned_records(history_raw: Any) -> dict[str, OwnedRecord]:
    if not isinstance(history_raw, list):
        raise ValueError("history JSON must be a list")
    owned: dict[str, OwnedRecord] = {}
    for item in history_raw:
        if not isinstance(item, dict):
            continue
        pn = str(item.get("PartNumber", "")).strip()
        if not pn:
            continue
        exact_items: list[str] = []
        for key in ("GottenItemsMN_CMOS", "GottenItemsMN_TTL", "GottenItemsMN_Other"):
            value = item.get(key, [])
            if isinstance(value, list):
                exact_items += [str(x).strip() for x in value if str(x).strip()]
        if exact_items:
            # 重複除去（同一型番が複数エントリにある場合はマージ）
            if pn in owned:
                merged = list(dict.fromkeys(owned[pn].exact_items + exact_items))
                owned[pn] = OwnedRecord(part_number=pn, exact_items=merged)
            else:
                owned[pn] = OwnedRecord(part_number=pn, exact_items=exact_items)
    return owned


def _is_open_collector(part: Part) -> bool:
    text = f"{part.description} {part.description_jp}".lower()
    return "open-collector" in text or "オープンコレクタ" in text


def _is_tristate(part: Part) -> bool:
    text = f"{part.description} {part.description_jp}".lower()
    return "3-state" in text or "three-state" in text or "tri-state" in text or "トライステート" in text


def _pick_preferred_exact_item(owned: OwnedRecord) -> str:
    """TI SN74*を優先、次いで最初のアイテムを返す。"""
    for x in owned.exact_items:
        if _normalize_token(x).startswith("SN74"):
            return x
    return owned.exact_items[0]


def _ti_symlink_candidates_from_exact(exact_part_number: str, *, max_strips: int = 6) -> list[str]:
    token = _normalize_token(exact_part_number)
    if not token.startswith("SN"):
        return []
    stem = token.lower()
    candidates: list[str] = []

    def add(st: str) -> None:
        url = f"{TI_SYMLINK_PREFIX}{st}.pdf"
        if url not in candidates:
            candidates.append(url)

    add(stem)
    cur = stem
    strips = 0
    while strips < max_strips and cur and cur[-1].isalpha():
        cur = cur[:-1]
        strips += 1
        add(cur)
    return candidates


def _probe_url_pdf(url: str, *, timeout_s: float) -> bool:
    try:
        req = urllib.request.Request(
            url,
            method="GET",
            headers={"User-Agent": "7400SeriesCollection/1.0", "Range": "bytes=0-4"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            ct = (resp.headers.get("Content-Type", "") or "").lower()
            data = resp.read(5)
            if ct and ("pdf" not in ct) and ("octet-stream" not in ct):
                return False
            return data.startswith(b"%PDF")
    except Exception:
        return False


def _download_pdf(url: str, dest: Path, *, timeout_s: float, sleep_s: float) -> tuple[int, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        sha256 = hashlib.sha256(dest.read_bytes()).hexdigest()
        return dest.stat().st_size, sha256
    req = urllib.request.Request(url, headers={"User-Agent": "7400SeriesCollection/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = resp.read()
        dest.write_bytes(data)
    if sleep_s > 0:
        time.sleep(sleep_s)
    sha256 = hashlib.sha256(dest.read_bytes()).hexdigest()
    return dest.stat().st_size, sha256


def _find_or_fetch_pdf(
    exact_part_number: str,
    local_pdf_index: dict[str, Path],
    *,
    download: bool,
    timeout_s: float,
    sleep_s: float,
) -> tuple[Optional[Path], str, Optional[str], Optional[str]]:
    """(pdf_path, source_label, url_used, sha256) を返す。"""
    token = _normalize_token(exact_part_number)

    def try_local() -> tuple[Optional[Path], str, Optional[str], Optional[str]]:
        for v in _local_exact_variants(exact_part_number):
            hit = local_pdf_index.get(v)
            if hit is not None and hit.exists():
                sha256_local = hashlib.sha256(hit.read_bytes()).hexdigest()
                return hit, f"local:{_safe_path_label(hit)}", None, sha256_local
        return None, "no-local", None, None

    def try_ti_download() -> tuple[Optional[Path], str, Optional[str], Optional[str]]:
        dest = DOWNLOAD_ROOT / "TI" / f"{token}.pdf"
        sidecar_url = dest.with_suffix(dest.suffix + ".url.txt")

        if dest.exists():
            sha256_dl = hashlib.sha256(dest.read_bytes()).hexdigest()
            if sidecar_url.exists():
                url_used = sidecar_url.read_text(encoding="utf-8").strip() or None
                return dest, f"downloaded:{_safe_path_label(dest)}", url_used, sha256_dl
            url_used = None
            if download:
                for url in _ti_symlink_candidates_from_exact(exact_part_number):
                    if _probe_url_pdf(url, timeout_s=timeout_s):
                        url_used = url
                        sidecar_url.write_text(url_used, encoding="utf-8", newline="\n")
                        break
            return dest, f"downloaded:{_safe_path_label(dest)}", url_used, sha256_dl

        candidates = _ti_symlink_candidates_from_exact(exact_part_number)
        url_used = None
        for url in candidates:
            if _probe_url_pdf(url, timeout_s=timeout_s):
                url_used = url
                break
        if not url_used:
            return None, "no-ti-url", None, None
        if not download:
            return None, "url-only", url_used, None
        size, sha256_dl = _download_pdf(url_used, dest, timeout_s=timeout_s, sleep_s=sleep_s)
        _ = size
        sidecar_url.write_text(url_used, encoding="utf-8", newline="\n")
        return dest, f"downloaded:{_safe_path_label(dest)}", url_used, sha256_dl

    # SN74* はTIダウンロードを優先
    if token.startswith("SN"):
        pdf_path, label, url_used, sha256_val = try_ti_download()
        if pdf_path is not None or url_used is not None:
            return pdf_path, label, url_used, sha256_val
        return try_local()

    # 非TIはローカルを優先
    local_path, local_label, local_url, local_sha = try_local()
    if local_path is not None:
        return local_path, local_label, local_url, local_sha

    # 最終手段: TI tryダウンロード
    return try_ti_download()


# ============================================================
# ピン情報抽出
# ============================================================

def _extract_pinout_from_pdf(pdf_path: Path) -> Optional[Pinout]:
    """PDFからピン配置情報を抽出する（保守的）。"""
    if not _PYPDF_AVAILABLE or PdfReader is None:
        return None

    try:
        reader = PdfReader(str(pdf_path))
    except Exception:
        return None

    def parse_pin_functions_table(text: str) -> Optional[dict[int, str]]:
        tokens = text.split()

        start_idx = None
        for i in range(len(tokens) - 2):
            if tokens[i].lower() == "pin" and tokens[i + 1].lower().startswith("function"):
                start_idx = i
                break
            if tokens[i].lower() == "pin" and tokens[i + 1].lower() == "functions":
                start_idx = i
                break

        if start_idx is None:
            for i in range(len(tokens) - 4):
                if tokens[i].lower().startswith("table") and tokens[i + 1].lower().startswith("pin"):
                    start_idx = i
                    break

        if start_idx is None:
            for i in range(len(tokens) - 1):
                if tokens[i].lower() in {"no.", "no"} and tokens[i + 1].lower() == "name":
                    start_idx = i
                    break

        if start_idx is None:
            return None

        mapping: dict[int, str] = {}

        def normalize_name(raw: str) -> str:
            s = (raw or "").strip().strip(",;:.")
            s = re.sub(r"\(\d+\)$", "", s)
            return s

        stop_words = {"pin", "pins", "pin(s)", "no.", "no", "name", "i/o", "io", "description"}

        def is_pin_name(tok: str) -> bool:
            name = normalize_name(tok)
            if not name:
                return False
            lower = name.lower()
            if lower in stop_words:
                return False
            upper = name.upper()
            if upper in {"NC", "GND", "VCC", "VDD", "VSS"}:
                return True
            if name.isalpha() and name.islower():
                return False
            if not re.fullmatch(r"[0-9A-Za-z/_-]+", name):
                return False
            if not re.search(r"[A-Za-z]", name):
                return False
            if name.isalpha() and not name.isupper():
                return False
            return True

        table_style_pin_first = False
        for i in range(start_idx, min(start_idx + 60, len(tokens) - 1)):
            if tokens[i].lower() in {"no.", "no"} and tokens[i + 1].lower() == "name":
                table_style_pin_first = True
                break

        for i in range(start_idx, len(tokens) - 1):
            t0 = tokens[i]
            t1 = tokens[i + 1]

            if table_style_pin_first:
                if t0.isdigit():
                    pin = int(t0)
                    if 0 < pin <= 64:
                        if is_pin_name(t1):
                            mapping.setdefault(pin, normalize_name(t1))
                            continue
                        if i + 2 < len(tokens):
                            t2 = tokens[i + 2]
                            if t1.isdigit() and is_pin_name(t2):
                                mapping.setdefault(pin, normalize_name(t1 + normalize_name(t2)))
                continue

            if is_pin_name(t0) and t1.isdigit():
                pin = int(t1)
                if 0 < pin <= 64:
                    mapping.setdefault(pin, normalize_name(t0))
                continue

            if t0.isdigit() and is_pin_name(t1):
                pin = int(t0)
                if 0 < pin <= 64:
                    mapping.setdefault(pin, normalize_name(t1))
                continue

        if len(mapping) < 8:
            return None
        values = {v.upper() for v in mapping.values()}
        if not ("GND" in values or "VSS" in values):
            return None
        if not ("VCC" in values or "VDD" in values):
            return None
        return mapping

    max_pages = min(12, len(reader.pages))
    for page_index in range(max_pages):
        text = reader.pages[page_index].extract_text() or ""
        if not text:
            continue
        if "Pin" not in text or "Function" not in text:
            continue
        pin_to_name = parse_pin_functions_table(text)
        if pin_to_name is None:
            continue
        pin_count = max(pin_to_name.keys())
        return Pinout(
            pin_count=pin_count,
            pin_to_name=dict(sorted(pin_to_name.items(), key=lambda kv: kv[0])),
            extracted_from=_safe_path_label(pdf_path),
        )
    return None


def _format_pin_table(pinout: Pinout) -> str:
    lines = ["| Pin | Name |", "|---:|---|"]
    for pin in sorted(pinout.pin_to_name.keys()):
        lines.append(f"| {pin} | {pinout.pin_to_name[pin]} |")
    return "\n".join(lines)


# ============================================================
# Markdownレンダリング
# ============================================================

def _render_sample_md(
    part: Part,
    *,
    exact: str,
    pinout: Optional[Pinout],
    url_used: Optional[str],
    sha256: Optional[str],
    cat_cfg: dict,
) -> str:
    oc = _is_open_collector(part)
    ts = _is_tristate(part)
    today = date.today().isoformat()

    circuit_title = cat_cfg.get("circuit_title", "基本動作デモ（1回路）")
    overview_extra = cat_cfg.get("overview_extra", "")
    input_desc = cat_cfg.get("input_desc", "- **入力ピン**: DIPスイッチでH/Lを設定")
    output_desc = cat_cfg.get("output_desc", "- **出力ピン**: LED＋抵抗で観測")
    parts_extra = cat_cfg.get("parts_extra", "")
    special_notes_base = cat_cfg.get("special_notes", "- 一次資料で確認してください。")
    needs_clock = cat_cfg.get("needs_clock", False)

    # ピン配置セクション
    if pinout is None:
        pin_section = (
            "## ピン配置（要一次資料確認）\n\n"
            "このパーツは現時点で**自動抽出によるピン配置確定ができませんでした**。\n"
            "実配線に入る前に、対象の実型番・パッケージを確定し、"
            "データシートの Pin configuration / Pin functions 表を参照して追記してください。\n"
        )
    else:
        pin_section = (
            "## ピン配置（データシートより抽出）\n\n"
            f"対象の実型番 `{exact}` のデータシートPDFから、ピン名/番号を機械抽出しました"
            f"（抽出元: `{pinout.extracted_from}`）。\n\n"
            + _format_pin_table(pinout)
            + "\n"
        )

    # 特記事項の組み立て
    extra_notes: list[str] = []
    if oc:
        extra_notes.append(
            "- **オープンコレクタ出力**: 出力にプルアップ抵抗が必要です（抵抗値・許容電流は一次資料で確認）。"
        )
    if ts:
        extra_notes.append(
            "- **3-state出力**: /OE等の制御ピンを必ず定義してバス衝突を避けてください。"
        )
    if needs_clock:
        extra_notes.append(
            "- **クロックのチャタリング対策**: 0.1µFセラミックコンデンサをタクトスイッチと並列に接続してください。"
        )

    all_notes = special_notes_base
    if extra_notes:
        all_notes += "\n" + "\n".join(extra_notes)

    # 部品リスト追加行
    parts_extra_md = ""
    if parts_extra:
        parts_extra_md = "\n" + parts_extra

    # 一次資料セクション
    src_lines: list[str] = [f"- **実型番**: `{exact}`"]
    if url_used:
        src_lines.append(f"- **データシートURL**: {url_used}")
    if sha256:
        src_lines.append(f"- **PDF sha256（ローカル）**: `{sha256}`")
    src_md = "\n".join(src_lines)

    return f"""# {part.part_number} {circuit_title}

> この資料はサンプル回路の解説です。**電気特性・最大定格・入力閾値などは必ず一次資料（データシート）で確認**してください。

## 回路概要

所持している `{part.part_number}` 系ICのうち、`{exact}`（DIP想定）を使って、最小構成で基本動作を確認する回路です。

{overview_extra}

## 回路の仕様

- **電源**: +5V（ロジックファミリにより範囲が異なるため一次資料で確認）
- **入力**: 手動（DIPスイッチ/タクトスイッチ）
- **出力**: LED表示（電流制限抵抗を必ず直列に接続）

## 必要部品リスト

### 汎用ロジックIC

| 汎用型番 | 個数 | 所持品型番（例） |
|---|---:|---|
| {part.part_number} | 1 | `{exact}` |

### 受動部品

| 部品 | 目安 | 個数 |
|---|---:|---:|
| LED | 任意 | 1〜（出力数分） |
| LED直列抵抗 | 330Ω〜1kΩ | 1〜（LED数分） |
| 入力プルアップ/プルダウン | 10kΩ | 入力数分 |
| デカップリングコンデンサ | 0.1µF | 1（IC直近） |{parts_extra_md}

{pin_section}

## 接続方法

### 入力

{input_desc}

### 出力

{output_desc}

## 配線の要点

- **電源（VCC/GND）**: ピン表で確認した電源ピンに接続。0.1µFのデカップリングコンデンサをIC VCC〜GND間の直近（できれば5mm以内）に配置。
- **入力のフローティング禁止**: 未使用入力は必ずVCCまたはGNDに接続。CMOS系（74HC等）は特に重要（誤動作・貫通電流の原因）。
- **出力電流**: LED駆動電流（目安8〜10mA）が出力定格以内であることを一次資料で確認。

### 注意事項

{all_notes}

## 一次資料（データシート）

{src_md}

---

生成日時: {today}
"""


# ============================================================
# メイン処理
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="全カテゴリの入手済みIC向けに最小デモ回路資料を生成します",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--force", action="store_true", help="既存の01_basic_function_demo.mdを上書き")
    parser.add_argument("--download", action="store_true", help="TI symlink PDFをダウンロードしてピン抽出")
    parser.add_argument(
        "--part", action="append", default=[],
        help="特定の汎用型番のみ処理（例: --part 74x74、複数回指定可）",
    )
    parser.add_argument(
        "--category", metavar="CATEGORY",
        help="特定カテゴリのみ処理（例: --category 05_flipflops_latches）",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--sleep", type=float, default=0.5)
    parser.add_argument("--dry-run", action="store_true", help="ファイルを書かずに対象一覧を表示")
    args = parser.parse_args()

    if not _PYPDF_AVAILABLE:
        print("[WARN] pypdf が見つかりません。ピン抽出なしでスタブを生成します。")
        print("       インストール: .venv/Scripts/pip install pypdf")

    overview_raw = _read_json(OVERVIEW_JSON_PATH)
    history_raw = _read_json(HISTORY_JSON_PATH)

    all_parts = {p.part_number: p for p in _iter_parts(overview_raw)}
    owned = _load_owned_records(history_raw)

    # 対象フィルタリング
    target_pns = sorted(pn for pn in owned if pn in all_parts)

    if args.part:
        requested = {str(x).strip() for x in args.part if str(x).strip()}
        target_pns = [pn for pn in target_pns if pn in requested]

    if args.category:
        target_pns = [pn for pn in target_pns if all_parts[pn].category == args.category]

    local_pdf_index = _build_local_pdf_index(LOCAL_PDF_ROOT)

    written = 0
    skipped = 0
    stubbed = 0
    errors = 0

    print(f"=== generate_usage_samples_all_categories ===")
    print(f"対象: {len(target_pns)} 件" + (" [dry-run]" if args.dry_run else ""))
    print()

    for pn in target_pns:
        part = all_parts[pn]
        owned_rec = owned[pn]
        exact = _pick_preferred_exact_item(owned_rec)
        cat_cfg = _get_category_config(part.category, part)

        out_path = USAGE_DIR / part.category / part.part_number / "01_basic_function_demo.md"

        if args.dry_run:
            status = "既存" if out_path.exists() else "新規"
            print(f"  [{status}] {part.category}/{pn} ({exact})")
            continue

        try:
            pdf_path, _label, url_used, sha256 = _find_or_fetch_pdf(
                exact,
                local_pdf_index,
                download=args.download,
                timeout_s=args.timeout,
                sleep_s=args.sleep,
            )
        except Exception as e:
            print(f"  [ERROR] {pn}: PDF検索失敗 — {e}")
            pdf_path, url_used, sha256 = None, None, None
            errors += 1

        pinout: Optional[Pinout] = None
        if pdf_path is not None and pdf_path.exists():
            try:
                pinout = _extract_pinout_from_pdf(pdf_path)
            except Exception as e:
                print(f"  [WARN] {pn}: ピン抽出失敗 — {e}")

        if pinout is None:
            stubbed += 1

        content = _render_sample_md(
            part,
            exact=exact,
            pinout=pinout,
            url_used=url_used,
            sha256=sha256,
            cat_cfg=cat_cfg,
        )

        if _write_text(out_path, content, force=args.force):
            written += 1
            pin_tag = f"ピン{pinout.pin_count}本抽出" if pinout else "ピン未抽出(スタブ)"
            print(f"  [書込] {part.category}/{pn} - {pin_tag}")
        else:
            skipped += 1

    print()
    print(f"=== 完了 ===")
    print(f"  書込:           {written} 件")
    print(f"  スキップ(既存): {skipped} 件")
    print(f"  スタブ(ピンなし): {stubbed} 件")
    print(f"  エラー:         {errors} 件")
    print(f"  --download: {args.download}")
    if not args.download:
        print()
        print("  TI SN74* パーツのPDFをダウンロードするには --download を付けて再実行してください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
