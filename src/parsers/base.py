# -*- coding: utf-8 -*-
"""파서 공통 인터페이스 + 엑셀 앵커 탐색 등 공통 유틸.

각 공정 파서는 BaseParser 를 상속하고 parse() 를 구현해
정규화된 (production, defect_detail) 두 DataFrame 을 돌려준다.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
import pandas as pd

from .. import normalize


@dataclass
class ParseResult:
    """파서 산출물 묶음. 경고는 UI에서 사용자에게 표시."""
    production: pd.DataFrame
    defect_detail: pd.DataFrame
    warnings: list[str] = field(default_factory=list)


class BaseParser:
    """공정 파서 베이스. process 명칭은 하위 클래스에서 지정."""

    process: str = "UNKNOWN"

    def parse(self, file) -> ParseResult:
        raise NotImplementedError

    # ── 공통 유틸 ──────────────────────────────────────────────────
    @staticmethod
    def load_sheet(file, sheet_name: str | None = None, data_only=True):
        """엑셀 시트를 openpyxl 워크시트로 로드. 시트명 끝 공백도 흡수."""
        wb = openpyxl.load_workbook(file, data_only=data_only)
        if sheet_name is None:
            return wb, wb.worksheets[0]
        # 시트명 끝 공백(예: '불량유형 ') 차이를 무시하고 매칭
        target = sheet_name.strip()
        for ws in wb.worksheets:
            if ws.title.strip() == target:
                return wb, ws
        raise KeyError(f"시트를 찾을 수 없습니다: {sheet_name!r} (가용: {wb.sheetnames})")

    @staticmethod
    def build_frames(prod_rows: list[dict], detail_rows: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
        """dict 리스트를 표준 컬럼 순서의 DataFrame 으로 변환."""
        prod = pd.DataFrame(prod_rows, columns=normalize.PRODUCTION_COLS)
        detail = pd.DataFrame(detail_rows, columns=normalize.DEFECT_DETAIL_COLS)
        return prod, detail
