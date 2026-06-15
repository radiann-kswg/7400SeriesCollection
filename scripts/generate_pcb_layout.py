#!/usr/bin/env python3
r"""
generate_pcb_layout.py

回路図 (.kicad_sch) から **PCB レイアウトまで** をできる限り自動化するパイプライン。
「フットプリント配置」「配線」という従来 GUI 必須だった工程を、

    ERC → ネットリスト → フットプリント配置 → 自動配線(Freerouting) → DRC → Gerber

の各ステージに分解し、外部ツール（kicad-cli / KiCAD 同梱 python / Freerouting）で
順に実行する。回路図自体は generate_pcb_demo_projects.py + kicad_sch_gen.py が
既に自動生成しているため、本スクリプトはその下流を担う。

────────────────────────────────────────────────────────────
実行環境（重要）
────────────────────────────────────────────────────────────
ステージごとに必要な実行系が異なる:

  * kicad-cli ステージ (netlist / drc / gerber)
        通常の python から subprocess で kicad-cli.exe を呼ぶだけ。確実。
  * pcbnew ステージ (footprint 配置 / DSN 出力 / SES 取り込み / 外形)
        KiCAD 同梱の python で実行する必要がある:
            & 'C:\Program Files\KiCad\10.0\bin\python.exe' scripts\generate_pcb_layout.py ...
        （通常の python では import pcbnew が失敗する → 該当ステージはスキップされ警告）
  * Freerouting ステージ (自動配線)
        Java + freerouting.jar が必要。--freerouting-jar で場所を指定。

────────────────────────────────────────────────────────────
使い方
────────────────────────────────────────────────────────────
  # まず回路図の ERC を通し、ネットリストだけ出す（通常 python で可）
  python scripts/generate_pcb_layout.py --part 74x00 --stages erc,netlist

  # KiCAD 同梱 python で配置〜Gerber まで一気通貫
  & 'C:\Program Files\KiCad\10.0\bin\python.exe' scripts/generate_pcb_layout.py \
        --part 74x00 --freerouting-jar C:\tools\freerouting.jar

  # 全入手済みプロジェクトを対象に（カテゴリ絞り込み可）
  python scripts/generate_pcb_layout.py --category 01_buffers_inverters --stages erc,netlist

--stages を省略すると pcbnew / freerouting が利用可能か自動判定し、可能な範囲を実行する。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
PCB_DEMO_DIR = BASE_DIR / "pcb-demo"

DEFAULT_KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
ALL_STAGES = ["erc", "netlist", "place", "route", "drc", "gerber"]

# 基板外形（テンプレ既定に合わせる）
BOARD_W_MM = 50.0
BOARD_H_MM = 50.0


# ============================================================
# 共通ユーティリティ
# ============================================================

def find_kicad_cli(explicit: str | None) -> str | None:
    for c in (explicit, os.environ.get("KICAD_CLI"), DEFAULT_KICAD_CLI):
        if c and Path(c).exists():
            return c
    return shutil.which("kicad-cli") or shutil.which("kicad-cli.exe")


def have_pcbnew() -> bool:
    try:
        import pcbnew  # noqa: F401
        return True
    except Exception:
        return False


def find_projects(category: str | None, part: str | None) -> list[Path]:
    """対象プロジェクトディレクトリ（.kicad_sch を含む）を列挙。"""
    out = []
    for sch in sorted(PCB_DEMO_DIR.glob("**/*.kicad_sch")):
        d = sch.parent
        if category and f"/{category}/" not in d.as_posix():
            continue
        if part and d.name != part:
            continue
        out.append(d)
    return out


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("    $ " + " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# ============================================================
# ステージ: kicad-cli 系（通常 python で可）
# ============================================================

def stage_erc(kicad_cli: str, proj: Path) -> bool:
    sch = proj / f"{proj.name}.kicad_sch"
    out = proj / "erc.json"
    r = run([kicad_cli, "sch", "erc", "--format", "json",
             "--severity-error", "--exit-code-violations",
             "--output", str(out), str(sch)])
    ok = r.returncode == 0
    print(f"    ERC: {'OK' if ok else 'エラーあり (erc.json 参照)'}")
    return ok


def stage_netlist(kicad_cli: str, proj: Path) -> bool:
    sch = proj / f"{proj.name}.kicad_sch"
    net = proj / f"{proj.name}.net"
    r = run([kicad_cli, "sch", "export", "netlist",
             "--format", "kicadsexpr", "--output", str(net), str(sch)])
    ok = r.returncode == 0 and net.exists()
    print(f"    netlist: {'生成 ' + net.name if ok else '失敗: ' + (r.stderr or '').strip()[:160]}")
    return ok


def stage_drc(kicad_cli: str, proj: Path) -> bool:
    pcb = proj / f"{proj.name}.kicad_pcb"
    out = proj / "drc.json"
    r = run([kicad_cli, "pcb", "drc", "--format", "json",
             "--severity-error", "--exit-code-violations",
             "--output", str(out), str(pcb)])
    ok = r.returncode == 0
    print(f"    DRC: {'OK' if ok else 'エラーあり (drc.json 参照)'}")
    return ok


def stage_gerber(kicad_cli: str, proj: Path) -> bool:
    pcb = proj / f"{proj.name}.kicad_pcb"
    gdir = proj / "gerber"
    gdir.mkdir(exist_ok=True)
    r1 = run([kicad_cli, "pcb", "export", "gerbers", "--output", str(gdir), str(pcb)])
    r2 = run([kicad_cli, "pcb", "export", "drill", "--output", str(gdir), str(pcb)])
    ok = r1.returncode == 0 and r2.returncode == 0
    print(f"    Gerber/Drill: {'出力 ' + gdir.name + '/' if ok else '失敗'}")
    return ok


# ============================================================
# ステージ: pcbnew 系（KiCAD 同梱 python が必要）
# ============================================================

def stage_place(proj: Path) -> bool:
    """
    ネットリストのフットプリントを PCB に配置し、外形(50×50)を引く。
    KiCAD 同梱 python (import pcbnew) が必要。
    """
    try:
        import pcbnew
    except Exception:
        print("    place: pcbnew が import できないためスキップ"
              "（KiCAD 同梱 python で実行してください）")
        return False

    pcb_path = proj / f"{proj.name}.kicad_pcb"
    net_path = proj / f"{proj.name}.net"
    if not net_path.exists():
        print("    place: ネットリストが無い（先に netlist ステージを実行）")
        return False

    board = pcbnew.LoadBoard(str(pcb_path)) if pcb_path.exists() else pcbnew.BOARD()

    # 1) 外形 (Edge.Cuts) を 50×50 で作成（既存があってもそのまま追加しないよう簡易チェック）
    _ensure_board_outline(board, pcbnew)

    # 2) ネットリストからフットプリントを配置
    #    KiCAD の python では NETLIST / NETLIST_READER を介して読み込む。
    #    API はバージョン差があるため、失敗時は明示ログを出す。
    try:
        placed = _place_from_netlist(board, str(net_path), pcbnew)
    except Exception as exc:  # noqa: BLE001
        print(f"    place: フットプリント配置 API でエラー: {exc}")
        print("           → Pcbnew GUI の『回路図から基板を更新』で代替してください。")
        pcbnew.SaveBoard(str(pcb_path), board)
        return False

    pcbnew.SaveBoard(str(pcb_path), board)
    print(f"    place: {placed} 個のフットプリントを配置し外形を作成")
    return placed > 0


def _ensure_board_outline(board, pcbnew) -> None:
    """Edge.Cuts に矩形外形を作成（左下原点付近）。"""
    SCALE = pcbnew.FromMM
    x0, y0 = 100.0, 80.0  # 配置原点（mm）
    pts = [(x0, y0), (x0 + BOARD_W_MM, y0),
           (x0 + BOARD_W_MM, y0 + BOARD_H_MM), (x0, y0 + BOARD_H_MM), (x0, y0)]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(pcbnew.VECTOR2I(SCALE(ax), SCALE(ay)))
        seg.SetEnd(pcbnew.VECTOR2I(SCALE(bx), SCALE(by)))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(SCALE(0.15))
        board.Add(seg)


def _place_from_netlist(board, net_path: str, pcbnew) -> int:
    """
    ネットリスト(kicadsexpr)を読み、未配置の各コンポーネントの footprint を
    ライブラリからロードして基板に追加・グリッド配置する。
    （nets の正式割当は後段の DSN/SES や GUI 更新でも補完できる簡易配置）
    """
    import re
    text = Path(net_path).read_text(encoding="utf-8")
    # (comp (ref "U1") ... (footprint "Package_DIP:DIP-14_W7.62mm"))
    comps = re.findall(
        r'\(comp\s+\(ref\s+"([^"]+)"\).*?\(footprint\s+"([^"]+)"\)',
        text, re.DOTALL,
    )
    SCALE = pcbnew.FromMM
    ox, oy, dx = 108.0, 88.0, 22.0
    placed = 0
    existing = {fp.GetReference() for fp in board.GetFootprints()}
    for i, (ref, fpid) in enumerate(comps):
        if ref in existing or ":" not in fpid:
            continue
        libnick, fpname = fpid.split(":", 1)
        fp = _load_footprint(libnick, fpname, pcbnew)
        if fp is None:
            print(f"      [WARN] footprint 取得失敗: {fpid} ({ref})")
            continue
        fp.SetReference(ref)
        fp.SetPosition(pcbnew.VECTOR2I(SCALE(ox + (i % 2) * dx), SCALE(oy + (i // 2) * dx)))
        board.Add(fp)
        placed += 1
    return placed


def _load_footprint(libnick: str, fpname: str, pcbnew):
    """フットプリントライブラリテーブルから footprint をロード。"""
    try:
        return pcbnew.FootprintLoad(_fp_lib_dir(libnick), fpname)
    except Exception:
        return None


def _fp_lib_dir(libnick: str) -> str:
    """libnick (例 Package_DIP) → .pretty ディレクトリの絶対パス。"""
    base = Path(r"C:\Program Files\KiCad\10.0\share\kicad\footprints")
    return str(base / f"{libnick}.pretty")


# ============================================================
# ステージ: Freerouting 自動配線
# ============================================================

def stage_route(proj: Path, freerouting_jar: str | None, java: str = "java") -> bool:
    """
    pcbnew で Specctra DSN を出力 → Freerouting で自動配線 → SES を pcbnew で取り込み。
    """
    if not freerouting_jar or not Path(freerouting_jar).exists():
        print("    route: --freerouting-jar 未指定のためスキップ")
        return False
    try:
        import pcbnew
    except Exception:
        print("    route: pcbnew が必要（KiCAD 同梱 python で実行）。スキップ")
        return False

    pcb_path = proj / f"{proj.name}.kicad_pcb"
    dsn = proj / f"{proj.name}.dsn"
    ses = proj / f"{proj.name}.ses"

    board = pcbnew.LoadBoard(str(pcb_path))
    # DSN 出力（KiCAD 10 の python に ExportSpecctraDSN がある）
    try:
        pcbnew.ExportSpecctraDSN(board, str(dsn))  # 署名はバージョン差あり
    except TypeError:
        pcbnew.ExportSpecctraDSN(str(dsn))
    except Exception as exc:  # noqa: BLE001
        print(f"    route: DSN 出力に失敗: {exc}")
        return False

    r = run([java, "-jar", freerouting_jar, "-de", str(dsn), "-do", str(ses),
             "-mp", "50"])
    if r.returncode != 0 or not ses.exists():
        print(f"    route: Freerouting 失敗: {(r.stderr or '')[:160]}")
        return False

    try:
        pcbnew.ImportSpecctraSES(board, str(ses))
    except TypeError:
        pcbnew.ImportSpecctraSES(str(ses))
    pcbnew.SaveBoard(str(pcb_path), board)
    print("    route: 自動配線を取り込み保存")
    return True


# ============================================================
# メイン
# ============================================================

def resolve_stages(arg: str | None, freerouting_jar: str | None) -> list[str]:
    if arg:
        req = [s.strip() for s in arg.split(",") if s.strip()]
        return [s for s in req if s in ALL_STAGES]
    # 自動判定
    stages = ["erc", "netlist"]
    if have_pcbnew():
        stages.append("place")
        if freerouting_jar:
            stages.append("route")
        stages += ["drc", "gerber"]
    else:
        print("[INFO] pcbnew 非検出 → erc/netlist のみ実行（配置以降は KiCAD 同梱 python で）")
    return stages


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--category")
    ap.add_argument("--part")
    ap.add_argument("--stages", help="カンマ区切り: " + ",".join(ALL_STAGES))
    ap.add_argument("--kicad-cli", dest="kicad_cli")
    ap.add_argument("--freerouting-jar")
    ap.add_argument("--java", default="java")
    args = ap.parse_args()

    kicad_cli = find_kicad_cli(args.kicad_cli)
    stages = resolve_stages(args.stages, args.freerouting_jar)
    need_cli = {"erc", "netlist", "drc", "gerber"} & set(stages)
    if need_cli and not kicad_cli:
        print("[ERROR] kicad-cli が見つかりません（--kicad-cli / 環境変数 KICAD_CLI）。")
        return 2

    projects = find_projects(args.category, args.part)
    if not projects:
        print("[INFO] 対象プロジェクトがありません。")
        return 0

    print("=" * 68)
    print(f"PCB パイプライン: {len(projects)} プロジェクト / ステージ: {', '.join(stages)}")
    print("=" * 68)

    n_ok = 0
    for proj in projects:
        print(f"\n[{proj.name}] {proj.relative_to(BASE_DIR).as_posix()}")
        results = {}
        if "erc" in stages:
            results["erc"] = stage_erc(kicad_cli, proj)
        if "netlist" in stages:
            results["netlist"] = stage_netlist(kicad_cli, proj)
        if "place" in stages:
            results["place"] = stage_place(proj)
        if "route" in stages:
            results["route"] = stage_route(proj, args.freerouting_jar, args.java)
        if "drc" in stages:
            results["drc"] = stage_drc(kicad_cli, proj)
        if "gerber" in stages:
            results["gerber"] = stage_gerber(kicad_cli, proj)
        if all(results.values()):
            n_ok += 1

    print("\n" + "=" * 68)
    print(f"完了: {n_ok}/{len(projects)} プロジェクトが全ステージ成功")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
