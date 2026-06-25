# -*- coding: utf-8 -*-
"""집계 회귀 검증.

4개 공정 파서(최신 파일) → production 결합 → 주차×공정 집계 → 주차별 요약.
26-W25 의 평균/가중 불량률이 마스터 '사출통합' 시트 요약과 4자리 일치하는지 확인.
또 파레토(점유율 합=1)도 점검.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.parsers.injection import InjectionParser  # noqa: E402
from src.parsers.grinding import GrindingParser    # noqa: E402
from src.parsers.kopac import KopacParser          # noqa: E402
from src.parsers.needle import NeedleParser        # noqa: E402
from src import aggregate                           # noqa: E402

BASE = Path(r"D:/Project/불량률/생산 현황 및 불량")
MASTER = Path(r"D:/Project/불량률/품질팀 관리본/각 공정별 불량 현황_주요 공정_공정검사 미포함.xlsx")
FILES = [
    (InjectionParser, BASE / "사출/사출 불량유형(2026)_W25.xlsx"),
    (GrindingParser, BASE / "연마/2026-W25-주간업무보고-연마.xlsx"),
    (KopacParser, BASE / "Kopac/불량유형_코팩_2606022.xlsx"),
    (NeedleParser, BASE / "주사침/2026-W25-불량유형_주사침 0619, 20.xlsx"),
]
# 마스터 사출통합 시트 W25 요약(검증 기준)
MASTER_W25 = {"avg": 0.003250530248025093, "weighted": 0.002390705403868861}
TOL = 1e-4


def _load_all():
    prods, dets, warns = [], [], []
    for P, path in FILES:
        res = P().parse(path)
        prods.append(res.production)
        dets.append(res.defect_detail)
        warns += res.warnings
    production = pd.concat(prods, ignore_index=True)
    detail = pd.concat(dets, ignore_index=True)
    return production, detail, warns


def run():
    production, detail, warns = _load_all()
    proc_week = aggregate.aggregate_by_process_week(production)
    summary = aggregate.weekly_summary(proc_week)

    print("[W25 공정별 집계]")
    w25 = proc_week[proc_week["week"] == "26-W25"]
    print(w25[["process", "input_qty", "defect_qty", "loss_qty", "defect_rate", "loss_rate"]].to_string(index=False))

    s = summary[summary["week"] == "26-W25"].iloc[0]
    print(f"\n[W25 요약] 공정수 {s['n_processes']} | 투입계 {s['total_input']:.0f} | 불량계 {s['total_defect']:.0f}")
    print(f"  평균 불량률: 파싱 {s['avg_defect_rate']:.7f} / 마스터 {MASTER_W25['avg']:.7f}")
    print(f"  가중 불량률: 파싱 {s['weighted_defect_rate']:.7f} / 마스터 {MASTER_W25['weighted']:.7f}")
    print(f"  (참고) 평균 손실률 {s['avg_loss_rate']:.5f} / 가중 손실률 {s['weighted_loss_rate']:.5f}")

    fails = []
    if abs(s["avg_defect_rate"] - MASTER_W25["avg"]) > TOL:
        fails.append("평균 불량률")
    if abs(s["weighted_defect_rate"] - MASTER_W25["weighted"]) > TOL:
        fails.append("가중 불량률")
    if s["n_processes"] != 4:
        fails.append(f"공정수 {s['n_processes']}≠4")

    # 파레토 점검: 사출 W25 점유율 합 ≈ 1
    par = aggregate.pareto(detail, process="사출 통합", week="26-W25")
    print(f"\n[사출 W25 파레토 상위]\n{par.head(5).to_string(index=False)}")
    if not par.empty and abs(par['share'].sum() - 1.0) > 1e-6:
        fails.append("파레토 점유율 합≠1")
    if not par.empty and abs(par['cum_share'].iloc[-1] - 1.0) > 1e-6:
        fails.append("누적점유율 끝≠1")

    print("\n" + ("✅ 집계 회귀 통과 — W25 평균/가중 불량률 마스터 일치"
                  if not fails else f"❌ 불일치 {fails}"))
    return not fails


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
