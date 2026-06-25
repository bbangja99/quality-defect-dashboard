# -*- coding: utf-8 -*-
"""집계·파생지표 계산 (명세서 §5 준수).

입력: 4개 공정 파서가 산출한 production / defect_detail (long format).
출력:
  - aggregate_by_process_week : 주차×공정 투입/불량/손실 + 불량률/손실률/PPM
  - weekly_summary            : 주차별 평균/가중 불량률·손실률 (메인 집계 우측 블록)
  - pareto                    : 불량유형 점유율·누적점유율 (파레토)

지표 정의(마스터 검증 완료):
  - 불량률 = Σ불량 / Σ투입 (투입 0이면 0)
  - PPM = 불량률 × 1,000,000
  - 평균 불량률 = 해당 주차에서 '투입>0'인 공정들의 불량률 단순 평균 (투입 0 공정 제외)
  - 가중 불량률 = Σ(공정 불량) / Σ(공정 투입)
  - 점유율 = 유형 불량 / 공정 총 불량,  누적점유율 = 내림차순 누적
"""
from __future__ import annotations
import pandas as pd

from . import normalize


def aggregate_by_process_week(production: pd.DataFrame) -> pd.DataFrame:
    """주차×공정 단위로 투입/불량/손실을 합산하고 비율·PPM을 재계산."""
    if production is None or production.empty:
        return pd.DataFrame(columns=[
            "year", "week", "week_num", "process",
            "input_qty", "defect_qty", "loss_qty", "defect_rate", "loss_rate", "ppm"])
    g = (production.groupby(["year", "week", "week_num", "process"], as_index=False)
         .agg(input_qty=("input_qty", "sum"),
              defect_qty=("defect_qty", "sum"),
              loss_qty=("loss_qty", "sum")))
    g["defect_rate"] = g.apply(lambda r: normalize.safe_rate(r["defect_qty"], r["input_qty"]), axis=1)
    g["loss_rate"] = g.apply(lambda r: normalize.safe_rate(r["loss_qty"], r["input_qty"]), axis=1)
    g["ppm"] = g["defect_rate"] * 1_000_000
    return g.sort_values(["week_num", "process"]).reset_index(drop=True)


def weekly_summary(process_week: pd.DataFrame) -> pd.DataFrame:
    """주차별 평균·가중 불량률/손실률 요약(메인 집계 우측 블록 재현)."""
    if process_week is None or process_week.empty:
        return pd.DataFrame(columns=[
            "year", "week", "week_num", "n_processes",
            "total_input", "total_defect", "total_loss",
            "avg_defect_rate", "weighted_defect_rate",
            "avg_loss_rate", "weighted_loss_rate"])
    rows = []
    for (yr, wk, wn), grp in process_week.groupby(["year", "week", "week_num"]):
        valid = grp[grp["input_qty"] > 0]            # 투입>0 공정만 평균 대상
        tot_in = grp["input_qty"].sum()
        tot_df = grp["defect_qty"].sum()
        tot_loss = grp["loss_qty"].sum()
        rows.append({
            "year": yr, "week": wk, "week_num": wn,
            "n_processes": int((grp["input_qty"] > 0).sum()),
            "total_input": tot_in, "total_defect": tot_df, "total_loss": tot_loss,
            "avg_defect_rate": valid["defect_rate"].mean() if len(valid) else 0.0,
            "weighted_defect_rate": normalize.safe_rate(tot_df, tot_in),
            "avg_loss_rate": valid["loss_rate"].mean() if len(valid) else 0.0,
            "weighted_loss_rate": normalize.safe_rate(tot_loss, tot_in),
        })
    return pd.DataFrame(rows).sort_values("week_num").reset_index(drop=True)


def pareto(defect_detail: pd.DataFrame, process: str | None = None,
           week: str | None = None, include_loss: bool = False) -> pd.DataFrame:
    """불량유형별 점유율·누적점유율·PPM(파레토). 기본은 손실 제외.

    process/week 를 주면 해당 범위로 필터. include_loss=True 면 손실유형도 포함.
    """
    cols = ["defect_type", "defect_qty", "share", "cum_share"]
    if defect_detail is None or defect_detail.empty:
        return pd.DataFrame(columns=cols)
    df = defect_detail
    if process is not None:
        df = df[df["process"] == process]
    if week is not None:
        df = df[df["week"] == week]
    if not include_loss:
        df = df[~df["is_loss"]]
    if df.empty:
        return pd.DataFrame(columns=cols)
    p = (df.groupby("defect_type", as_index=False)["defect_qty"].sum()
         .sort_values("defect_qty", ascending=False).reset_index(drop=True))
    total = p["defect_qty"].sum()
    p["share"] = p["defect_qty"] / total if total else 0.0
    p["cum_share"] = p["share"].cumsum()
    return p
