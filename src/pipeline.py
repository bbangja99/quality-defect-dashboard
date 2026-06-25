# -*- coding: utf-8 -*-
"""로딩 파이프라인 — 공정별 파서 선택·실행·결합.

두 가지 진입점:
  - load_from_folder(base) : 로컬 '생산 현황 및 불량/' 폴더에서 공정별 최신 파일을
    자동 선택해 파싱·결합. (사내 PC 로컬 실행 모드)
  - parse_one(process, file) / combine(results) : 업로드된 파일을 공정별로 파싱·결합.
    (Streamlit 업로드 모드)

산출: 결합된 production / defect_detail (long format) + 경고 + 사용 파일 목록.
"""
from __future__ import annotations
import re
from pathlib import Path
from dataclasses import dataclass, field

import pandas as pd

from .parsers.base import ParseResult
from .parsers.injection import InjectionParser
from .parsers.grinding import GrindingParser
from .parsers.kopac import KopacParser
from .parsers.needle import NeedleParser
from . import normalize

# 공정 → 파서 클래스
PARSERS = {
    "사출": InjectionParser,
    "연마": GrindingParser,
    "Kopac": KopacParser,
    "주사침": NeedleParser,
}

# 로컬 폴더 모드: 하위 폴더명 → (공정키, 파일 glob)
FOLDER_SOURCES = {
    "사출": ("사출", "*.xlsx"),
    "연마": ("연마", "*.xlsx"),
    "Kopac": ("Kopac", "*.xlsx"),
    "주사침": ("주사침", "*.xlsx"),
}


@dataclass
class LoadResult:
    production: pd.DataFrame
    defect_detail: pd.DataFrame
    warnings: list[str] = field(default_factory=list)
    used_files: dict[str, str] = field(default_factory=dict)


def _content_weeknum(path: Path) -> int:
    """파일 내용의 가장 늦은 날짜 셀로 주차번호 추론(파일명 인식 실패 시 보완)."""
    import datetime as _dt
    import openpyxl
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception:
        return -1
    latest = None
    for ws in wb.worksheets:
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i > 500:  # 대용량 시트 방어
                break
            for v in row:
                if isinstance(v, _dt.datetime):
                    d = v.date()
                    if latest is None or d > latest:
                        latest = d
    wb.close()
    return normalize.week_from_date(latest)[2] if latest else -1


def _week_sortkey(path: Path):
    """파일명→날짜→내용 순으로 주차번호(week_num)를 구해 정렬 키로. 최후엔 mtime."""
    name = path.name
    wn = -1
    m = re.search(r"\d{2}\s*[-_]\s*W\s*\d{1,2}|20\d{2}\s*[-_]?\s*W\s*\d{1,2}|W\s*\d{1,2}", name, re.I)
    if m:
        try:
            wn = normalize.normalize_week(m.group(0))[2]
        except ValueError:
            pass
    if wn < 0:
        d = normalize.yymmdd_from_name(name)
        if d:
            wn = normalize.week_from_date(d)[2]
    if wn < 0:
        wn = _content_weeknum(path)   # 파일명으로 못 구하면 내용 최신 날짜로
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0
    return (wn, mtime)


def parse_one(process: str, file) -> ParseResult:
    """단일 파일을 해당 공정 파서로 파싱."""
    parser_cls = PARSERS.get(process)
    if parser_cls is None:
        raise KeyError(f"알 수 없는 공정: {process!r} (가능: {list(PARSERS)})")
    return parser_cls().parse(file)


def combine(results: dict[str, ParseResult]) -> LoadResult:
    """{공정: ParseResult} 를 결합해 LoadResult 로."""
    prods, dets, warns = [], [], []
    for proc, res in results.items():
        if res is None:
            continue
        if res.production is not None and not res.production.empty:
            prods.append(res.production)
        if res.defect_detail is not None and not res.defect_detail.empty:
            dets.append(res.defect_detail)
        warns += [f"[{proc}] {w}" for w in res.warnings]
    production = pd.concat(prods, ignore_index=True) if prods else pd.DataFrame(columns=normalize.PRODUCTION_COLS)
    detail = pd.concat(dets, ignore_index=True) if dets else pd.DataFrame(columns=normalize.DEFECT_DETAIL_COLS)
    return LoadResult(production=production, defect_detail=detail, warnings=warns)


def load_from_folder(base) -> LoadResult:
    """'생산 현황 및 불량/' 폴더에서 공정별 최신 파일을 자동 선택해 파싱·결합."""
    base = Path(base)
    results: dict[str, ParseResult] = {}
    used: dict[str, str] = {}
    pre_warn: list[str] = []

    for sub, (proc, glob) in FOLDER_SOURCES.items():
        d = base / sub
        if not d.exists():
            pre_warn.append(f"[{proc}] 폴더 없음: {d}")
            continue
        files = [p for p in d.glob(glob) if not p.name.startswith("~$")]
        if not files:
            pre_warn.append(f"[{proc}] 엑셀 파일 없음")
            continue
        latest = max(files, key=_week_sortkey)
        try:
            results[proc] = parse_one(proc, latest)
            used[proc] = latest.name
        except Exception as e:  # 한 공정 실패가 전체를 막지 않도록
            pre_warn.append(f"[{proc}] 파싱 실패({latest.name}): {e}")

    out = combine(results)
    out.warnings = pre_warn + out.warnings
    out.used_files = used
    return out
