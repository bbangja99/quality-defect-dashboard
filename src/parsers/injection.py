# -*- coding: utf-8 -*-
"""사출 공정 파서.

입력: '사출 불량유형(2026)[_W##].xlsx'

★ 소스 선택(중요): 품질팀 마스터의 '사출 통합' 주차별 투입/불량/불량률은
  이 파일의 **'주차별_트렌드' 시트와 정확히 일치**한다(검증됨). 반면 'Raw_Data'·
  개별 주차시트(W##)는 설비동 일부만/구버전이라 합계가 어긋난다.
  → 따라서 production 의 1차 소스는 '주차별_트렌드'로 한다(마스터 재현 보장).
  (주차별_트렌드 가 없으면 Raw_Data 로 폴백)

- 사출은 선별 공정이라 손실(로스) 항목이 없다 → loss_qty=0.
- '주차별_트렌드'는 이미 설비동 통합 → process='사출 통합'.
"""
from __future__ import annotations

import pandas as pd

from .base import BaseParser, ParseResult
from .. import normalize

TREND_SHEET = "주차별_트렌드"
# 트렌드 시트의 메타(비-불량유형) 컬럼
TREND_META = ["주차", "불량률", "불량합계", "선별수량"]


class InjectionParser(BaseParser):
    process = "사출 통합"

    def parse(self, file) -> ParseResult:
        warnings: list[str] = []
        xls = pd.ExcelFile(file, engine="openpyxl")
        sheets = [s.strip() for s in xls.sheet_names]

        if TREND_SHEET in sheets:
            real = [s for s in xls.sheet_names if s.strip() == TREND_SHEET][0]
            return self._parse_trend(xls.parse(real), warnings)

        warnings.append("사출: '주차별_트렌드' 시트가 없어 Raw_Data 로 폴백합니다.")
        if any(s == "Raw_Data" for s in sheets):
            return self._parse_raw(xls.parse("Raw_Data"), warnings)
        warnings.append("사출: 사용할 수 있는 시트가 없습니다.")
        return ParseResult(*self.build_frames([], []), warnings=warnings)

    # ── 1차: 주차별_트렌드 ─────────────────────────────────────────
    def _parse_trend(self, df, warnings) -> ParseResult:
        df = df.dropna(how="all")
        defect_cols = [c for c in df.columns if str(c).strip() not in TREND_META]
        prod_rows, detail_rows = [], []
        for _, row in df.iterrows():
            try:
                year, week, week_num = normalize.normalize_week(row.get("주차"))
            except (ValueError, TypeError):
                continue  # '합계' 등 비-주차 행
            input_qty = normalize.clean_number(row.get("선별수량"))
            defect_qty = normalize.clean_number(row.get("불량합계"))
            prod_rows.append({
                "year": year, "week": week, "week_num": week_num, "date": None,
                "process": "사출 통합", "model": None,
                "input_qty": input_qty, "defect_qty": defect_qty, "loss_qty": 0.0,
                "defect_rate": normalize.safe_rate(defect_qty, input_qty), "loss_rate": 0.0,
                "inspection_included": True, "setting_included": True,
            })
            for c in defect_cols:
                qty = normalize.clean_number(row.get(c))
                if qty == 0:
                    continue
                detail_rows.append({
                    "year": year, "week": week, "week_num": week_num, "date": None,
                    "process": "사출 통합", "model": None,
                    "defect_type": normalize.standardize_defect_type("사출 통합", str(c).strip()),
                    "defect_qty": qty, "is_loss": False,
                })
        prod, detail = self.build_frames(prod_rows, detail_rows)
        if prod.empty:
            warnings.append("사출: 주차별_트렌드에서 유효 행을 찾지 못했습니다.")
        return ParseResult(production=prod, defect_detail=detail, warnings=warnings)

    # ── 폴백: Raw_Data ─────────────────────────────────────────────
    def _parse_raw(self, df, warnings) -> ParseResult:
        df = df.dropna(how="all")
        meta = ["주차", "설비동", "날짜", "모델명", "선별수량", "불량률", "불량합계", "TOTAL"]
        defect_cols = [c for c in df.columns if str(c).strip() not in meta]
        prod_rows, detail_rows = [], []
        for _, row in df.iterrows():
            try:
                year, week, week_num = normalize.normalize_week(row.get("주차"))
            except (ValueError, TypeError):
                continue
            input_qty = normalize.clean_number(row.get("선별수량"))
            defect_qty = normalize.clean_number(row.get("불량합계"))
            model = row.get("모델명")
            model = str(model).strip() if model is not None and not pd.isna(model) else None
            prod_rows.append({
                "year": year, "week": week, "week_num": week_num, "date": None,
                "process": "사출 통합", "model": model,
                "input_qty": input_qty, "defect_qty": defect_qty, "loss_qty": 0.0,
                "defect_rate": normalize.safe_rate(defect_qty, input_qty), "loss_rate": 0.0,
                "inspection_included": True, "setting_included": True,
            })
            for c in defect_cols:
                qty = normalize.clean_number(row.get(c))
                if qty == 0:
                    continue
                detail_rows.append({
                    "year": year, "week": week, "week_num": week_num, "date": None,
                    "process": "사출 통합", "model": model,
                    "defect_type": normalize.standardize_defect_type("사출 통합", str(c).strip()),
                    "defect_qty": qty, "is_loss": False,
                })
        return ParseResult(*self.build_frames(prod_rows, detail_rows), warnings=warnings)
