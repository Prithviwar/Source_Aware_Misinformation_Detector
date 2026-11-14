"""Platt recalibration, fitted on validation predictions only."""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression

from .metrics import _logit, calibration_slope_intercept


class PlattCalibrator:
    def __init__(self, a: float = 0.0, b: float = 1.0):
        self.a, self.b = float(a), float(b)

    def fit(self, p_raw, y) -> "PlattCalibrator":
        z = _logit(p_raw).reshape(-1, 1)
        clf = LogisticRegression(penalty=None, solver="lbfgs", max_iter=1000).fit(z, np.asarray(y, int))
        self.a, self.b = float(clf.intercept_[0]), float(clf.coef_[0, 0])
        return self

    def transform(self, p_raw) -> np.ndarray:
        return 1 / (1 + np.exp(-(self.a + self.b * _logit(p_raw))))

    def to_dict(self) -> dict:
        return {"method": "platt", "a": self.a, "b": self.b}

    @classmethod
    def from_dict(cls, d: dict | None):
        return None if d is None else cls(d["a"], d["b"])


def needs_recalibration(y, p, acceptable: dict) -> tuple[bool, dict]:
    """acceptable = {'slope': [lo, hi], 'intercept': [lo, hi]} (a mentor decision)."""
    si = calibration_slope_intercept(y, p)
    if si["slope"] is None:
        return False, si
    ok = acceptable["slope"][0] <= si["slope"] <= acceptable["slope"][1] and \
        acceptable["intercept"][0] <= si["intercept"] <= acceptable["intercept"][1]
    return (not ok), si
