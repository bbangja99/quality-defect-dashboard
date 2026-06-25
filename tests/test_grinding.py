# -*- coding: utf-8 -*-
"""연마 파서 검증.

파일이 스스로 계산해 둔 요약값(불량 합계=435, 세팅+검사=170, 투입=101000,
불량율=0.004307, 총 손실률=0.005990)과 파서 산출을 대조한다.
또한 손실(세팅/QC샘플/공정검사)이 defect_qty 에서 제외되고 loss_qty 로
분리되는지(요청 5번) 확인한다.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.parsers.grinding import GrindingParser  # noqa: E402

GRIND_FILE = Path(r"D:/Project/불량률/생산 현황 및 불량/연마/2026-W18-주간업무보고-연마.xlsx")

# 파일 내 사전 계산된 정답값
EXP = dict(week="26-W18", input_qty=101000, defect_qty=435, loss_qty=170,
           defect_rate=0.0043069, loss_rate=170 / 101000, total_loss_rate=0.0059901)
TOL = 1e-4


def run():
    assert GRIND_FILE.exists(), f"연마 파일 없음: {GRIND_FILE}"
    res = GrindingParser().parse(GRIND_FILE)
    prod, detail = res.production, res.defect_detail
    print(f"[파싱] production {len(prod)}행, defect_detail {len(detail)}행, 경고 {len(res.warnings)}건")
    for w in res.warnings:
        print("   ⚠", w)

    assert not prod.empty, "production 이 비어 있음"
    r = prod.iloc[0]
    fails = []

    def chk(name, got, exp, tol=0.5):
        ok = abs(got - exp) <= tol
        print(f"  {name}: 파싱 {got} / 정답 {exp}  {'OK' if ok else '✗'}")
        if not ok:
            fails.append(name)

    print(f"\n주차: 파싱 {r['week']} / 정답 {EXP['week']}  {'OK' if r['week']==EXP['week'] else '✗'}")
    if r["week"] != EXP["week"]:
        fails.append("week")
    chk("투입수량", r["input_qty"], EXP["input_qty"])
    chk("불량수량(손실제외)", r["defect_qty"], EXP["defect_qty"])
    chk("손실수량", r["loss_qty"], EXP["loss_qty"])
    chk("불량률", r["defect_rate"], EXP["defect_rate"], TOL)
    chk("손실률", r["loss_rate"], EXP["loss_rate"], TOL)

    # 손실 유형 분리 확인
    print("\n[손실 분리 확인]")
    losses = detail[detail["is_loss"]]["defect_type"].tolist()
    real = detail[~detail["is_loss"]]["defect_type"].tolist()
    print(f"  손실로 분류: {losses}")
    print(f"  불량으로 분류: {real}")
    for must in ("세팅", "QC샘플", "공정검사"):
        if must not in losses:
            fails.append(f"손실누락:{must}")
    # 총손실률 = (불량+손실)/투입
    total_loss_rate = (r["defect_qty"] + r["loss_qty"]) / r["input_qty"]
    chk("총손실률", total_loss_rate, EXP["total_loss_rate"], TOL)

    print("\n" + ("✅ 연마 파서 검증 통과" if not fails else f"❌ 불일치 {fails}"))
    return not fails


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
