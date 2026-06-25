# -*- coding: utf-8 -*-
"""Plotly 차트 빌더 (대시보드용).

모든 차트는 한글 폰트 깨짐을 줄이기 위해 공통 폰트 패밀리를 지정한다.
입력은 aggregate.py 가 만든 DataFrame.
"""
from __future__ import annotations
import plotly.graph_objects as go
import plotly.express as px

from . import config

FONT = "Malgun Gothic, AppleGothic, NanumGothic, sans-serif"


def _layout(fig, title, yfmt=".2%"):
    fig.update_layout(
        title=title, font=dict(family=FONT, size=13),
        margin=dict(l=40, r=20, t=50, b=40), hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white",
    )
    fig.update_yaxes(tickformat=yfmt, gridcolor="#eee")
    fig.update_xaxes(gridcolor="#f5f5f5")
    return fig


def overall_trend(summary):
    """주차별 평균/가중 불량률 추이 라인."""
    s = summary.sort_values("week_num")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s["week"], y=s["avg_defect_rate"], name="평균 불량률",
                             mode="lines+markers", line=dict(width=2)))
    fig.add_trace(go.Scatter(x=s["week"], y=s["weighted_defect_rate"], name="가중 불량률",
                             mode="lines+markers", line=dict(width=2, dash="dot")))
    return _layout(fig, "전체 불량률 추이 (평균·가중)")


def process_trend(proc_week):
    """공정별 불량률 추이 멀티 라인."""
    df = proc_week.sort_values("week_num")
    fig = go.Figure()
    for proc in [p for p in config.PROCESSES if p in set(df["process"])]:
        sub = df[df["process"] == proc]
        fig.add_trace(go.Scatter(
            x=sub["week"], y=sub["defect_rate"], name=proc, mode="lines+markers",
            line=dict(width=2, color=config.PROCESS_COLORS.get(proc))))
    return _layout(fig, "공정별 불량률 추이")


def loss_trend(proc_week):
    """공정별 손실률 추이 멀티 라인."""
    df = proc_week.sort_values("week_num")
    fig = go.Figure()
    for proc in [p for p in config.PROCESSES if p in set(df["process"])]:
        sub = df[df["process"] == proc]
        if sub["loss_rate"].abs().sum() == 0:
            continue
        fig.add_trace(go.Scatter(
            x=sub["week"], y=sub["loss_rate"], name=proc, mode="lines+markers",
            line=dict(width=2, color=config.PROCESS_COLORS.get(proc))))
    return _layout(fig, "공정별 손실률 추이")


def pareto_bar(pareto_df, title="불량유형 파레토"):
    """불량유형 막대 + 누적점유율 라인(이중 축)."""
    p = pareto_df.copy()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=p["defect_type"], y=p["defect_qty"], name="불량수량",
                         marker_color="#1f77b4"))
    fig.add_trace(go.Scatter(x=p["defect_type"], y=p["cum_share"], name="누적점유율",
                             yaxis="y2", mode="lines+markers", line=dict(color="#d62728")))
    fig.update_layout(
        title=title, font=dict(family=FONT, size=13),
        margin=dict(l=40, r=50, t=50, b=80), plot_bgcolor="white",
        yaxis=dict(title="불량수량", gridcolor="#eee"),
        yaxis2=dict(title="누적점유율", overlaying="y", side="right",
                    tickformat=".0%", range=[0, 1.01]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def defect_donut(pareto_df, title="불량유형 비중"):
    """불량유형 점유율 도넛."""
    p = pareto_df.copy()
    fig = px.pie(p, names="defect_type", values="defect_qty", hole=0.45)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(title=title, font=dict(family=FONT, size=13),
                      margin=dict(l=20, r=20, t=50, b=20))
    return fig
