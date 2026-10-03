"""Score the FROZEN held-out rankings against the human claim-level primary-source annotation.

Nothing is retrieved or re-ranked: rankings come from results/source_targeted/rankings_heldout.jsonl.gz
(top-100 per method, frozen run) and results/heldout/rankings_hybrid.jsonl.gz (full hybrid, for the control pool).

  python score_heldout_primary.py check  <filled.csv>   validate the sheet only (reads no gold, no rankings)
  python score_heldout_primary.py selftest              rebuild pools from the frozen files and assert they reproduce
                                                        the published held-out GOLD table (no annotation used)
  python score_heldout_primary.py score  <filled.csv>   primary-source metrics -> results/heldout_primary/

Primary definition (fixed before any label exists; see data/annotations/heldout_primary_package/README.md):
  primary docs of claim c = reachable (non-empty) human-gold docs of c whose publisher key (cand_key, the key used
  in the frozen evaluation) equals a key of an authority the annotator listed for c.
  Claims marked no_identifiable_primary / unclear, and claims with no such doc, are outside the denominator
  (counted and reported).
Metrics: PrimR@1/3/5/10/20, PrimMRR@100, primary claim coverage of the candidate pool before re-ranking.
Tests (exact McNemar + paired bootstrap, Holm across the 4): PrimR@10 G vs A, G vs D, D vs A; primary coverage
F vs size-matched control. Sensitivity: the same excluding confidence=low.
"""
import csv
import gzip
import hashlib
import json
import sys
from pathlib import Path

from authority_resolution import SOCIAL, org_domain, pred_keys
from common import ANNOTATIONS, RESULTS
from source_targeted import cand_key

PKG = ANNOTATIONS / "heldout_primary_package"
FROZEN_RK = RESULTS / "source_targeted" / "rankings_heldout.jsonl.gz"
FROZEN_TABLE = RESULTS / "source_targeted" / "results_heldout.json"
OUT = RESULTS / "heldout_primary"
KS = (1, 3, 5, 10, 20)
METHODS = ["hybrid", "hybrid+generic", "hybrid+heuristic", "hybrid+llm_authority", "targeted", "hybrid+targeted",
           "hybrid+targeted+llm_authority", "control:hybrid_top(100+added)", "ORACLE:targeted+prior"]
A, D, F, G, CTRL = "hybrid", "hybrid+llm_authority", "hybrid+targeted", "hybrid+targeted+llm_authority", \
    "control:hybrid_top(100+added)"
EXCLUDED_SITUATIONS = {"no_identifiable_primary", "unclear"}


# ------------------------------------------------------------------ annotation sheet
def entry_keys(text: str) -> tuple[set[str], list[str]]:
    """Publisher keys for one 'domain_or_account' cell ('cdc.gov; twitter.com/cdcgov'). Returns keys, problems."""
    keys, bad = set(), []
    for tok in [t.strip() for t in text.replace(",", ";").replace(" ", ";").split(";") if t.strip()]:
        if tok.startswith("@"):
            bad.append(f"'{tok}': give platform/handle, e.g. twitter.com/{tok[1:]}")
            continue
        if "." not in tok:
            bad.append(f"'{tok}': not a domain (e.g. cdc.gov) or platform/handle (e.g. twitter.com/cdcgov)")
            continue
        dom = org_domain(tok)
        k = pred_keys({"social_account": tok} if dom in SOCIAL else {"domain": tok})
        if dom in SOCIAL and not any("/" in x for x in k):
            bad.append(f"'{tok}': social platform without a handle")
        keys |= k
        if not k:
            bad.append(f"'{tok}': not a domain or platform/handle")
    return keys, bad


def read_sheet(path):
    manifest = json.load(open(PKG / "MANIFEST.json", encoding="utf-8"))
    with open(path, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    blank = {int(r["claim_id"]): r for r in csv.DictReader(open(PKG / "heldout_primary_annotation.csv", encoding="utf-8-sig"))}
    errors, ann = [], {}
    if [int(r["claim_id"]) for r in rows] != manifest["claim_order"]:
        errors.append("claim IDs / order differ from MANIFEST.json (rows must not be added, removed or re-sorted)")
    for r in rows:
        c = int(r["claim_id"])
        where = f"row {r.get('row')} claim {c}"
        for col in manifest["context_cols"]:
            if c in blank and (r.get(col) or "") != (blank[c].get(col) or ""):
                errors.append(f"{where}: context column '{col}' was edited")
        for col, allowed in manifest["allowed_values"].items():
            v = (r.get(col) or "").strip()
            if v and v not in allowed:
                errors.append(f"{where}: {col}='{v}' not in {allowed}")
        sit = (r.get("authority_situation") or "").strip()
        if not sit:
            errors.append(f"{where}: authority_situation is empty")
        if not (r.get("annotator_id") or "").strip():
            errors.append(f"{where}: annotator_id is empty")
        if not (r.get("confidence") or "").strip():
            errors.append(f"{where}: confidence is empty")
        auths = []
        for i in (1, 2, 3):
            name, dk = (r.get(f"authority_{i}_name") or "").strip(), (r.get(f"authority_{i}_domain_or_account") or "").strip()
            if not (name or dk):
                continue
            keys, bad = entry_keys(dk)
            errors += [f"{where}: authority_{i}: {b}" for b in bad]
            if not keys:
                errors.append(f"{where}: authority_{i} has no usable domain_or_account")
            if not (r.get(f"authority_{i}_type") or "").strip():
                errors.append(f"{where}: authority_{i}_type is empty")
            auths.append({"rank": i, "name": name, "keys": sorted(keys)})
        if sit in ("single_primary", "multiple_legitimate_authorities") and not auths:
            errors.append(f"{where}: situation '{sit}' but no authority listed")
        if sit == "multiple_legitimate_authorities" and len(auths) < 2:
            errors.append(f"{where}: 'multiple_legitimate_authorities' needs >=2 authorities")
        ann[c] = {"situation": sit, "confidence": (r.get("confidence") or "").strip(), "authorities": auths,
                  "keys": set().union(*[set(a["keys"]) for a in auths]) if auths else set(),
                  "annotator": (r.get("annotator_id") or "").strip()}
    return ann, errors


# ------------------------------------------------------------------ frozen rankings and pools
def frozen():
    from validation_heldout import gold_info, load_heldout, load_rk
    R = {}
    with gzip.open(FROZEN_RK, "rt", encoding="utf-8") as fh:
        for x in map(json.loads, fh):
            R.setdefault(x["method"], {})[x["claim_id"]] = [u for u, _ in x["ranked"]]
    hyb_full = {c: [u for u, _ in v] for c, v in load_rk("hybrid", True).items()}
    P = {m: {} for m in R}
    for c in R[A]:
        h100 = set(hyb_full[c][:100])
        fpool = h100 | set(R["targeted"][c])
        added = len(fpool - h100)
        for m in ("bm25", "dense"):
            P[m][c] = set(R[m][c][:100])
        for m in ("hybrid", "hybrid+generic", "hybrid+heuristic", "hybrid+llm_authority"):
            P[m][c] = h100
        P["targeted"][c] = set(R["targeted"][c])
        P[F][c] = P[G][c] = fpool
        P[CTRL][c] = set(hyb_full[c][:100 + added])
        P["ORACLE:targeted+prior"][c] = None      # oracle's targeted pool was not saved -> coverage N/A
    T = gold_info(load_heldout())
    return R, P, T


def metrics(R, P, target, claims, prefix):
    out = {}
    for m in METHODS:
        row = {}
        for k in KS:
            row[f"{prefix}R@{k}"] = round(sum(bool(target[c] & set(R[m][c][:k])) for c in claims) / len(claims), 3)
        rr = [next((1 / i for i, u in enumerate(R[m][c][:100], 1) if u in target[c]), 0.0) for c in claims]
        row[f"{prefix}MRR@100"] = round(sum(rr) / len(claims), 3)
        row[f"{prefix}_claim_coverage"] = ("N/A (pool not saved)" if P[m][claims[0]] is None else
                                           round(sum(bool(target[c] & P[m][c]) for c in claims) / len(claims), 3))
        row["n_claims"] = len(claims)
        out[m] = row
    return out


def selftest():
    R, P, T = frozen()
    gold = {c: T[c]["gold"] for c in T}
    claims = [c for c in T if gold[c]]
    ref = json.load(open(FROZEN_TABLE, encoding="utf-8"))["table"]
    bad = 0
    for m in METHODS:
        mine = metrics(R, P, gold, claims, "Gold")[m]
        for k, v in mine.items():
            if k in ref[m] and v != ref[m][k] and not isinstance(v, str):
                print(f"MISMATCH {m} {k}: {v} vs frozen {ref[m][k]}")
                bad += 1
        pool = [len(P[m][c]) for c in claims] if P[m][claims[0]] is not None else None
        print(f"{m:34s} GoldR@10 {mine['GoldR@10']}  coverage {mine['Gold_claim_coverage']}  (frozen {ref[m]['GoldR@10']}, {ref[m]['Gold_claim_coverage']})")
    mean_pool = sum(len(P[F][c]) for c in P[F]) / len(P[F])
    print(f"mean F pool {mean_pool:.1f} (frozen {ref[F]['mean_pool_size']})")
    assert bad == 0 and round(mean_pool, 1) == ref[F]["mean_pool_size"], "pools do not reproduce the frozen table"
    print("SELFTEST OK: pools and gold metrics reproduce results_heldout.json exactly")


def score(path):
    from validation_heldout import boot_ci, holm, mcnemar
    ann, errors = read_sheet(path)
    if errors:
        print("\n".join(errors[:50]))
        sys.exit(f"{len(errors)} problems: fix the sheet first (python score_heldout_primary.py check {path})")
    R, P, T = frozen()
    here = Path(__file__).parent
    out = {"annotation_file": str(path), "annotation_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
           "scorer_sha256": hashlib.sha256((here / Path(__file__).name).read_bytes()).hexdigest(),
           "frozen_rankings_sha256": hashlib.sha256(FROZEN_RK.read_bytes()).hexdigest(),
           "annotators": sorted({a["annotator"] for a in ann.values()})}
    for tag, keep in (("main", lambda a: True), ("sensitivity_excluding_low_confidence", lambda a: a["confidence"] != "low")):
        prim = {c: {u for u in T[c]["gold"] if cand_key(u) in ann[c]["keys"]}
                if ann[c]["situation"] not in EXCLUDED_SITUATIONS and keep(ann[c]) else set() for c in ann}
        claims = [c for c in ann if prim[c]]
        funnel = {"claims_annotated": len(ann),
                  "situation_counts": {s: sum(a["situation"] == s for a in ann.values()) for s in
                                       ("single_primary", "multiple_legitimate_authorities", "no_identifiable_primary", "unclear")},
                  "excluded_no_or_unclear_primary": sum(a["situation"] in EXCLUDED_SITUATIONS for a in ann.values()),
                  "excluded_low_confidence": sum(not keep(a) for a in ann.values()),
                  "annotated_authority_has_gold_url_any": sum(bool({cand_key(u) for u in T[c]["gold_all"]} & ann[c]["keys"])
                                                              for c in ann if ann[c]["situation"] not in EXCLUDED_SITUATIONS and keep(ann[c])),
                  "claims_with_reachable_primary_doc (denominator)": len(claims),
                  "primary_docs": sum(len(prim[c]) for c in claims)}
        block = {"funnel": funnel}
        if claims:
            block["table"] = metrics(R, P, prim, claims, "Prim")
            hit = lambda m, c, k=10: bool(prim[c] & set(R[m][c][:k]))
            cov = lambda m, c: bool(prim[c] & P[m][c])
            fam = [("PrimR@10 G vs A", [hit(A, c) for c in claims], [hit(G, c) for c in claims]),
                   ("PrimR@10 G vs D", [hit(D, c) for c in claims], [hit(G, c) for c in claims]),
                   ("PrimR@10 D vs A", [hit(A, c) for c in claims], [hit(D, c) for c in claims]),
                   ("PrimCoverage F vs size-matched control", [cov(CTRL, c) for c in claims], [cov(F, c) for c in claims])]
            tests = []
            for name, a, b in fam:
                w, l, p = mcnemar(a, b)
                d, lo, hi = boot_ci(a, b)
                tests.append({"test": name, "n": len(a), "wins": w, "losses": l, "p": round(p, 5), "diff": d, "CI95": [lo, hi]})
            for t, adj in zip(tests, holm([t["p"] for t in tests])):
                t["p_holm"] = round(adj, 5)
            block["tests_holm"] = tests
        out[tag] = block
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT / "primary_results_heldout.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps(out, indent=1))


def check(path):
    ann, errors = read_sheet(path)
    filled = sum(bool(a["situation"]) for a in ann.values())
    print(f"{len(ann)} rows, {filled} with authority_situation; {len(errors)} problems")
    print("\n".join(errors[:100]))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"check": lambda: check(sys.argv[2]), "selftest": selftest, "score": lambda: score(sys.argv[2])}[cmd]()
