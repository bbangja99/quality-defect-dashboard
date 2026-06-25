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


def _collapse_result(res: ParseResult) -> ParseResult:
    """한 파일 안의 중복 행을 주차·공정·모델 기준으로 정리한다."""
    prod = res.production.copy()
    detail = res.defect_detail.copy()

    if not prod.empty:
        keys = ["year", "week", "week_num", "date", "process", "model"]
        prod = (prod.groupby(keys, dropna=False, as_index=False)
                .agg(input_qty=("input_qty", "sum"),
                     defect_qty=("defect_qty", "sum"),
                     loss_qty=("loss_qty", "sum"),
                     inspection_included=("inspection_included", "max"),
                     setting_included=("setting_included", "max")))
        prod["defect_rate"] = prod.apply(
            lambda r: normalize.safe_rate(r["defect_qty"], r["input_qty"]), axis=1)
        prod["loss_rate"] = prod.apply(
            lambda r: normalize.safe_rate(r["loss_qty"], r["input_qty"]), axis=1)
        prod = prod[normalize.PRODUCTION_COLS]

    if not detail.empty:
        keys = [
            "year", "week", "week_num", "date", "process", "model",
            "defect_type", "is_loss",
        ]
        detail = (detail.groupby(keys, dropna=False, as_index=False)
                  .agg(defect_qty=("defect_qty", "sum")))
        detail = detail[normalize.DEFECT_DETAIL_COLS]

    return ParseResult(prod, detail, list(res.warnings))


def combine_many(results: list[tuple[str, ParseResult]]) -> LoadResult:
    """여러 파일을 합치고 같은 주차·모델 스냅샷은 최신 파일로 대체."""
    prods, dets, warns = [], [], []
    for seq, (proc, raw_res) in enumerate(results):
        if raw_res is None:
            continue
        res = _collapse_result(raw_res)
        if res.production is not None and not res.production.empty:
            p = res.production.copy()
            p["_source_seq"] = seq
            prods.append(p)
        if res.defect_detail is not None and not res.defect_detail.empty:
            d = res.defect_detail.copy()
            d["_source_seq"] = seq
            dets.append(d)
        warns += [f"[{proc}] {w}" for w in res.warnings]

    if prods:
        production = pd.concat(prods, ignore_index=True)
        key = ["year", "week", "week_num", "process", "model"]
        production = (production.sort_values("_source_seq")
                      .drop_duplicates(key, keep="last")
                      .drop(columns="_source_seq")
                      .sort_values(["week_num", "process", "model"], na_position="last")
                      .reset_index(drop=True))
    else:
        production = pd.DataFrame(columns=normalize.PRODUCTION_COLS)

    if dets:
        detail = pd.concat(dets, ignore_index=True)
        key = [
            "year", "week", "week_num", "process", "model",
            "defect_type", "is_loss",
        ]
        detail = (detail.sort_values("_source_seq")
                  .drop_duplicates(key, keep="last")
                  .drop(columns="_source_seq")
                  .sort_values(
                      ["week_num", "process", "model", "defect_type"],
                      na_position="last")
                  .reset_index(drop=True))
    else:
        detail = pd.DataFrame(columns=normalize.DEFECT_DETAIL_COLS)

    return LoadResult(production=production, defect_detail=detail, warnings=warns)


def combine(results: dict[str, ParseResult]) -> LoadResult:
    """{공정: ParseResult} 를 결합해 LoadResult 로."""
    return combine_many(list(results.items()))


def load_from_folder(base) -> LoadResult:
    """공정별 파일을 누적 파싱한다. 사출 연간 스냅샷만 최신 파일을 사용."""
    base = Path(base)
    results: list[tuple[str, ParseResult]] = []
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
        selected = ([max(files, key=_week_sortkey)] if proc == "사출"
                    else sorted(files, key=_week_sortkey))
        used_names = []
        for path in selected:
            try:
                results.append((proc, parse_one(proc, path)))
                used_names.append(path.name)
            except Exception as e:  # 한 공정 실패가 전체를 막지 않도록
                pre_warn.append(f"[{proc}] 파싱 실패({path.name}): {e}")
        if used_names:
            used[proc] = ", ".join(used_names)

    out = combine_many(results)
    out.warnings = pre_warn + out.warnings
    out.used_files = used
    return out
