# -*- coding: utf-8 -*-
"""정규화 데이터의 완전성·산술 일치 여부를 점검한다."""
from __future__ import annotations

import pandas as pd

from . import aggregate


def submission_status(production: pd.DataFrame, expected_processes: list[str]) -> pd.DataFrame:
    proc_week = aggregate.aggregate_by_process_week(production)
    columns = ["week", "week_num", "submitted", "expected", "complete", "missing"]
    if proc_week.empty:
        return pd.DataFrame(columns=columns)

    rows = []
    expected = set(expected_processes)
    for (week, week_num), grp in proc_week.groupby(["week", "week_num"]):
        submitted = set(grp.loc[grp["input_qty"] > 0, "process"])
        missing = [p for p in expected_processes if p not in submitted]
        rows.append({
            "week": week,
            "week_num": week_num,
            "submitted": len(submitted & expected),
            "expected": len(expected),
            "complete": not missing,
            "missing": ", ".join(missing) if missing else "-",
        })
    return pd.DataFrame(rows, columns=columns).sort_values("week_num").reset_index(drop=True)


def build_quality_log(
    production: pd.DataFrame,
    defect_detail: pd.DataFrame,
    expected_processes: list[str],
) -> pd.DataFrame:
    columns = ["level", "week", "process", "check", "message"]
    logs: list[dict] = []

    def add(level, week, process, check, message):
        logs.append({
            "level": level, "week": week or "-", "process": process or "-",
            "check": check, "message": message,
        })

    if production.empty:
        add("오류", "-", "-", "데이터", "생산 데이터가 없습니다.")
        return pd.DataFrame(logs, columns=columns)

    for _, row in production.iterrows():
        if row["input_qty"] < 0 or row["defect_qty"] < 0 or row["loss_qty"] < 0:
            add("오류", row["week"], row["process"], "음수", "수량에 음수가 포함되어 있습니다.")
        if row["input_qty"] == 0 and (row["defect_qty"] or row["loss_qty"]):
            add("오류", row["week"], row["process"], "분모", "투입 0인데 불량 또는 손실이 존재합니다.")
        if row["defect_rate"] > 1 or row["loss_rate"] > 1:
            add("오류", row["week"], row["process"], "비율", "100%를 초과하는 비율이 있습니다.")

    status = submission_status(production, expected_processes)
    for _, row in status[~status["complete"]].iterrows():
        add("정보", row["week"], "-", "제출 현황", f"미제출 공정: {row['missing']}")

    # 연마·주사침은 파일 정의상 유형별 합계가 생산 집계와 정확히 일치한다.
    # 사출 과거 주차와 Kopac은 요약표/검사표의 집계 범위가 달라 단순 대조하지 않는다.
    reconcilable = {"연마", "주사침"}
    detail_for_check = defect_detail[
        defect_detail["process"].isin(reconcilable)
    ] if defect_detail is not None and not defect_detail.empty else pd.DataFrame()
    if not detail_for_check.empty:
        detail_sum = (detail_for_check.groupby(["week", "process", "is_loss"], as_index=False)
                      ["defect_qty"].sum())
        detail_piv = (detail_sum.pivot_table(
            index=["week", "process"], columns="is_loss",
            values="defect_qty", aggfunc="sum", fill_value=0)
            .reset_index())
        detail_piv.columns.name = None
        detail_piv = detail_piv.rename(columns={False: "detail_defect", True: "detail_loss"})
        for col in ("detail_defect", "detail_loss"):
            if col not in detail_piv:
                detail_piv[col] = 0.0

        prod_sum = (production[production["process"].isin(reconcilable)]
                    .groupby(["week", "process"], as_index=False)
                    .agg(defect_qty=("defect_qty", "sum"), loss_qty=("loss_qty", "sum")))
        chk = prod_sum.merge(detail_piv, on=["week", "process"], how="left").fillna(0)
        for _, row in chk.iterrows():
            if abs(row["defect_qty"] - row["detail_defect"]) > 1:
                add("주의", row["week"], row["process"], "불량 합계",
                    f"생산 집계 {row['defect_qty']:,.0f}건 / 유형 합계 {row['detail_defect']:,.0f}건")
            if abs(row["loss_qty"] - row["detail_loss"]) > 1:
                add("주의", row["week"], row["process"], "손실 합계",
                    f"생산 집계 {row['loss_qty']:,.0f}건 / 손실유형 합계 {row['detail_loss']:,.0f}건")

    if not logs:
        add("정상", "-", "-", "전체", "점검 항목에서 이상이 발견되지 않았습니다.")
    return pd.DataFrame(logs, columns=columns)
