# -*- coding: utf-8 -*-
"""주사침 파서 검증.

요청사항 적용 확인:
  - 주사침/범용/안과용만 관리, 의료기기 set 모델 제외
  - 세팅소모/QC검사/공정검사는 손실로 분리
파일 내부값과 대조:
  - 손실 = 175 (= 총로스수량 1171 - 총불량수량 996, = 60+65+50)
  - 총불량수량 996 = 관리대상 불량(992) + 의료기기 불량(4)
  - 관리대상 적합 = 142,681 (의료기기 2,029 제외)
  - 주차 = 26-W18
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.parsers.needle import NeedleParser  # noqa: E402

NEEDLE = Path(r"D:/Project/불량률/생산 현황 및 불량/주사침/2026-W18-불량유형_주사침 0430.xlsx")


def run():
    assert NEEDLE.exists(), f"주사침 파일 없음: {NEEDLE}"
    res = NeedleParser().parse(NEEDLE)
    prod, detail = res.production, res.defect_detail
    print(f"[파싱] production {len(prod)}행, defect_detail {len(detail)}행")
    for w in res.warnings:
        print("   ⚠", w)

    assert not prod.empty
    r = prod.iloc[0]
    print(prod[["week", "process", "input_qty", "defect_qty", "loss_qty",
                "defect_rate", "loss_rate"]].to_string(index=False))

    fails = []

    def chk(name, got, exp, tol=0.5):
        ok = abs(got - exp) <= tol
        print(f"  {name}: 파싱 {got:.4f} / 기대 {exp}  {'OK' if ok else '✗'}")
        if not ok:
            fails.append(f"{name}({got}≠{exp})")

    # 제외된 의료기기 불량수량을 경고에서 파싱
    import re as _re
    excl_w = next((w for w in res.warnings if "의료기기 set 불량" in w), "")
    excluded = float(_re.search(r"(\d+)건", excl_w).group(1)) if excl_w else 0.0

    print(f"\n주차: {r['week']} {'OK' if r['week']=='26-W18' else '✗'}")
    if r["week"] != "26-W18":
        fails.append("week")
    chk("손실수량", r["loss_qty"], 175)
    # 불변식: 관리대상 불량 + 의료기기 불량 = 총불량수량(996)
    chk("관리대상불량+의료기기불량=총불량", r["defect_qty"] + excluded, 996)
    # 관리대상 적합 = 투입 - 불량 = 142,681 (의료기기 2,029 제외 검산)
    chk("관리대상 적합", r["input_qty"] - r["defect_qty"], 142681)
    chk("불량률", r["defect_rate"], r["defect_qty"] / r["input_qty"], 1e-9)
    print(f"  (검산) 관리대상불량 {r['defect_qty']:.0f} + 의료기기 {excluded:.0f} = {r['defect_qty']+excluded:.0f}")

    # 손실/제외 분류 확인
    print("\n[손실로 분류]")
    losses = detail[detail["is_loss"]]
    print(losses[["model", "defect_type", "defect_qty"]].to_string(index=False))
    for must in ("세팅소모", "QC검사", "공정검사"):
        if must not in losses["defect_type"].map(lambda s: s.replace(" ", "")).tolist():
            fails.append(f"손실누락:{must}")

    print("\n[관리대상 불량유형 — 의료기기 제외 확인]")
    types = detail[~detail["is_loss"]]["defect_type"].tolist()
    print("  유형:", sorted(set(types)))
    bad = [t for t in types if "set" in t.lower()]
    if bad:
        fails.append(f"의료기기 set 미제외: {bad}")
    # 카테고리(model) 분포
    print("  카테고리:", detail[~detail["is_loss"]]["model"].value_counts().to_dict())

    # 교차검증: 관리대상 불량 + 의료기기 불량 = 총불량수량 996
    excl = next((w for w in res.warnings if "의료기기 set 불량" in w), "")
    print(f"\n  (정보) {excl}")

    print("\n" + ("✅ 주사침 파서 검증 통과" if not fails else f"❌ 불일치 {fails}"))
    return not fails


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
