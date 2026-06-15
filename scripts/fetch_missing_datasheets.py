#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""入手済み 7400 シリーズ IC のうち、データシート未収集（収集予定）の型番について
メーカー公式サイトから PDF を取得し、既存の収録物にならって
``datasheets/_download/{メーカー}/.../{型番}.PDF`` へ格納するスクリプト。

設計方針（規範順守）:
- 取得先は **メーカー公式ドメインのみ**（TI / Nexperia(NXP) / Renesas / onsemi(Fairchild) / Toshiba）。
  サードパーティのデータシート転載サイトは使用しない。
- ダウンロードした内容は **PDF シグネチャ（``%PDF``）と Content-Type** で検証し、
  本物の PDF だけを保存する。HTML エラーページ等は保存せず FAIL として報告する。
- 既に同等のファイルが存在する型番はスキップ（``datasheets/_download`` をトークン索引化して
  ``CD74HC533,CD74HC563.PDF`` のような複合ファイルも認識する）。
- 公式 URL が確定できない型番（主に Toshiba / 一部 Fairchild FAST 等）は
  ダウンロードせず「要手動」として一覧化する。
- 取得した PDF 本体は Git 管理外（``datasheets/_download/`` は .gitignore 済み）。
  本スクリプトは ``--update`` 時に ``datasheet_sources.json`` へ
  URL / sha256 / バイト数 / 参照日 等の **メタ情報のみ** を記録する。

使い方:
    python3 scripts/fetch_missing_datasheets.py --dry-run        # 計画だけ表示
    python3 scripts/fetch_missing_datasheets.py                  # 実ダウンロード
    python3 scripts/fetch_missing_datasheets.py --update         # DL + 収集状況/sources 更新
    python3 scripts/fetch_missing_datasheets.py --manufacturer TI # メーカー絞り込み
    python3 scripts/fetch_missing_datasheets.py --max 10          # 件数制限（試運転）

ネットワーク制限のないローカル環境（利用者の PC）での実行を想定しています。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# パス定義（リポジトリ・ルート基準）
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
STATUS_JSON = REPO_ROOT / "datasheets" / "7400_series_ic_datasheet_collection_status.json"
SOURCES_JSON = REPO_ROOT / "datasheets" / "datasheet_sources.json"
DOWNLOAD_ROOT = REPO_ROOT / "datasheets" / "_download"
REPORT_DEFAULT = REPO_ROOT / ".temp" / "datasheet_fetch" / "fetch_missing_report.json"

USER_AGENT = "7400SeriesCollection/1.0 (+datasheet collector; personal archive)"

# メーカー名（status/sources 表記ゆれ）-> _download 配下フォルダ名
FOLDER = {
    "TI(TexasInstruments)": "TI(TexasInstruments)",
    "TI(Texas Instruments)": "TI(TexasInstruments)",
    "RENESAS": "RENESAS",
    "TOSHIBA": "TOSHIBA",
    "PHILIPS(NXPSemiconductors)": "PHILIPS(NXPSemiconductors)",
    "PHILIPS(NXP Semiconductors)": "PHILIPS(NXPSemiconductors)",
    "NXP Semiconductors": "PHILIPS(NXPSemiconductors)",
    "FAIRCHILD(FairchildSemiconductor)": "FAIRCHILD(FairchildSemiconductor)",
    "FAIRCHILD(Fairchild Semiconductor)": "FAIRCHILD(FairchildSemiconductor)",
    "UTC(UnisonicTechnologies)": "UTC(UnisonicTechnologies)",
}

TI_SYMLINK = "https://www.ti.com/lit/ds/symlink/"


# ---------------------------------------------------------------------------
# 小物
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def norm_token(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", text or "").upper()


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def is_pdf(data: bytes) -> bool:
    return data[:5].startswith(b"%PDF")


def looks_pdf_mime(content_type: str) -> bool:
    ct = (content_type or "").lower()
    return ("application/pdf" in ct) or ("octet-stream" in ct) or ct == ""


# ---------------------------------------------------------------------------
# メーカー別 候補 URL / ファイル名 生成
#   返り値: (filename_stem, [candidate_urls])  filename は拡張子なし大文字
# ---------------------------------------------------------------------------
def strip_pkg(token: str) -> str:
    """末尾のパッケージ/温度記号らしき英字を 1 つ落とす（保守的）。"""
    return token[:-1] if token and token[-1].isalpha() else token


def ti_plan(exact: str, seed_url: str = "") -> tuple[str, list[str]]:
    epn = norm_token(exact).lower()
    cands: list[str] = []
    if seed_url:
        cands.append(seed_url)
    # 規則的な symlink 候補（base = 接頭辞+数字、必要に応じ a/b リビジョン付き）
    m = re.match(r"^(sn\d{2}[a-z]*)(\d{2,4})([a-z].*)?$", epn)
    if m:
        prefix, digits, tail = m.group(1), m.group(2), (m.group(3) or "")
        base = f"{prefix}{digits}"
        for u in (f"{TI_SYMLINK}{base}.pdf",):
            cands.append(u)
        letter = tail[:1]
        if letter in {"a", "b", "c"}:
            cands.append(f"{TI_SYMLINK}{base}{letter}.pdf")
        if prefix in {"sn74als", "sn54als", "sn74as", "sn54as", "sn74ahc"}:
            cands.append(f"{TI_SYMLINK}{base}a.pdf")
        # SN74 <-> SN54 は同一データシートを共有することが多い
        if prefix.startswith("sn74"):
            cands.append(f"{TI_SYMLINK}sn54{prefix[4:]}{digits}.pdf")
    else:
        cands.append(f"{TI_SYMLINK}{epn}.pdf")
    # ファイル名は採用 URL から決めるため、ここでは暫定 stem を返す
    stem = (seed_url and Path(seed_url).stem.upper()) or norm_token(exact)
    # 重複排除（順序維持）
    seen, ordered = set(), []
    for u in cands:
        if u and u not in seen:
            seen.add(u)
            ordered.append(u)
    return stem, ordered


def nxp_plan(exact: str) -> tuple[str, list[str]]:
    t = norm_token(exact)  # e.g. 74HC00N, 74HCU04AP
    m = re.match(r"^74(HCU|HCT|HC)(\d{2,4})", t)
    if not m:
        return norm_token(exact), []
    fam, digits = m.group(1), m.group(2)
    if fam == "HCU":
        fname = f"74HCU{digits}"
        files = [f"74HCU{digits}.pdf"]
    else:  # HC / HCT は HC_HCT 統合データシート
        fname = f"74HC{digits}"
        files = [f"74HC_HCT{digits}.pdf", f"74HC{digits}.pdf"]
    base = "https://assets.nexperia.com/documents/data-sheet/"
    return fname, [base + f for f in files]


def renesas_plan(exact: str) -> tuple[str, list[str]]:
    t = norm_token(exact)
    stem = t
    while stem and stem[-1].isalpha() and not re.search(r"\d$", stem):
        stem = stem[:-1]
    # 末尾の単一パッケージ記号 (P/N/F) を除去
    stem = re.sub(r"(P|N|F|FP|FN)$", "", t)
    low = stem.lower()
    base = "https://www.renesas.com/en/document/dst/"
    cands = [f"{base}{low}-datasheet"]
    # HD74xxx で LS/HC 等が無い場合は LS 版も試す
    mm = re.match(r"^hd74(\d{2,4})$", low)
    if mm:
        cands.append(f"{base}hd74ls{mm.group(1)}-datasheet")
    return stem.upper(), cands


def onsemi_plan(exact: str) -> tuple[str, list[str]]:
    t = norm_token(exact)
    stem = re.sub(r"N$", "", t)  # 末尾 N(パッケージ) を除去
    low = stem.lower()
    base1 = "https://www.onsemi.com/download/data-sheet/pdf/"
    base2 = "https://www.onsemi.com/pdf/datasheet/"
    cands = [f"{base1}{low}-d.pdf", f"{base2}{low}-d.pdf"]
    # MC74HC??? は MM74HC??? でホストされている場合がある
    mhc = re.match(r"^mc(74hc\d{2,4}a?)$", low)
    if mhc:
        cands.append(f"{base1}mm{mhc.group(1)}-d.pdf")
        cands.append(f"{base2}mm{mhc.group(1)}-d.pdf")
    return stem.upper(), cands


def toshiba_plan(exact: str) -> tuple[str, list[str]]:
    # 東芝公式 PDF は docget.jsp?did=<数値> で、数値 ID を機械的に推測できない。
    # 自動取得は行わず、製品ページを参照情報として残す（要手動）。
    return norm_token(exact), []


def plan_for(exact: str, manufacturer: str, seed_url: str) -> tuple[str, list[str], str]:
    """returns (filename_stem, candidate_urls, maker_key)"""
    folder = FOLDER.get(manufacturer, "")
    man = manufacturer or ""
    if not folder:
        # メーカー未記載でも型番から推定（SN74ALS/AS… は TI）
        if re.match(r"^SN\d{2}", norm_token(exact)):
            folder, man = "TI(TexasInstruments)", "TI(Texas Instruments)"
    if folder == "TI(TexasInstruments)":
        stem, cands = ti_plan(exact, seed_url)
        return stem, cands, "TI(Texas Instruments)"
    if folder == "PHILIPS(NXPSemiconductors)":
        stem, cands = nxp_plan(exact)
        return stem, cands, "NXP Semiconductors"
    if folder == "RENESAS":
        stem, cands = renesas_plan(exact)
        return stem, cands, "RENESAS"
    if folder == "FAIRCHILD(FairchildSemiconductor)":
        stem, cands = onsemi_plan(exact)
        return stem, cands, "onsemi (Fairchild)"
    if folder == "TOSHIBA":
        stem, cands = toshiba_plan(exact)
        return stem, cands, "TOSHIBA"
    # フォールバック: seed_url があれば使う
    cands = [seed_url] if seed_url else []
    return norm_token(exact), cands, (man or "?")


def ti_subdir(stem_upper: str) -> str:
    if stem_upper.startswith("CD74"):
        return "CD74HC"
    if stem_upper.startswith("SN74HC") or stem_upper.startswith("SN54HC"):
        return "SN74HC"
    if stem_upper.startswith("SN74LS") or stem_upper.startswith("SN54LS"):
        return "SN74LS"
    return ""


def target_path(folder: str, stem_upper: str) -> Path:
    if folder == "TI(TexasInstruments)":
        sub = ti_subdir(stem_upper)
        return (DOWNLOAD_ROOT / folder / sub / f"{stem_upper}.PDF") if sub else (DOWNLOAD_ROOT / folder / f"{stem_upper}.PDF")
    return DOWNLOAD_ROOT / folder / f"{stem_upper}.PDF"


# ---------------------------------------------------------------------------
# 既存 PDF のトークン索引（スキップ判定用、複合ファイル対応）
# ---------------------------------------------------------------------------
def build_local_index(root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not root.exists():
        return index
    for pdf in root.rglob("*.[pP][dD][fF]"):
        if not pdf.is_file():
            continue
        for raw in re.split(r"[\s,]+", pdf.stem):
            tok = norm_token(raw)
            if tok:
                index.setdefault(tok, pdf)
    return index


def already_have(stem_upper: str, exact: str, index: dict[str, Path]) -> Path | None:
    for key in (stem_upper, norm_token(exact)):
        if key in index:
            return index[key]
    return None


# ---------------------------------------------------------------------------
# ダウンロード
# ---------------------------------------------------------------------------
def fetch(url: str, timeout: float) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        ct = resp.headers.get("Content-Type", "")
        data = resp.read()
    return data, ct


def try_download(cands: list[str], timeout: float, retries: int) -> tuple[bytes | None, str, str]:
    """候補 URL を順に試し、最初の有効 PDF を返す。(data, used_url, note)"""
    last = ""
    for url in cands:
        for attempt in range(retries + 1):
            try:
                data, ct = fetch(url, timeout)
                if data and is_pdf(data) and looks_pdf_mime(ct):
                    return data, url, ""
                last = f"not-pdf(ct={ct}, {len(data)}B)"
                break  # 内容が PDF でないなら次の URL へ
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}"
                if e.code in (403, 429) and attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = f"ERR {getattr(e, 'reason', e)}"
                if attempt < retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                break
    return None, "", last


# ---------------------------------------------------------------------------
# 計画構築
# ---------------------------------------------------------------------------
def build_plan():
    status = read_json(STATUS_JSON)
    sources = read_json(SOURCES_JSON)
    sidx: dict[tuple[str, str], dict] = {}
    for rec in sources:
        for s in rec.get("Sources", []):
            sidx[(rec["PartNumber"], s["ExactPartNumber"])] = s

    plan = []
    for rec in status:
        pn = rec["PartNumber"]
        for mn, val in rec.get("GottenItems_MakerOfDataSheet", {}).items():
            if not str(val).startswith("(収集予定"):
                continue
            s = sidx.get((pn, mn), {})
            seed = s.get("FinalUrl") or s.get("Url") or ""
            manufacturer = s.get("Manufacturer", "")
            stem, cands, maker = plan_for(mn, manufacturer, seed)
            folder = FOLDER.get(manufacturer, "")
            if not folder and re.match(r"^SN\d{2}", norm_token(mn)):
                folder = "TI(TexasInstruments)"
            plan.append({
                "PartNumber": pn,
                "ExactPartNumber": mn,
                "Manufacturer": maker,
                "Folder": folder,
                "FileStem": stem,
                "Candidates": cands,
            })
    return status, sources, sidx, plan


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="未収集 7400 データシートをメーカー公式から取得")
    ap.add_argument("--dry-run", action="store_true", help="ダウンロードせず計画のみ表示")
    ap.add_argument("--update", action="store_true", help="成功分の収集状況/sources を更新")
    ap.add_argument("--manufacturer", default="", help="メーカー絞り込み（部分一致: TI/Renesas/NXP/onsemi/Toshiba/Fairchild）")
    ap.add_argument("--part", default="", help="PartNumber 絞り込み（例 74x240）")
    ap.add_argument("--max", type=int, default=0, help="処理件数の上限（0=無制限）")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--sleep", type=float, default=1.0, help="ダウンロード間スリープ秒")
    ap.add_argument("--report", default=str(REPORT_DEFAULT))
    args = ap.parse_args(argv)

    status, sources, sidx, plan = build_plan()
    index = build_local_index(DOWNLOAD_ROOT)

    if args.manufacturer:
        key = args.manufacturer.lower()
        plan = [p for p in plan if key in p["Manufacturer"].lower() or key in p["Folder"].lower()]
    if args.part:
        plan = [p for p in plan if p["PartNumber"] == args.part]
    if args.max > 0:
        plan = plan[: args.max]

    results = []
    n_ok = n_skip = n_fail = n_manual = 0
    collected_updates: dict[tuple[str, str], str] = {}

    for i, p in enumerate(plan, 1):
        pn, mn, folder, stem = p["PartNumber"], p["ExactPartNumber"], p["Folder"], p["FileStem"]
        cands = p["Candidates"]
        tag = f"[{i}/{len(plan)}] {pn} {mn} ({p['Manufacturer']})"

        if not folder:
            print(f"{tag}: SKIP (フォルダ未確定)")
            results.append({**p, "Result": "SKIP", "Reason": "folder-unresolved"})
            n_skip += 1
            continue

        have = already_have(stem, mn, index)
        if have is not None:
            print(f"{tag}: HAVE  既存 {have.relative_to(REPO_ROOT)}")
            results.append({**p, "Result": "HAVE", "Path": str(have.relative_to(REPO_ROOT))})
            collected_updates[(pn, mn)] = p["Manufacturer"]
            n_skip += 1
            continue

        if not cands:
            ref = ""
            if folder == "TOSHIBA":
                ref = ("https://toshiba.semicon-storage.com/us/semiconductor/product/"
                       f"general-purpose-logic-ics/detail.{norm_token(mn)}.html")
            print(f"{tag}: MANUAL 公式 PDF URL 未確定（要手動）" + (f"  参照: {ref}" if ref else ""))
            results.append({**p, "Result": "MANUAL", "Reason": "no-official-url", "Reference": ref})
            n_manual += 1
            continue

        if args.dry_run:
            dest = target_path(folder, stem)
            print(f"{tag}: PLAN -> {dest.relative_to(REPO_ROOT)}")
            for u in cands:
                print(f"        try: {u}")
            results.append({**p, "Result": "PLAN", "Target": str(dest.relative_to(REPO_ROOT))})
            continue

        data, used, note = try_download(cands, args.timeout, args.retries)
        if data is None:
            print(f"{tag}: FAIL  {note}")
            results.append({**p, "Result": "FAIL", "Reason": note, "Tried": cands})
            n_fail += 1
            time.sleep(args.sleep)
            continue

        # 採用 URL から TI のファイル名を確定（symlink 名に合わせる）
        if folder == "TI(TexasInstruments)":
            stem = Path(used).stem.upper()
        dest = target_path(folder, stem)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        print(f"{tag}: OK    {dest.relative_to(REPO_ROOT)}  ({len(data)}B)  <- {used}")
        results.append({
            **p, "Result": "OK", "Path": str(dest.relative_to(REPO_ROOT)),
            "Url": used, "Bytes": len(data), "Sha256": sha,
        })
        index.setdefault(stem, dest)
        collected_updates[(pn, mn)] = p["Manufacturer"]
        # sources へメタ反映
        s = sidx.get((pn, mn))
        if s is not None:
            s["FinalUrl"] = used
            s["Url"] = s.get("Url") or used
            s["ContentType"] = "application/pdf"
            s["ContentLength"] = str(len(data))
            s["Sha256"] = sha
            s["CheckedAt"] = now_iso()
            s["LastAccessed"] = now_iso()[:10]
        n_ok += 1
        time.sleep(args.sleep)

    # レポート
    report = {
        "GeneratedAt": now_iso(),
        "Totals": {"ok": n_ok, "have/skip": n_skip, "fail": n_fail, "manual": n_manual, "planned": len(plan)},
        "Results": results,
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    write_json(Path(args.report), report)

    print("\n==== 集計 ====")
    print(f"  OK(新規取得) : {n_ok}")
    print(f"  HAVE/SKIP    : {n_skip}")
    print(f"  FAIL         : {n_fail}")
    print(f"  MANUAL(要手動): {n_manual}")
    print(f"  レポート     : {Path(args.report).relative_to(REPO_ROOT) if str(REPO_ROOT) in str(Path(args.report).resolve()) else args.report}")

    if args.update and not args.dry_run and collected_updates:
        # 収集状況 JSON を更新（収集予定 -> メーカー名）
        for rec in status:
            pn = rec["PartNumber"]
            d = rec.get("GottenItems_MakerOfDataSheet", {})
            for mn in list(d):
                if (pn, mn) in collected_updates and str(d[mn]).startswith("(収集予定"):
                    d[mn] = collected_updates[(pn, mn)]
        write_json(STATUS_JSON, status)
        write_json(SOURCES_JSON, sources)
        print(f"  → 収集状況/sources を更新しました（{len(collected_updates)} 件）")

    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
