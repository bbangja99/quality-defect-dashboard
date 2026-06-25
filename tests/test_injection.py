# -*- coding: utf-8 -*-
"""사출 파서 검증 — 마스터 회귀.

품질팀 마스터('사출 통합' 시트)의 주차별 투입/불량/불량률과, 파서가
'주차별_트렌드'에서 산출한 값이 일치하는지 확인한다(소수점 4자리).
이것이 자동화 신뢰성의 핵심 근거다.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.parsers.injection import InjectionParser  # noqa: E402
from src import normalize  # noqa: E402

# 최신 파일 우선
INJ_DIR = Path(r"D:/Project/불량률/생산 현황 및 불량/사출")
INJ_FILE = INJ_DIR / "사출 불량유형(2026)_W25.xlsx"
if not INJ_FILE.exists():
    INJ_FILE = INJ_DIR / "사출 불량유형(2026).xlsx"

MASTER = Path(r"D:/Project/불량률/품질팀 관리본/각 공정별 불량 현황_주요 공정_공정검사 미포함.xlsx")
TOL = 1e-4


def _master_injection():
    """마스터 '사출 통합' 시트에서 주차별 사출 통합 투입/불량/불량률 추출."""
    df = pd.read_excel(MASTER, sheet_name="각 공정 주차별 생산현황-사출통합", engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    # 컬럼: (공백) 날짜 주차 공정 투입수량 불량수량 불량률 ...
    rows = []
    for _, r in df.iterrows():
        proc = r.get("공정")
        if proc is None or "사출" not in str(proc):
            continue
        try:
            wk = normalize.normalize_week(r.get("주차"))[1]
        except (ValueError, TypeError):
            continue
        rows.append((wk, normalize.clean_number(r.get("투입수량")),
                     normalize.clean_number(r.get("불량수량")),
                     normalize.clean_number(r.get("불량률"))))
    return pd.DataFrame(rows, columns=["week", "inp", "df", "rate"])


def run():
    res = InjectionParser().parse(INJ_FILE)
    print(f"[파싱] {INJ_FILE.name} → production {len(res.production)}행, "
          f"detail {len(res.defect_detail)}행, 경고 {len(res.warnings)}")
    for w in res.warnings:
        print("   ⚠", w)
    got = (res.production.groupby("week")
              .agg(inp=("input_qty", "sum"), df=("defect_qty", "sum")).reset_index())
    got["rate"] = got.apply(lambda r: normalize.safe_rate(r["df"], r["inp"]), axis=1)

    # 현 방식('사출 통합'=주차별_트렌드)이 적용된 최근 주차. 이 구간은 정확히 일치해야 함.
    # (W18 이전은 과거 새만금/오식도 분리 합산 방식이라 정의가 다름 → 정보로만 표시)
    CURRENT_FROM = 2026 * 100 + 18  # 26-W18
    mst = _master_injection()
    m = got.merge(mst, on="week", how="inner", suffixes=("_got", "_mst"))
    print(f"\n마스터와 겹치는 주차 {len(m)}개 대조:")
    fails, hist = [], []
    for _, r in m.sort_values("week").iterrows():
        wn = normalize.normalize_week(r["week"])[2]
        ok = (abs(r["inp_got"] - r["inp_mst"]) < 0.5 and abs(r["df_got"] - r["df_mst"]) < 0.5
              and abs(r["rate_got"] - r["rate_mst"]) < TOL)
        mark = "OK" if ok else ("hist" if wn < CURRENT_FROM else "✗")
        if not ok:
            (hist if wn < CURRENT_FROM else fails).append(r["week"])
        print(f"  {r['week']} | 투입 {r['inp_got']:.0f}/{r['inp_mst']:.0f} | "
              f"불량 {r['df_got']:.0f}/{r['df_mst']:.0f} | 불량률 {r['rate_got']:.5f}/{r['rate_mst']:.5f}  {mark}")

    if hist:
        print(f"\n  (참고) 과거 방식 주차 {len(hist)}개는 새만금/오식도 분리 합산이라 정의가 다름: {hist}")
    recent_ok = sum(1 for _, r in m.iterrows() if normalize.normalize_week(r['week'])[2] >= CURRENT_FROM)
    print("\n" + (f"✅ 사출 마스터 회귀 통과 — 현 방식(26-W18~) {recent_ok}주차 정확 일치"
                  if not fails else f"❌ 현 방식 구간 {len(fails)}건 불일치: {fails}"))
    return not fails


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
