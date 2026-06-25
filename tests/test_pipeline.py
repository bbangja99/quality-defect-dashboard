# -*- coding: utf-8 -*-
from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import pipeline, normalize  # noqa: E402
from src.parsers.base import ParseResult  # noqa: E402


def _result(week, input_qty, defect_qty):
    year, label, week_num = normalize.normalize_week(week)
    prod = pd.DataFrame([{
        "year": year, "week": label, "week_num": week_num, "date": None,
        "process": "연마", "model": "A",
        "input_qty": input_qty, "defect_qty": defect_qty, "loss_qty": 0,
        "defect_rate": defect_qty / input_qty, "loss_rate": 0,
        "inspection_included": False, "setting_included": False,
    }], columns=normalize.PRODUCTION_COLS)
    detail = pd.DataFrame([{
        "year": year, "week": label, "week_num": week_num, "date": None,
        "process": "연마", "model": "A", "defect_type": "휨",
        "defect_qty": defect_qty, "is_loss": False,
    }], columns=normalize.DEFECT_DETAIL_COLS)
    return ParseResult(prod, detail)


def run():
    old = _result("26-W25", 1000, 10)
    revised = _result("26-W25", 1200, 8)
    next_week = _result("26-W26", 900, 9)
    out = pipeline.combine_many([
        ("연마", old), ("연마", revised), ("연마", next_week),
    ])
    assert len(out.production) == 2
    w25 = out.production[out.production["week"] == "26-W25"].iloc[0]
    assert w25["input_qty"] == 1200
    assert w25["defect_qty"] == 8
    assert len(out.defect_detail) == 2
    print("✅ 다중 파일 결합·동일 주차 최신 스냅샷 대체 통과")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
