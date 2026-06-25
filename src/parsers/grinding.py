# -*- coding: utf-8 -*-
"""연마 공정 파서.

입력: '2026-W##-주간업무보고-연마.xlsx' 의 '불량유형 ' 시트(시트명 끝 공백 주의).
레이아웃(제품/LOT 블록 단위로 반복될 수 있음):
  - 'OO 불량 유형 분석'   → 제품(모델)
  - '제조번호 | LOT'
  - '불량명 | 불량수량 | 불량율'  (헤더)
  - 포인트/막힘/휨/이물/연마상태/길이/낙하 …  (실제 불량)
  - 세팅/QC샘플/공정검사                       (손실 — 불량률 제외, 손실률로 별도)
  - '투입수량 | n', '생산수량 | n', '불량 합계 | n', '세팅 + 검사 | n', '총 손실률 | r'

요청사항 5번 적용: 세팅·QC샘플·공정검사는 손실로 분류해 defect_qty 에서 제외하고
loss_qty 로 별도 집계한다. 파일의 '불량 합계'(손실 제외)와 일치하도록 설계.
"""
from __future__ import annotations
import re

from .base import BaseParser, ParseResult
from .. import normalize

# 불량 데이터가 아닌 요약/메타 라벨(공백 제거 후 비교)
_SUMMARY_LABELS = {
    "불량명", "제조번호", "투입수량", "생산수량", "불량합계",
    "불량율", "세팅+검사", "총손실수량", "총손실률",
}


def _norm_label(s) -> str:
    return re.sub(r"\s+", "", str(s)) if s is not None else ""


class GrindingParser(BaseParser):
    process = "연마"

    def parse(self, file) -> ParseResult:
        warnings: list[str] = []
        wb, ws = self.load_sheet(file, "불량유형")

        # 1) 주차: 시트 상단에서 'W##' 패턴이 든 셀을 찾아 정규화
        year = week = week_num = None
        for row in ws.iter_rows(min_row=1, max_row=min(8, ws.max_row), max_col=6, values_only=True):
            for v in row:
                if v and re.search(r"W\s*\d{1,2}", str(v)):
                    try:
                        year, week, week_num = normalize.normalize_week(v)
                        break
                    except ValueError:
                        continue
            if week:
                break
        if not week:
            warnings.append("연마: 주차 라벨을 찾지 못했습니다.")

        # 2) 블록 순회 파싱
        prod_rows, detail_rows = [], []
        cur_product = None
        cur_input = 0.0
        cur_defects: list[tuple[str, float]] = []
        in_block = False

        def flush():
            """수집된 한 블록을 production/defect_detail 로 확정."""
            if not in_block or not cur_defects:
                return
            defect_qty = sum(q for n, q in cur_defects
                             if not normalize.is_loss_type("연마", n))
            loss_qty = sum(q for n, q in cur_defects
                           if normalize.is_loss_type("연마", n))
            prod_rows.append({
                "year": year, "week": week, "week_num": week_num, "date": None,
                "process": "연마", "model": cur_product,
                "input_qty": cur_input, "defect_qty": defect_qty, "loss_qty": loss_qty,
                "defect_rate": normalize.safe_rate(defect_qty, cur_input),
                "loss_rate": normalize.safe_rate(loss_qty, cur_input),
                "inspection_included": False, "setting_included": False,
            })
            for n, q in cur_defects:
                if q == 0:
                    continue
                detail_rows.append({
                    "year": year, "week": week, "week_num": week_num, "date": None,
                    "process": "연마", "model": cur_product,
                    "defect_type": normalize.standardize_defect_type("연마", n),
                    "defect_qty": q, "is_loss": normalize.is_loss_type("연마", n),
                })

        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=4, values_only=True):
            b, c = (row[1] if len(row) > 1 else None), (row[2] if len(row) > 2 else None)
            label = _norm_label(b)

            if b and "불량유형분석" in label:
                # 새 제품 블록 시작 전 이전 블록 확정
                flush()
                cur_product = re.sub(r"불량\s*유형\s*분석", "", str(b)).strip()
                cur_input, cur_defects, in_block = 0.0, [], False
                continue
            if label == "불량명":          # 헤더 → 데이터 수집 개시
                in_block = True
                cur_defects = []
                continue
            if label == "투입수량":
                cur_input = normalize.clean_number(c)
                continue
            if label in _SUMMARY_LABELS:    # 기타 요약행은 무시
                continue
            # 실제 불량/손실 데이터 행
            if in_block and b and c is not None:
                qty = normalize.clean_number(c)
                cur_defects.append((str(b).strip(), qty))

        flush()
        if not prod_rows:
            warnings.append("연마: 유효한 불량 데이터를 찾지 못했습니다.")

        prod, detail = self.build_frames(prod_rows, detail_rows)
        wb.close()
        return ParseResult(production=prod, defect_detail=detail, warnings=warnings)
