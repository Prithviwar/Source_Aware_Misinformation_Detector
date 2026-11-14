"""One-hot encoding fitted on training data only.

- NOT_COMPUTED is encoded in the same column as UNKNOWN (both mean "no
  value"); the distinction is kept in the prediction output instead.
- Levels seen fewer than ``min_count`` times in training are pooled into
  __RARE__. Levels never seen in training are also mapped to __RARE__ and
  reported as warnings at inference.
- Interaction cells (e.g. action_type x publisher_type) get a column only
  if the cell has at least ``min_count`` training pairs; otherwise only the
  two main effects carry information.
- Full one-hot (no dropped reference level): the L2 penalty makes the
  coefficients identifiable.
"""

from __future__ import annotations

from collections import Counter

import numpy as np

from .schema import NOT_COMPUTED, UNKNOWN

RARE = "__RARE__"


def _norm(value: str) -> str:
    return UNKNOWN if value == NOT_COMPUTED else value


class Encoder:
    def __init__(self, features: list[str], interactions: list[tuple[str, str]] | None = None,
                 min_count: int = 1):
        self.features = list(features)
        self.interactions = [tuple(i) for i in (interactions or []) if i[0] in features and i[1] in features]
        self.min_count = int(min_count)
        self.levels: dict[str, list[str]] = {}
        self.cells: dict[str, list[str]] = {}
        self.columns: list[str] = []
        self._index: dict[str, int] = {}
        self.fitted = False

    def fit(self, records: list[dict]) -> "Encoder":
        if not records:
            raise ValueError("cannot fit encoder on zero records")
        for name in self.features:
            counts = Counter(_norm(r["features"][name]) for r in records)
            kept = sorted(v for v, c in counts.items() if c >= self.min_count and v != UNKNOWN)
            self.levels[name] = kept + [UNKNOWN, RARE]
        for a, b in self.interactions:
            key = f"{a}*{b}"
            counts = Counter(self._cell(r, a, b) for r in records)
            self.cells[key] = sorted(c for c, n in counts.items() if n >= self.min_count and c is not None)
        self.columns = [f"{n}={lv}" for n in self.features for lv in self.levels[n]]
        self.columns += [f"{k}={c}" for k, cells in self.cells.items() for c in cells]
        self._index = {c: i for i, c in enumerate(self.columns)}
        self.fitted = True
        return self

    @staticmethod
    def _cell(record: dict, a: str, b: str):
        va, vb = _norm(record["features"][a]), _norm(record["features"][b])
        if UNKNOWN in (va, vb):
            return None
        return f"{va}|{vb}"

    def _level(self, name: str, value: str) -> tuple[str, bool]:
        v = _norm(value)
        if v in self.levels[name]:
            return v, False
        return RARE, True

    def transform(self, records: list[dict], warnings: list[list[str]] | None = None) -> np.ndarray:
        if not self.fitted:
            raise RuntimeError("encoder is not fitted")
        X = np.zeros((len(records), len(self.columns)), dtype=float)
        for i, r in enumerate(records):
            notes = []
            for name in self.features:
                lv, unseen = self._level(name, r["features"][name])
                if unseen and _norm(r["features"][name]) != RARE:
                    notes.append(f"{name}='{r['features'][name]}' unseen or rare in training; encoded as {RARE}")
                X[i, self._index[f"{name}={lv}"]] = 1.0
            for a, b in self.interactions:
                cell = self._cell(r, a, b)
                col = f"{a}*{b}={cell}"
                if cell is not None and col in self._index:
                    X[i, self._index[col]] = 1.0
            if warnings is not None:
                warnings.append(notes)
        return X

    def to_dict(self) -> dict:
        return {"features": self.features, "interactions": [list(i) for i in self.interactions],
                "min_count": self.min_count, "levels": self.levels, "cells": self.cells,
                "columns": self.columns}

    @classmethod
    def from_dict(cls, d: dict) -> "Encoder":
        e = cls(d["features"], [tuple(i) for i in d["interactions"]], d["min_count"])
        e.levels, e.cells, e.columns = d["levels"], d["cells"], d["columns"]
        e._index = {c: i for i, c in enumerate(e.columns)}
        e.fitted = True
        return e
