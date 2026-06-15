#!/usr/bin/env python3
"""
verify_kicad_sch.py

生成済みの .kicad_sch を **GUI を開かずに** kicad-cli で一括 ERC 検証する。
「KiCAD で開いて目視確認」という手動工程を不要にするためのスクリプト。

使い方 (Windows / KiCAD 10.0 インストール環境):
  python scripts/verify_kicad_sch.py                       # pcb-demo 配下を全検証
  python scripts/verify_kicad_sch.py --category 01_buffers_inverters
  python scripts/verify_kicad_sch.py --part 74x00
  python scripts/verify_kicad_sch.py --only-real           # 実シンボル回路図のみ
  python scripts/verify_kicad_sch.py --kicad-cli "D:\\path\\kicad-cli.exe"

終了コード:
  0 = 検証した実シンボル回路図がすべて ERC エラー 0
  1 = ERC エラーを含む回路図があった
  2 = kicad-cli が見つからない等の実行環境エラー

備考:
  - テキスト注釈版（部品を含まない）回路図は ERC 上は自明に通るため、
    既定では「実シンボル回路図」(generator "kicad_sch_gen") を主対象に集計する。
  - JSON レポートを --report-dir に保存できる（既定は保存しない）。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
PCB_DEMO_DIR = BASE_DIR / "pcb-demo"

DEFAULT_KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"


def find_kicad_cli(explicit: str | None) -> str | None:
    """kicad-cli の実行パスを解決する。"""
    candidates = []
    if explicit:
        candidates.append(explicit)
    env = os.environ.get("KICAD_CLI")
    if env:
        candidates.append(env)
    candidates.append(DEFAULT_KICAD_CLI)
    # PATH 上の kicad-cli / kicad-cli.exe
    which = shutil.which("kicad-cli") or shutil.which("kicad-cli.exe")
    if which:
        candidates.append(which)
    for c in candidates:
        if c and Path(c).exists():
            return c
    return which  # 最後の手段（PATH 解決）


def is_real_symbol_sch(path: Path) -> bool:
    """実シンボル回路図（kicad_sch_gen 生成）かどうか。"""
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:400]
    except OSError:
        return False
    return 'generator "kicad_sch_gen"' in head


def collect_targets(category: str | None, part: str | None) -> list[Path]:
    targets = sorted(PCB_DEMO_DIR.glob("**/*.kicad_sch"))
    if category:
        targets = [p for p in targets if f"/{category}/" in p.as_posix()]
    if part:
        targets = [p for p in targets if p.stem == part]
    return targets


def run_erc(kicad_cli: str, sch: Path, report_dir: Path | None) -> tuple[int, int, str]:
    """
    1 ファイルに ERC を実行。
    戻り値: (errors, warnings, raw_report_text)
    errors < 0 は実行失敗を表す。
    """
    if report_dir:
        report_dir.mkdir(parents=True, exist_ok=True)
        out_path = report_dir / f"{sch.stem}.erc.json"
    else:
        tmp = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        )
        tmp.close()
        out_path = Path(tmp.name)

    cmd = [
        kicad_cli, "sch", "erc",
        "--format", "json",
        "--severity-error", "--severity-warning",
        "--output", str(out_path),
        str(sch),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return (-1, -1, f"実行失敗: {exc}")

    errors = warnings = 0
    raw = ""
    try:
        data = json.loads(out_path.read_text(encoding="utf-8"))
        for sheet in data.get("sheets", []):
            for v in sheet.get("violations", []):
                sev = v.get("severity", "")
                if sev == "error":
                    errors += 1
                elif sev == "warning":
                    warnings += 1
        raw = json.dumps(data, ensure_ascii=False)
    except (OSError, json.JSONDecodeError):
        # JSON が読めない場合は stdout/stderr とリターンコードで判断
        raw = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode not in (0,):
            errors = max(errors, 1)
    finally:
        if not report_dir:
            try:
                out_path.unlink()
            except OSError:
                pass
    return (errors, warnings, raw)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--category")
    ap.add_argument("--part")
    ap.add_argument("--only-real", action="store_true",
                    help="実シンボル回路図のみ検証")
    ap.add_argument("--kicad-cli", dest="kicad_cli")
    ap.add_argument("--report-dir", help="ERC JSON レポートの保存先")
    args = ap.parse_args()

    kicad_cli = find_kicad_cli(args.kicad_cli)
    if not kicad_cli or not Path(kicad_cli).exists():
        print(f"[ERROR] kicad-cli が見つかりません。--kicad-cli か環境変数 KICAD_CLI で指定してください。")
        print(f"        試したパス: {kicad_cli or DEFAULT_KICAD_CLI}")
        return 2

    report_dir = Path(args.report_dir) if args.report_dir else None
    targets = collect_targets(args.category, args.part)
    if args.only_real:
        targets = [t for t in targets if is_real_symbol_sch(t)]
    if not targets:
        print("[INFO] 対象の .kicad_sch がありません。")
        return 0

    print("=" * 68)
    print(f"ERC 検証: {len(targets)} ファイル  (kicad-cli: {kicad_cli})")
    print("=" * 68)

    n_pass = n_fail = n_warn = n_real = n_text = n_exec_err = 0
    failures: list[str] = []

    for sch in targets:
        real = is_real_symbol_sch(sch)
        kind = "実" if real else "text"
        if real:
            n_real += 1
        else:
            n_text += 1
        errors, warnings, _ = run_erc(kicad_cli, sch, report_dir)
        rel = sch.relative_to(BASE_DIR).as_posix()
        if errors < 0:
            n_exec_err += 1
            print(f"  [EXEC-ERR] ({kind}) {rel}")
            failures.append(rel)
            continue
        if errors > 0:
            n_fail += 1
            failures.append(rel)
            flag = f"ERR={errors}"
            mark = "[FAIL]"
        else:
            n_pass += 1
            flag = "OK"
            mark = "[ OK ]"
        if warnings > 0:
            n_warn += 1
            flag += f" WARN={warnings}"
        print(f"  {mark} ({kind}) {rel}  {flag}")

    print("=" * 68)
    print(f"合計 {len(targets)} (実シンボル {n_real} / テキスト {n_text})")
    print(f"  PASS={n_pass}  FAIL={n_fail}  warn含む={n_warn}  実行エラー={n_exec_err}")
    if failures:
        print("  要確認:")
        for f in failures:
            print(f"    - {f}")
    print("=" * 68)

    return 1 if (n_fail or n_exec_err) else 0


if __name__ == "__main__":
    sys.exit(main())
