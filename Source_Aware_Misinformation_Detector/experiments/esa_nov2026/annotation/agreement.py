"""Inter-annotator agreement for the claim-document RELEVANCE and AUTHORITY labels.

  python experiments/esa_nov2026/annotation/agreement.py A.csv B.csv [C.csv ...] [--out report.json]
  python experiments/esa_nov2026/annotation/agreement.py --selftest

Reports, per label (relevance, authority) and for the binary "authority hit" (relevant/partially relevant AND
primary/authoritative-secondary):
  * observed agreement, Cohen's kappa (2 annotators), quadratic-weighted kappa for the ORDINAL scales,
  * Krippendorff's alpha (nominal; any number of annotators; missing values allowed),
  * confusion matrix (2 annotators).
'cannot_determine' is kept as its own nominal category for kappa/alpha and excluded from the ordinal statistics.
No labels are invented: rows with an empty label are treated as missing.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from itertools import combinations

RELEVANCE = ["relevant", "partially_relevant", "not_relevant", "cannot_determine"]
AUTHORITY = ["primary", "authoritative_secondary", "secondary_derivative", "not_authoritative", "cannot_determine"]
ORDINAL = {"relevance": ["not_relevant", "partially_relevant", "relevant"],
           "authority": ["not_authoritative", "secondary_derivative", "authoritative_secondary", "primary"]}


def authority_hit(rel, auth):
    if not rel or not auth or "cannot_determine" in (rel, auth):
        return None
    return "hit" if rel in ("relevant", "partially_relevant") and auth in ("primary", "authoritative_secondary") else "no_hit"


def cohen_kappa(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    n = len(pairs)
    if n == 0:
        return None, 0
    po = sum(x == y for x, y in pairs) / n
    ca, cb = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    pe = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / n ** 2
    return (1.0 if pe == 1 else (po - pe) / (1 - pe)), n


def weighted_kappa(a, b, scale):
    idx = {c: i for i, c in enumerate(scale)}
    pairs = [(idx[x], idx[y]) for x, y in zip(a, b) if x in idx and y in idx]
    n, k = len(pairs), len(scale)
    if n == 0:
        return None, 0
    w = lambda i, j: (i - j) ** 2 / (k - 1) ** 2
    ca, cb = Counter(i for i, _ in pairs), Counter(j for _, j in pairs)
    do = sum(w(i, j) for i, j in pairs) / n
    de = sum(ca[i] * cb[j] * w(i, j) for i in range(k) for j in range(k)) / n ** 2
    return (1.0 if de == 0 else 1 - do / de), n


def kripp_alpha_nominal(units):
    """units: list of lists of labels (None = missing) for each item, one entry per annotator."""
    vals = [[v for v in u if v is not None] for u in units]
    vals = [v for v in vals if len(v) >= 2]
    if not vals:
        return None
    o = Counter()
    for v in vals:
        m = len(v)
        for i, j in combinations(range(m), 2):
            o[(v[i], v[j])] += 1 / (m - 1)
            o[(v[j], v[i])] += 1 / (m - 1)
    nc = Counter()
    for (c, _), x in o.items():
        nc[c] += x
    n = sum(nc.values())
    do = sum(x for (c, k), x in o.items() if c != k)
    de = sum(nc[c] * nc[k] for c in nc for k in nc if c != k) / (n - 1)
    return 1.0 if de == 0 else 1 - do / de


def load(path):
    with open(path, encoding="utf-8-sig") as fh:
        return {r["pair_id"]: r for r in csv.DictReader(fh)}


def norm(v, allowed):
    v = (v or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not v:
        return None
    if v not in allowed:
        raise ValueError(f"label {v!r} not in {allowed}")
    return v


def report(sheets):
    ids = sorted(set.intersection(*[set(s) for s in sheets]))
    out = {"n_annotators": len(sheets), "n_common_pairs": len(ids)}
    lab = {}
    for name, allowed in (("relevance", RELEVANCE), ("authority", AUTHORITY)):
        lab[name] = [[norm(s[i].get(name), allowed) for s in sheets] for i in ids]
    lab["authority_hit"] = [[authority_hit(lab["relevance"][k][a], lab["authority"][k][a]) for a in range(len(sheets))]
                            for k in range(len(ids))]
    for name, units in lab.items():
        r = {"n_labelled_by_all": sum(all(v is not None for v in u) for u in units),
             "krippendorff_alpha_nominal": kripp_alpha_nominal(units)}
        if len(sheets) == 2:
            a, b = [u[0] for u in units], [u[1] for u in units]
            both = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
            r["observed_agreement"] = (sum(x == y for x, y in both) / len(both)) if both else None
            r["cohen_kappa"], _ = cohen_kappa(a, b)
            if name in ORDINAL:
                r["quadratic_weighted_kappa_ordinal"], r["n_ordinal"] = weighted_kappa(a, b, ORDINAL[name])
            r["confusion_A_rows_B_cols"] = {f"{x} | {y}": c for (x, y), c in sorted(Counter(both).items())}
        out[name] = r
    return out


def selftest():
    # Hand-checkable cases (NOT annotation data).
    k, _ = cohen_kappa(list("aabb"), list("aabb"))
    assert abs(k - 1) < 1e-12
    k, _ = cohen_kappa(list("ab"), list("ba"))
    assert abs(k - (-1)) < 1e-12
    # Classic example: yy=35, yn=15, ny=15, nn=35 -> po = 0.7, pe = 0.5, kappa = 0.4
    a = ["y"] * 50 + ["n"] * 50
    b = ["y"] * 35 + ["n"] * 15 + ["y"] * 15 + ["n"] * 35
    k, _ = cohen_kappa(a, b)
    assert abs(k - 0.4) < 1e-12, k
    # Krippendorff nominal: perfect agreement -> 1 ; two annotators equals Cohen-like scale
    assert kripp_alpha_nominal([["x", "x"], ["y", "y"], ["x", "x", None]]) == 1.0
    al = kripp_alpha_nominal([[x, y] for x, y in zip(a, b)])
    assert 0.39 < al < 0.41, al  # alpha ~ kappa for large n with equal marginals (0.4030)
    wk, _ = weighted_kappa(["not_relevant", "relevant"], ["not_relevant", "relevant"], ORDINAL["relevance"])
    assert wk == 1.0
    assert authority_hit("relevant", "primary") == "hit" and authority_hit("not_relevant", "primary") == "no_hit"
    assert authority_hit("relevant", "cannot_determine") is None
    print("agreement.py selftest: PASS (hand-checkable fixtures only; not annotation data)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    outp = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    if outp in args:
        args.remove(outp)
    if len(args) < 2:
        sys.exit(__doc__)
    rep = report([load(p) for p in args])
    print(json.dumps(rep, indent=1))
    if outp:
        json.dump(rep, open(outp, "w", encoding="utf-8"), indent=1)
