# -*- coding: utf-8 -*-
"""공통 정규화 스키마 정의 + 주차 라벨 통일 + 불량유형 표준화.

모든 공정 파서는 최종적으로 아래 두 long-format 테이블을 산출한다.
  - production    : 주차×공정[×모델] 의 투입/불량/손실 수량과 비율
  - defect_detail : 주차×공정[×모델]×불량유형 의 불량수량
"""
from __future__ import annotations
import re
import datetime as dt
import pandas as pd

from . import config

# ── 공통 스키마 컬럼 정의 ───────────────────────────────────────────
PRODUCTION_COLS = [
    "year", "week", "week_num", "date", "process", "model",
    "input_qty", "defect_qty", "loss_qty", "defect_rate", "loss_rate",
    "inspection_included", "setting_included",
]
DEFECT_DETAIL_COLS = [
    "year", "week", "week_num", "date", "process", "model",
    "defect_type", "defect_qty", "is_loss",
]


# ── 주차 라벨 정규화 ────────────────────────────────────────────────
_WEEK_RE = re.compile(r"(?:(\d{2})\s*[-_]\s*)?W\s*(\d{1,2})", re.IGNORECASE)


def normalize_week(label) -> tuple[int, str, int]:
    """다양한 주차 표기를 (year, 'YY-W##', week_num) 으로 통일한다.

    허용 입력 예: 'W50', '26-W02', '26-W2', 'W02', '2026-W18'.
    연도 추론: 접두사가 있으면 그대로, 없으면 config.WEEK_YEAR_THRESHOLD 로 추론
    (W40 이상 → 2025, 미만 → 2026). week_num = year*100 + week (정렬용).
    """
    if label is None:
        raise ValueError("주차 라벨이 비어 있습니다.")
    s = str(label).strip()
    m = _WEEK_RE.search(s)
    if not m:
        raise ValueError(f"주차 라벨을 해석할 수 없습니다: {label!r}")

    yy, ww = m.group(1), int(m.group(2))

    # 4자리 연도(2026-W18)도 허용
    m4 = re.search(r"(20\d{2})\s*[-_]?\s*W", s, re.IGNORECASE)
    if m4:
        year = int(m4.group(1))
    elif yy is not None:
        year = 2000 + int(yy)
    else:
        year = 2025 if ww >= config.WEEK_YEAR_THRESHOLD else 2026

    week_label = f"{year % 100:02d}-W{ww:02d}"
    week_num = year * 100 + ww
    return year, week_label, week_num


def week_from_date(d: dt.date) -> tuple[int, str, int]:
    """날짜 → (ISO연도, 'YY-W##', week_num). 파일명 날짜로 주차를 정할 때 사용."""
    iso_year, iso_week, _ = d.isocalendar()
    return iso_year, f"{iso_year % 100:02d}-W{iso_week:02d}", iso_year * 100 + iso_week


def yymmdd_from_name(name: str) -> dt.date | None:
    """파일명에서 YYMMDD(6자리) 또는 2026-W## 를 찾아 날짜로 변환(실패 시 None).

    예: '전수검사 내역_코팩_260427.xlsx' → 2026-04-27
    """
    s = str(name)
    m = re.search(r"(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)", s)  # YYMMDD
    if m:
        yy, mm, dd = (int(g) for g in m.groups())
        try:
            return dt.date(2000 + yy, mm, dd)
        except ValueError:
            return None
    m = re.search(r"20(\d{2})\s*[-_]?\s*W\s*(\d{1,2})", s, re.IGNORECASE)
    if m:
        return week_monday(2000 + int(m.group(1)), int(m.group(2)))
    return None


def week_monday(year: int, week: int) -> dt.date:
    """ISO 기준 해당 연/주차의 월요일 날짜를 반환(메인 집계 '날짜' 열용)."""
    try:
        return dt.date.fromisocalendar(year, week, 1)
    except ValueError:
        # 주차 53/00 등 경계값은 그대로 None 처리하도록 호출부에서 방어
        return None


# ── 불량유형 표준화 ─────────────────────────────────────────────────
def standardize_defect_type(process: str, raw_name: str) -> str:
    """공정별 별칭 사전으로 불량유형명을 표준명으로 변환."""
    name = str(raw_name).strip()
    aliases = config.DEFECT_ALIASES.get(process, {})
    return aliases.get(name, name)


def is_loss_type(process: str, defect_type: str, defect_name: str | None = None) -> bool:
    """해당 불량유형(또는 불량명)이 손실(로스)로 분류되는지 판정.

    - 일반 공정: config.LOSS_TYPES[process] 집합에 표준명이 들어있으면 손실.
    - Kopac: 불량명 텍스트에 KOPAC_LOSS_KEYWORDS 가 포함되면 손실.
    """
    if process == "Kopac":
        target = defect_name if defect_name is not None else defect_type
        return any(k in str(target) for k in config.KOPAC_LOSS_KEYWORDS)
    return defect_type in config.LOSS_TYPES.get(process, set())


# ── 값 클린징 ───────────────────────────────────────────────────────
def clean_number(v) -> float:
    """'#DIV/0!', '#VALUE!', 빈셀, 콤마 등을 안전하게 숫자로 변환(실패 시 0)."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return 0.0 if pd.isna(v) else float(v)
    s = str(v).strip().replace(",", "")
    if s == "" or s.startswith("#"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def safe_rate(defect: float, input_qty: float) -> float:
    """불량률 = 불량/투입. 투입 0이면 0 반환(명세서 §5)."""
    return defect / input_qty if input_qty else 0.0
