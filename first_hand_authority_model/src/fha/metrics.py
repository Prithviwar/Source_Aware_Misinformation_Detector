"""Evaluation metrics. All accept optional sample weights (used by the bootstrap)."""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from sklearn.metrics import average_precision_score, roc_auc_score

EPS = 1e-12


def _has_both(y, w=None) -> bool:
    y = np.asarray(y)
    w = np.ones_like(y, dtype=float) if w is None else np.asarray(w)
    return (w[y == 1].sum() > 0) and (w[y == 0].sum() > 0)


def auprc(y, s, w=None):
    return float(average_precision_score(y, s, sample_weight=w)) if _has_both(y, w) else None


def auroc(y, s, w=None):
    return float(roc_auc_score(y, s, sample_weight=w)) if _has_both(y, w) else None


def brier(y, p, w=None):
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.average((p - y) ** 2, weights=w))


def log_loss(y, p, w=None):
    y, p = np.asarray(y, float), np.clip(np.asarray(p, float), 1e-7, 1 - 1e-7)
    return float(np.average(-(y * np.log(p) + (1 - y) * np.log(1 - p)), weights=w))


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-7, 1 - 1e-7)
    return np.log(p / (1 - p))


def calibration_slope_intercept(y, p):
    """Slope: logistic fit of y on logit(p). Intercept: calibration-in-the-large
    with logit(p) as an offset (slope fixed at 1). Ideal values are 1 and 0."""
    y = np.asarray(y, float)
    if not _has_both(y):
        return {"slope": None, "intercept": None}
    z = _logit(p)

    def nll(a, b):
        q = 1 / (1 + np.exp(-(a + b * z)))
        q = np.clip(q, EPS, 1 - EPS)
        return -np.sum(y * np.log(q) + (1 - y) * np.log(1 - q))

    slope = minimize(lambda t: nll(t[0], t[1]), x0=[0.0, 1.0], method="BFGS").x[1]
    intercept = minimize_scalar(lambda a: nll(a, 1.0), bounds=(-20, 20), method="bounded").x
    return {"slope": float(slope), "intercept": float(intercept)}


def reliability_table(y, p, bins: int = 10):
    """Equal-count bins: mean predicted vs observed rate. Descriptive only."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    order = np.argsort(p)
    rows = []
    for chunk in np.array_split(order, min(bins, len(order))):
        if len(chunk):
            rows.append({"n": int(len(chunk)), "mean_pred": float(p[chunk].mean()), "obs_rate": float(y[chunk].mean())})
    return rows


def _by_claim(claim_ids, pair_ids, y, s):
    groups = defaultdict(list)
    for c, pid, yi, si in zip(claim_ids, pair_ids, y, s):
        groups[c].append((-float(si), pid, int(yi)))
    for c in groups:
        groups[c].sort()  # score desc, then pair_id: deterministic tie-break (documented)
    return groups


def ranking_metrics(claim_ids, pair_ids, y, s, ks=(1, 3)):
    """NDCG@k and hit@k over claims with at least one positive candidate.
    Claims with no positive are counted, not scored."""
    groups = _by_claim(claim_ids, pair_ids, y, s)
    out = {"claims_with_positive": 0, "claims_without_positive": 0}
    sums = {f"ndcg@{k}": 0.0 for k in ks} | {f"hit@{k}": 0.0 for k in ks}
    tied = 0
    for items in groups.values():
        ys = [it[2] for it in items]
        scores = [it[0] for it in items]
        tied += int(len(set(scores)) < len(scores))
        if sum(ys) == 0:
            out["claims_without_positive"] += 1
            continue
        out["claims_with_positive"] += 1
        ideal = sorted(ys, reverse=True)
        for k in ks:
            dcg = sum(yi / np.log2(i + 2) for i, yi in enumerate(ys[:k]))
            idcg = sum(yi / np.log2(i + 2) for i, yi in enumerate(ideal[:k]))
            sums[f"ndcg@{k}"] += dcg / idcg
            sums[f"hit@{k}"] += float(any(ys[:k]))
    n = out["claims_with_positive"]
    out.update({k: (v / n if n else None) for k, v in sums.items()})
    out["claims_with_tied_scores"] = tied
    return out


def within_publisher_auroc(pub_ids, y, s):
    """Mean AUROC over publishers labelled positive for some claims and negative
    for others. A score constant per publisher gives exactly 0.5."""
    groups = defaultdict(lambda: ([], []))
    for p, yi, si in zip(pub_ids, y, s):
        groups[p][0].append(int(yi))
        groups[p][1].append(float(si))
    per = {p: float(roc_auc_score(ys, ss)) for p, (ys, ss) in groups.items() if 0 < sum(ys) < len(ys)}
    return {"mean": float(np.mean(list(per.values()))) if per else None, "n_publishers": len(per), "per_publisher": per}


def within_publisher_ci(per_publisher: dict, n: int = 2000, seed: int = 0, alpha: float = 0.05):
    """Percentile interval for the mean within-publisher AUROC, resampling publishers."""
    vals = np.array(list(per_publisher.values()))
    if len(vals) < 2:
        return {"lo": None, "hi": None, "n_publishers": int(len(vals))}
    rng = np.random.default_rng(seed)
    means = vals[rng.integers(0, len(vals), (n, len(vals)))].mean(axis=1)
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return {"lo": float(lo), "hi": float(hi), "n_publishers": int(len(vals))}


def by_category(categories, y, s, min_pairs: int = 1):
    """AUPRC and AUROC within each category (e.g. publisher type). Categories
    lacking a positive or a negative get None; counts are always reported."""
    groups = defaultdict(list)
    for c, yi, si in zip(categories, y, s):
        groups[c].append((yi, si))
    out = {}
    for c in sorted(groups):
        ys, ss = zip(*groups[c])
        out[c] = {"n": len(ys), "positives": int(sum(ys)),
                  "auprc": auprc(ys, ss) if len(ys) >= min_pairs else None,
                  "auroc": auroc(ys, ss) if len(ys) >= min_pairs else None}
    return out


def best_f1_threshold(y, p):
    """Threshold maximising F1; chosen on validation data only."""
    y, p = np.asarray(y), np.asarray(p)
    best, best_t = -1.0, 0.5
    for t in np.unique(p):
        pred = p >= t
        tp = np.sum(pred & (y == 1))
        fp = np.sum(pred & (y == 0))
        fn = np.sum(~pred & (y == 1))
        f1 = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
        if f1 > best:
            best, best_t = f1, float(t)
    return best_t
