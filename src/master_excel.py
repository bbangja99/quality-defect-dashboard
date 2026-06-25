# -*- coding: utf-8 -*-
"""마스터 취합본(xlsx) 재생성 (명세서 §3 레이아웃 재현).

build_master(production, defect_detail) -> xlsx 바이트.
시트 구성:
  1) '주차별 생산현황'  : 메인 집계 — 좌(날짜|주차|공정|투입|불량|불량률) + 우(주차|평균|가중 불량률)
  2) 공정별 시트(Kopac/주사침/사출 통합/연마) : 주차별 투입/불량/불량률/손실 + 불량유형 피벗
  3) '모델별 불량률 현황' : 카테고리|모델명|투입수량|불량수량|불량률|비고
  4) 'Raw_production' / 'Raw_defect_detail' : 정규화 long 데이터
"""
from __future__ import annotations
import io
import datetime as dt

import pandas as pd

from . import aggregate, config, normalize


def _monday(week_num: int):
    """week_num(=year*100+week) → 해당 ISO 주차 월요일 날짜."""
    year, wk = week_num // 100, week_num % 100
    try:
        return dt.date.fromisocalendar(year, wk, 1)
    except ValueError:
        return None


def build_master(production: pd.DataFrame, defect_detail: pd.DataFrame) -> bytes:
    proc_week = aggregate.aggregate_by_process_week(production)
    summary = aggregate.weekly_summary(proc_week)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        wb = xw.book
        f_hdr = wb.add_format({"bold": True, "bg_color": "#DDEBF7", "border": 1, "align": "center"})
        f_pct = wb.add_format({"num_format": "0.00%"})
        f_int = wb.add_format({"num_format": "#,##0"})
        f_date = wb.add_format({"num_format": "yyyy-mm-dd"})
        f_title = wb.add_format({"bold": True, "font_size": 13})

        _write_main(xw, wb, proc_week, summary, f_hdr, f_pct, f_int, f_date)
        for proc in [p for p in config.PROCESSES if p in set(proc_week["process"])]:
            _write_process(xw, wb, proc_week, defect_detail, proc, f_hdr, f_pct, f_int)
        _write_models(xw, wb, production, f_hdr, f_pct, f_int, f_title)

        # Raw 시트
        if not production.empty:
            production.to_excel(xw, sheet_name="Raw_production", index=False)
        if not defect_detail.empty:
            defect_detail.to_excel(xw, sheet_name="Raw_defect_detail", index=False)

    return buf.getvalue()


def _write_main(xw, wb, proc_week, summary, f_hdr, f_pct, f_int, f_date):
    ws = wb.add_worksheet("주차별 생산현황")
    xw.sheets["주차별 생산현황"] = ws
    # 좌측 헤더 (B~G), 우측 헤더 (I~K)
    for c, t in zip(range(1, 7), ["날짜", "주차", "공정", "투입수량", "불량수량", "불량률"]):
        ws.write(0, c, t, f_hdr)
    for c, t in zip(range(8, 11), ["주차", "평균 불량률", "가중 불량률"]):
        ws.write(0, c, t, f_hdr)
    ws.set_column(1, 1, 12)
    ws.set_column(2, 3, 10)
    ws.set_column(4, 5, 11)
    ws.set_column(8, 10, 12)

    order = {p: i for i, p in enumerate(config.PROCESSES)}
    r = 1
    for wn in sorted(proc_week["week_num"].unique()):
        grp = proc_week[proc_week["week_num"] == wn].copy()
        grp = grp.sort_values("process", key=lambda s: s.map(lambda p: order.get(p, 99)))
        mon = _monday(int(wn))
        first = True
        for _, row in grp.iterrows():
            if first and mon:
                ws.write_datetime(r, 1, dt.datetime(mon.year, mon.month, mon.day), f_date)
            ws.write(r, 2, row["week"])
            ws.write(r, 3, row["process"])
            ws.write_number(r, 4, float(row["input_qty"]), f_int)
            ws.write_number(r, 5, float(row["defect_qty"]), f_int)
            ws.write_number(r, 6, float(row["defect_rate"]), f_pct)
            r += 1
            first = False
    # 우측 주차별 요약
    rr = 1
    for _, s in summary.sort_values("week_num").iterrows():
        ws.write(rr, 8, s["week"])
        ws.write_number(rr, 9, float(s["avg_defect_rate"]), f_pct)
        ws.write_number(rr, 10, float(s["weighted_defect_rate"]), f_pct)
        rr += 1


def _write_process(xw, wb, proc_week, defect_detail, proc, f_hdr, f_pct, f_int):
    name = proc.replace("/", "_")[:31]
    ws = wb.add_worksheet(name)
    xw.sheets[name] = ws
    # 좌: 주차별 투입/불량/불량률/손실/손실률
    cols = ["주차", "투입수량", "불량수량", "불량률", "손실수량", "손실률"]
    for c, t in enumerate(cols):
        ws.write(0, c, t, f_hdr)
    sub = proc_week[proc_week["process"] == proc].sort_values("week_num")
    r = 1
    for _, row in sub.iterrows():
        ws.write(r, 0, row["week"])
        ws.write_number(r, 1, float(row["input_qty"]), f_int)
        ws.write_number(r, 2, float(row["defect_qty"]), f_int)
        ws.write_number(r, 3, float(row["defect_rate"]), f_pct)
        ws.write_number(r, 4, float(row["loss_qty"]), f_int)
        ws.write_number(r, 5, float(row["loss_rate"]), f_pct)
        r += 1
    ws.set_column(0, 5, 11)

    # 우: 불량유형 피벗(행=주차, 열=불량유형, 값=불량수량) — 손실 제외
    dd = defect_detail[(defect_detail["process"] == proc) & (~defect_detail["is_loss"])]
    if dd.empty:
        return
    piv = dd.pivot_table(index="week", columns="defect_type", values="defect_qty",
                         aggfunc="sum", fill_value=0)
    # week_num 순 정렬
    wn_map = (defect_detail[["week", "week_num"]].drop_duplicates().set_index("week")["week_num"])
    piv = piv.reindex(sorted(piv.index, key=lambda w: wn_map.get(w, 0)))
    start_col = 8
    ws.write(0, start_col, "불량유형 피벗(불량수량)", f_hdr)
    ws.write(1, start_col, "주차", f_hdr)
    for j, dtype in enumerate(piv.columns):
        ws.write(1, start_col + 1 + j, str(dtype), f_hdr)
    for i, (wk, prow) in enumerate(piv.iterrows()):
        ws.write(2 + i, start_col, wk)
        for j, dtype in enumerate(piv.columns):
            ws.write_number(2 + i, start_col + 1 + j, float(prow[dtype]), f_int)


def _write_models(xw, wb, production, f_hdr, f_pct, f_int, f_title):
    ws = wb.add_worksheet("모델별 불량률 현황")
    xw.sheets["모델별 불량률 현황"] = ws
    ws.write(0, 0, "모델별 불량률 현황", f_title)
    for c, t in enumerate(["카테고리", "모델명", "투입수량", "불량수량", "불량률", "비고"]):
        ws.write(2, c, t, f_hdr)
    md = production[production["model"].notna()]
    if not md.empty:
        g = (md.groupby(["process", "model"], as_index=False)
             .agg(input_qty=("input_qty", "sum"), defect_qty=("defect_qty", "sum")))
        g["rate"] = g.apply(lambda r: normalize.safe_rate(r["defect_qty"], r["input_qty"]), axis=1)
        g = g.sort_values(["process", "defect_qty"], ascending=[True, False])
        r = 3
        for _, row in g.iterrows():
            ws.write(r, 0, row["process"])
            ws.write(r, 1, row["model"])
            ws.write_number(r, 2, float(row["input_qty"]), f_int)
            ws.write_number(r, 3, float(row["defect_qty"]), f_int)
            ws.write_number(r, 4, float(row["rate"]), f_pct)
            r += 1
    ws.set_column(0, 1, 18)
    ws.set_column(2, 4, 11)
