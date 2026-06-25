# -*- coding: utf-8 -*-
"""공정별 불량률 취합·분석 대시보드 (Streamlit).

실행: streamlit run app.py
모드: ① 로컬 폴더 자동 로드(사내 PC)  ② 파일 업로드(클라우드)
"""
from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src import pipeline, aggregate, charts, config, master_excel, quality_checks  # noqa: E402

st.set_page_config(page_title="공정별 불량률 대시보드", page_icon="📊", layout="wide")

DEFAULT_FOLDER = r"D:/Project/불량률/생산 현황 및 불량"


# ── 선택적 비밀번호 게이트 (secrets 에 password 가 있을 때만 작동) ──
def _password_ok() -> bool:
    pw = None
    try:
        pw = st.secrets.get("password")
    except Exception:
        pw = None
    if not pw:
        return True  # 비밀번호 미설정 → 게이트 비활성
    if st.session_state.get("auth_ok"):
        return True
    entered = st.text_input("🔒 비밀번호", type="password")
    if entered and entered == pw:
        st.session_state["auth_ok"] = True
        return True
    if entered:
        st.error("비밀번호가 올바르지 않습니다.")
    return False


@st.cache_data(show_spinner="데이터 로딩·파싱 중…")
def _load_folder(folder: str):
    res = pipeline.load_from_folder(folder)
    return res.production, res.defect_detail, res.warnings, res.used_files


def _load_uploads(uploads: dict):
    results = []
    for proc, files in uploads.items():
        for f in files or []:
            try:
                results.append((proc, pipeline.parse_one(proc, f)))
            except Exception as e:
                st.warning(f"[{proc}] {getattr(f,'name','파일')} 파싱 실패: {e}")
    out = pipeline.combine_many(results)
    return out.production, out.defect_detail, out.warnings, {}


def main():
    if not _password_ok():
        st.stop()

    st.title("📊 공정별 불량률 취합·분석 대시보드")
    st.caption("풍림파마텍 품질팀 · 주차별 생산·불량 자동 취합")

    # ── 사이드바: 데이터 소스 ──────────────────────────────────────
    # 로컬 폴더가 없으면(예: 클라우드 배포) 업로드 모드를 기본으로.
    default_mode = 0 if Path(DEFAULT_FOLDER).exists() else 1
    st.sidebar.header("데이터 소스")
    mode = st.sidebar.radio("불러오기 방식", ["로컬 폴더", "파일 업로드"], index=default_mode)

    if mode == "로컬 폴더":
        folder = st.sidebar.text_input("폴더 경로", value=DEFAULT_FOLDER)
        if st.sidebar.button("🔄 새로고침"):
            _load_folder.clear()
        production, detail, warns, used = _load_folder(folder)
    else:
        st.sidebar.caption("공정별로 최신 엑셀을 올리세요.")
        uploads = {p: st.sidebar.file_uploader(p, type=["xlsx"], accept_multiple_files=True, key=f"u_{p}")
                   for p in pipeline.PARSERS}
        production, detail, warns, used = _load_uploads(uploads)

    if production is None or production.empty:
        st.info("데이터가 없습니다. 폴더 경로를 확인하거나 파일을 업로드하세요.")
        with st.expander("경고/로그"):
            for w in warns:
                st.write("•", w)
        st.stop()

    # ── 사이드바: 필터 ────────────────────────────────────────────
    st.sidebar.header("필터")
    weeks = sorted(production["week"].dropna().unique(),
                   key=lambda w: production.loc[production["week"] == w, "week_num"].iloc[0])
    default_start = weeks[max(0, len(weeks) - 8)]
    wsel = st.sidebar.select_slider("주차 범위", options=weeks,
                                    value=(default_start, weeks[-1])) if len(weeks) > 1 else (weeks[0], weeks[0])
    procs = [p for p in config.PROCESSES if p in set(production["process"])]
    psel = st.sidebar.multiselect("공정", procs, default=procs)
    if not psel:
        st.warning("분석할 공정을 한 개 이상 선택하세요.")
        st.stop()

    lo = production.loc[production["week"] == wsel[0], "week_num"].iloc[0]
    hi = production.loc[production["week"] == wsel[1], "week_num"].iloc[0]
    pmask = production["process"].isin(psel) & production["week_num"].between(lo, hi)
    dmask = detail["process"].isin(psel) & detail["week_num"].between(lo, hi)
    prod_f, det_f = production[pmask], detail[dmask]

    proc_week = aggregate.aggregate_by_process_week(prod_f)
    summary = aggregate.weekly_summary(proc_week)
    status = quality_checks.submission_status(prod_f, psel)
    quality_log = quality_checks.build_quality_log(prod_f, det_f, psel)

    if used:
        st.sidebar.markdown("**사용 파일**")
        for k, v in used.items():
            st.sidebar.caption(f"· {k}: {v}")

    # ── 탭 ────────────────────────────────────────────────────────
    t_overview, t_proc, t_defect, t_dl, t_check = st.tabs(
        ["전체 현황", "공정별", "불량유형/모델", "다운로드", "검증/로그"])

    # 전체 현황
    with t_overview:
        if not summary.empty:
            complete_weeks = set(status.loc[status["complete"], "week"])
            complete_summary = summary[summary["week"].isin(complete_weeks)]
            latest = (complete_summary if not complete_summary.empty else summary).sort_values("week_num").iloc[-1]
            latest_status = status[status["week"] == latest["week"]].iloc[0]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("최신 완전 취합 주차", latest["week"],
                      f"{latest_status['submitted']}/{latest_status['expected']}개 공정")
            c2.metric("가중 불량률", f"{latest['weighted_defect_rate']:.3%}")
            c3.metric("평균 불량률", f"{latest['avg_defect_rate']:.3%}")
            c4.metric("가중 손실률", f"{latest['weighted_loss_rate']:.3%}")
            if len(complete_summary) > 1:
                prev = complete_summary.sort_values("week_num").iloc[-2]
                delta = latest["weighted_defect_rate"] - prev["weighted_defect_rate"]
                st.caption(
                    f"이전 완전 취합 주차({prev['week']}) 대비 가중 불량률 "
                    f"{'▲' if delta > 0 else '▼'} {abs(delta):.3%}")
            if not status[~status["complete"]].empty:
                st.info("일부 주차는 공정 파일이 모두 없어 전체 평균 비교에서 제외됩니다.")
            overall_data = complete_summary if not complete_summary.empty else summary
            st.plotly_chart(charts.overall_trend(overall_data), use_container_width=True)
            st.plotly_chart(charts.process_trend(proc_week), use_container_width=True)
            st.subheader("주차별 공정 제출 현황")
            st.dataframe(
                status[["week", "submitted", "expected", "complete", "missing"]],
                use_container_width=True, hide_index=True,
                column_config={
                    "week": "주차", "submitted": "제출", "expected": "대상",
                    "complete": "완전 취합", "missing": "미제출 공정",
                },
            )
        else:
            st.info("표시할 집계가 없습니다.")

    # 공정별
    with t_proc:
        proc = st.selectbox("공정 선택", psel)
        wk = st.selectbox("주차 선택", [w for w in weeks if lo <= production.loc[production["week"]==w,"week_num"].iloc[0] <= hi][::-1])
        cc1, cc2 = st.columns(2)
        par = aggregate.pareto(det_f, process=proc, week=wk)
        if not par.empty:
            cc1.plotly_chart(charts.pareto_bar(par, f"{proc} {wk} 파레토"), use_container_width=True)
            cc2.plotly_chart(charts.defect_donut(par, f"{proc} {wk} 불량유형 비중"), use_container_width=True)
        else:
            st.info(f"{proc} {wk} 불량유형 데이터가 없습니다.")
        st.plotly_chart(charts.loss_trend(proc_week), use_container_width=True)
        st.dataframe(proc_week[proc_week["process"] == proc][
            ["week", "input_qty", "defect_qty", "loss_qty", "defect_rate", "loss_rate", "ppm"]],
            use_container_width=True, hide_index=True)

    # 불량유형/모델
    with t_defect:
        st.subheader("불량유형 추이 (선택 공정 합산)")
        par_all = aggregate.pareto(det_f, process=None, week=None)
        if not par_all.empty:
            st.plotly_chart(charts.pareto_bar(par_all, "전체 기간 불량유형 파레토"), use_container_width=True)
        if "model" in det_f.columns and det_f["model"].notna().any():
            st.subheader("모델별 불량수량")
            mdf = (det_f[~det_f["is_loss"]].dropna(subset=["model"])
                   .groupby(["process", "model"], as_index=False)["defect_qty"].sum()
                   .sort_values("defect_qty", ascending=False))
            st.dataframe(mdf, use_container_width=True, hide_index=True)

    # 다운로드
    with t_dl:
        st.subheader("정규화 데이터 다운로드")
        st.download_button("⬇ production.csv", prod_f.to_csv(index=False).encode("utf-8-sig"),
                           "production.csv", "text/csv")
        st.download_button("⬇ defect_detail.csv", det_f.to_csv(index=False).encode("utf-8-sig"),
                           "defect_detail.csv", "text/csv")
        st.download_button("⬇ weekly_summary.csv", summary.to_csv(index=False).encode("utf-8-sig"),
                           "weekly_summary.csv", "text/csv")
        st.divider()
        st.subheader("마스터 취합본 (xlsx)")
        st.caption("주차별 생산현황(메인 집계) + 공정별 + 모델별 + Raw 시트 자동 생성")
        xlsx_bytes = master_excel.build_master(prod_f, det_f)
        st.download_button("⬇ 마스터_취합본.xlsx", xlsx_bytes, "마스터_취합본.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # 검증/로그
    with t_check:
        st.subheader("주차×공정 집계")
        st.dataframe(proc_week, use_container_width=True, hide_index=True)
        st.subheader("주차별 요약")
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.subheader("경고/로그")
        warn_only = [w for w in warns if "사용 파일" not in w]
        if warn_only:
            for w in warn_only:
                st.write("⚠", w)
        else:
            st.success("경고 없음")
        st.subheader("자동 데이터 품질 점검")
        st.dataframe(quality_log, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
