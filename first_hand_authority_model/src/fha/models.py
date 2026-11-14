"""The four compared models.

1. RoleRuleModel          hand-written rules (no learning)
2. TypePriorModel         smoothed P(y=1 | publisher_type)
3. LogisticModel(publisher-only features)
4. LogisticModel(claim-conditioned features + interactions)

Models 3 and 4 share the learner, the tuning grid and the training rows,
so their difference isolates the contribution of claim information.
All models serialise to plain JSON (no pickle).
"""

from __future__ import annotations

import json

import numpy as np
from sklearn.linear_model import LogisticRegression

from .encoding import Encoder
from .schema import FeatureSchema, NOT_COMPUTED, UNKNOWN


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))


def feature_set(name: str, schema: FeatureSchema) -> tuple[list[str], list[tuple[str, str]]]:
    if name == "publisher_only_lr":
        return schema.names_in("publisher"), []
    if name == "claim_conditioned_lr":
        return schema.names, schema.interactions
    raise ValueError(f"unknown logistic feature set '{name}'")


class LogisticModel:
    kind = "logistic"

    def __init__(self, name: str, features: list[str], interactions=None, C: float = 1.0,
                 min_count: int = 1, class_weight=None, max_iter: int = 2000):
        self.name = name
        self.encoder = Encoder(features, interactions, min_count)
        self.C, self.class_weight, self.max_iter = float(C), class_weight, max_iter
        self.coef: np.ndarray | None = None
        self.intercept: float | None = None

    def fit(self, records: list[dict], y, sample_weight=None) -> "LogisticModel":
        y = np.asarray(y, dtype=int)
        if len(set(y.tolist())) < 2:
            raise ValueError(f"{self.name}: training data needs both classes")
        X = self.encoder.fit(records).transform(records)
        clf = LogisticRegression(penalty="l2", C=self.C, solver="lbfgs", max_iter=self.max_iter,
                                 class_weight=self.class_weight)
        clf.fit(X, y, sample_weight=sample_weight)
        self.coef = clf.coef_.ravel().copy()
        self.intercept = float(clf.intercept_[0])
        return self

    def decision(self, records: list[dict], warnings=None) -> np.ndarray:
        if self.coef is None:
            raise RuntimeError(f"{self.name} is not fitted")
        return self.encoder.transform(records, warnings) @ self.coef + self.intercept

    def predict_proba(self, records: list[dict], warnings=None) -> np.ndarray:
        return _sigmoid(self.decision(records, warnings))

    def contributions(self, record: dict, top: int = 3) -> list[tuple[str, float]]:
        x = self.encoder.transform([record])[0]
        contrib = x * self.coef
        idx = [i for i in np.argsort(-np.abs(contrib)) if contrib[i] != 0][:top]
        return [(self.encoder.columns[i], round(float(contrib[i]), 4)) for i in idx]

    def to_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name, "C": self.C, "class_weight": self.class_weight,
                "encoder": self.encoder.to_dict(), "coef": self.coef.tolist(), "intercept": self.intercept}

    @classmethod
    def from_dict(cls, d: dict) -> "LogisticModel":
        m = cls(d["name"], d["encoder"]["features"], d["encoder"]["interactions"], d["C"],
                d["encoder"]["min_count"], d["class_weight"])
        m.encoder = Encoder.from_dict(d["encoder"])
        m.coef, m.intercept = np.asarray(d["coef"], dtype=float), float(d["intercept"])
        return m


class TypePriorModel:
    """P(y=1 | publisher_type) with additive smoothing toward the overall rate."""

    kind = "type_prior"

    def __init__(self, name: str = "type_prior", alpha: float = 1.0):
        self.name, self.alpha = name, float(alpha)
        self.rates: dict[str, float] = {}
        self.base: float | None = None

    def fit(self, records: list[dict], y, sample_weight=None) -> "TypePriorModel":
        y = np.asarray(y, dtype=float)
        self.base = float(y.mean())
        groups: dict[str, list[float]] = {}
        for r, yi in zip(records, y):
            groups.setdefault(r["features"]["publisher_type"], []).append(yi)
        self.rates = {t: (sum(v) + self.alpha * self.base) / (len(v) + self.alpha) for t, v in groups.items()}
        return self

    def predict_proba(self, records: list[dict], warnings=None) -> np.ndarray:
        if self.base is None:
            raise RuntimeError("type prior is not fitted")
        return np.array([self.rates.get(r["features"]["publisher_type"], self.base) for r in records])

    def to_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name, "alpha": self.alpha, "rates": self.rates, "base": self.base}

    @classmethod
    def from_dict(cls, d: dict) -> "TypePriorModel":
        m = cls(d["name"], d["alpha"])
        m.rates, m.base = d["rates"], d["base"]
        return m


class RoleRuleModel:
    """Transparent tiered rules read from a rules file (frozen before labels).

    tier 3  actor_relation == SAME_ENTITY and action_type in self_act_actions
    tier 2  (action_type, publisher_type) in responsibility table and jurisdiction_match == SAME
    tier 1  (action_type, publisher_type) in responsibility table, jurisdiction missing
    tier 0  otherwise
    Score = tier / 3. Ties are expected and reported, not broken.
    """

    kind = "role_rules"

    def __init__(self, rules: dict, name: str = "role_rules"):
        self.name, self.rules = name, rules
        self.self_act = set(rules["self_act_actions"])
        self.table = {(a, p) for a, ps in rules["responsibility"].items() for p in ps}

    def fit(self, records=None, y=None, sample_weight=None) -> "RoleRuleModel":
        return self  # nothing is learned

    def tier(self, record: dict) -> int:
        f = record["features"]
        if f["actor_relation"] == "SAME_ENTITY" and f["action_type"] in self.self_act:
            return 3
        if (f["action_type"], f["publisher_type"]) in self.table:
            if f["jurisdiction_match"] == "SAME":
                return 2
            if f["jurisdiction_match"] in (UNKNOWN, NOT_COMPUTED):
                return 1
        return 0

    def predict_proba(self, records: list[dict], warnings=None) -> np.ndarray:
        return np.array([self.tier(r) / 3.0 for r in records])

    def to_dict(self) -> dict:
        return {"kind": self.kind, "name": self.name, "rules": self.rules}

    @classmethod
    def from_dict(cls, d: dict) -> "RoleRuleModel":
        return cls(d["rules"], d["name"])


def model_from_dict(d: dict):
    return {"logistic": LogisticModel, "type_prior": TypePriorModel, "role_rules": RoleRuleModel}[d["kind"]].from_dict(d)


def load_rules(path) -> dict:
    with open(path, encoding="utf-8") as f:
        rules = json.load(f)
    for key in ("status", "self_act_actions", "responsibility"):
        if key not in rules:
            raise ValueError(f"rules file missing '{key}'")
    return rules
