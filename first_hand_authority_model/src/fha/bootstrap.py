"""Paired bootstrap intervals respecting claim and publisher dependence.

Schemes:
- two_way:   resample claims and publishers independently; a pair's weight
             is (times its claim drawn) x (times its publisher drawn).
             Owen (2007) reports this is mildly conservative for crossed data.
- claim:     resample claims only.
- publisher: resample publishers only.
Resamples where the weighted data lack a positive or a negative are skipped
and counted; a high count means the test set is too small for the claim.
"""

from __future__ import annotations

import numpy as np

SCHEMES = ("two_way", "claim", "publisher")


def resample_weights(claim_ids, pub_ids, scheme: str, rng) -> np.ndarray:
    claim_ids, pub_ids = np.asarray(claim_ids), np.asarray(pub_ids)
    w = np.ones(len(claim_ids))
    if scheme in ("two_way", "claim"):
        uc, inv = np.unique(claim_ids, return_inverse=True)
        counts = np.bincount(rng.integers(0, len(uc), len(uc)), minlength=len(uc))
        w = w * counts[inv]
    if scheme in ("two_way", "publisher"):
        up, inv = np.unique(pub_ids, return_inverse=True)
        counts = np.bincount(rng.integers(0, len(up), len(up)), minlength=len(up))
        w = w * counts[inv]
    if scheme not in SCHEMES:
        raise ValueError(f"scheme must be one of {SCHEMES}")
    return w


def paired_bootstrap(y, scores: dict, claim_ids, pub_ids, metric, comparisons, scheme="two_way",
                     n: int = 2000, seed: int = 0, alpha: float = 0.05) -> dict:
    y = np.asarray(y)
    rng = np.random.default_rng(seed)
    draws = {m: [] for m in scores}
    diffs = {f"{a} - {b}": [] for a, b in comparisons}
    degenerate = 0
    for _ in range(n):
        w = resample_weights(claim_ids, pub_ids, scheme, rng)
        vals = {m: metric(y, s, w) for m, s in scores.items()}
        if any(v is None for v in vals.values()):
            degenerate += 1
            continue
        for m, v in vals.items():
            draws[m].append(v)
        for a, b in comparisons:
            diffs[f"{a} - {b}"].append(vals[a] - vals[b])

    def ci(xs):
        if not xs:
            return {"lo": None, "hi": None}
        lo, hi = np.quantile(xs, [alpha / 2, 1 - alpha / 2])
        return {"lo": float(lo), "hi": float(hi)}

    point = {m: metric(y, s) for m, s in scores.items()}
    return {
        "scheme": scheme, "n_resamples": n, "n_degenerate": degenerate, "seed": seed,
        "models": {m: {"point": point[m], **ci(draws[m])} for m in scores},
        "differences": {k: {"point": (point[k.split(" - ")[0]] - point[k.split(" - ")[1]])
                            if None not in (point[k.split(" - ")[0]], point[k.split(" - ")[1]]) else None,
                            **ci(v)} for k, v in diffs.items()},
    }


def classify_outcome(diff: dict, delta_min, degenerate_share: float, max_degenerate_share: float = 0.05) -> str:
    """Map the primary-difference interval to an outcome class (Section 10.2 of the spec)."""
    if delta_min is None:
        return "NOT_CLASSIFIABLE: minimum meaningful difference (delta_min) not approved"
    if diff["lo"] is None or degenerate_share > max_degenerate_share:
        return "INCONCLUSIVE: too many degenerate bootstrap resamples"
    if diff["hi"] < 0:
        return "HARMFUL"
    if diff["lo"] > 0 and diff["point"] >= delta_min:
        return "SUPPORTED"
    if diff["hi"] < delta_min:
        return "UNSUPPORTED"
    return "INCONCLUSIVE"
