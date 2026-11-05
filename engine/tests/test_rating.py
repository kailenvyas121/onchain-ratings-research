"""Offline tests for src/rating.py.  python -m pytest tests -q"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rating import SCALE, asof, is_investment_grade, notch  # noqa: E402


def test_scale_bands_are_contiguous():
    bands = list(SCALE.values())
    assert all(a[1] == b[0] for a, b in zip(bands, bands[1:]))


def test_investment_grade_line_is_between_A_and_A_minus():
    assert is_investment_grade("A") and is_investment_grade("A+")
    assert not is_investment_grade("A-") and not is_investment_grade("B+")


def test_notch_direction():
    assert notch("A-") > notch("A")  # positive = downgrade


def test_asof_never_looks_ahead():
    s = pd.Series({pd.Timestamp("2026-01-01"): 1.0, pd.Timestamp("2026-01-05"): 2.0})
    assert asof(s, pd.Timestamp("2026-01-04")) == 1.0
    assert asof(s, pd.Timestamp("2026-01-05")) == 2.0
    assert asof(s, pd.Timestamp("2026-01-20")) is None  # gap too long
