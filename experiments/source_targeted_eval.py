"""Evaluation of source-targeted retrieval + the ablation A-H (docs/source_targeted_preregistration.md).

  python source_targeted_eval.py devgrid   design grid on the 120 DEVELOPMENT claims only
  python source_targeted_eval.py dev       frozen config on development claims (exploratory)
  python source_targeted_eval.py heldout   frozen config on the 200 held-out claims (run once)

Methods (every ranking starts from the claim; gold is read only in scoring):
  bm25, dense, hybrid                   frozen relevance rankings (query = claim)
  hybrid+generic                        frozen: generic credibility prior, lambda=1, hybrid top-100
  hybrid+heuristic                      'full' heuristic prior (authority_retrieval), same lambda/pool
  hybrid+llm_authority                  frozen: predicted top-3 publisher keys, lambda=1, top-100
  targeted                              source-targeted retrieval only (predicted authority)
  hybrid+targeted                       RRF fusion of hybrid top-100 and targeted top-M
  hybrid+targeted+llm_authority         the fused pool re-ranked with the predicted-authority prior
  control:hybrid_top(100+added)         SIZE-MATCHED control: hybrid top-(100 + #docs targeted adds)
  ORACLE:targeted+prior                 same pipeline with gold-derived authority keys (upper bound only)

Candidate pool (coverage is measured on it, before any re-ranking):
  bm25/dense/hybrid top-100; targeted top-M; hybrid top-100 U targeted top-M; control top-(100+added).
"""
import csv
import gzip
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from common import ANNOTATIONS, RESULTS, load_sample, normalize_url
from source_targeted import (ClaimIndex, cand_key, fuse, make_queries, oracle_candidates,
                             primary_authority_candidates, rerank_prior, targeted_rank)

OUT = RESULTS / "source_targeted"
KS = (1, 3, 5, 10, 20, 50, 100)
LAMBDA, POOL = 1.0, 100

# ------------------------------------------------ FROZEN CONFIG (set from devgrid; see preregistration)
FROZEN = {"text_mode": "claim", "order": "authority", "m": 10}
# -------------------------------------------------------------------------------------------------


def load_split(split):
    import validation_heldout as V
    heldout = split == "heldout"
    sample = V.load_heldout() if heldout else load_sample()
    preds_raw = {}
    raw = V.PRED_RAW if heldout else __import__("authority_resolution").RAW
    for line in open(raw, encoding="utf-8"):
        x = json.loads(line)
        if x.get("cond") == "L+Wctx" and x.get("pred"):
            preds_raw[int(x["claim_id"])] = x["pred"]
    rk = {m: V.load_rk(m, heldout) for m in ("bm25", "dense", "hybrid")}
    return sample, preds_raw, rk


def gold_truth(split, sample):
    """Gold is read HERE only (scoring). Also returns oracle keys (labelled, diagnostic)."""
    import validation_heldout as V
    from authority_resolution import load_targets
    roles = None
    if split != "heldout":
        roles = {}
        with open(ANNOTATIONS / "source_roles.csv", encoding="utf-8") as fh:
            for x in csv.DictReader(fh):
                roles[(int(x["claim_id"]), normalize_url(x["evidence_url"]))] = x["source_role"]
    T = V.gold_info(sample, roles)
    if split == "heldout":
        oracle = {c: T[c]["gold_keys"] for c in T}          # publishers of ALL human gold URLs
        oracle_label = "ORACLE (publishers of all human gold URLs; leaks by design)"
    else:
        tg, _, _ = load_targets()
        oracle = {c: set(tg.get(c, set())) for c in T}      # pilot-primary publishers
        oracle_label = "ORACLE (publishers of pilot-primary gold URLs; leaks by design)"
    return T, oracle, oracle_label


_IDX = {}


def build(sample, preds, rk, cfg, oracle=None, want=("all",)):
    """All method rankings + candidate pools. `oracle` only feeds the ORACLE method."""
    from authority_retrieval import claim_entities, entity_keys, full_prior, generic_prior
    from baseline_retrieval import retrieval_corpus
    from validation_heldout import rerank
    R, P, info = {}, {}, {}

    def put(m, c, ranking, pool):
        R.setdefault(m, {})[c] = ranking
        P.setdefault(m, {})[c] = pool

    for r in sample:
        c = int(r["claim_id"])
        pred = preds.get(c)
        pkeys = set().union(*[set(a["keys"]) for a in primary_authority_candidates(pred)]) if pred else set()
        prior = lambda u, k=pkeys: float(cand_key(u) in k)
        hyb = rk["hybrid"][c]
        for m in ("bm25", "dense", "hybrid"):
            put(m, c, rk[m][c], {u for u, _ in rk[m][c][:POOL]})
        hpool = {u for u, _ in hyb[:POOL]}
        put("hybrid+generic", c, rerank(hyb, generic_prior), hpool)
        if "heuristic" in want or "all" in want:
            ek, iso = entity_keys(claim_entities(r)), r.get("location_ISO_code")
            put("hybrid+heuristic", c, rerank(hyb, lambda u: full_prior(u, ek, iso)), hpool)
        put("hybrid+llm_authority", c, rerank(hyb, prior), hpool)

        if c not in _IDX:
            _IDX[c] = ClaimIndex(retrieval_corpus(c))
        idx = _IDX[c]
        qs = make_queries(r["claim"], pred, cfg["text_mode"])
        tr = targeted_rank(idx, qs, rk["dense"][c], cfg["order"])
        tpool = tr[:cfg["m"]] if cfg["m"] else tr
        put("targeted", c, tpool, {u for u, _ in tpool})
        fused = fuse(hyb, tr, POOL, cfg["m"])
        put("hybrid+targeted", c, fused, {u for u, _ in fused})
        put("hybrid+targeted+llm_authority", c, rerank_prior(fused, prior, LAMBDA), {u for u, _ in fused})
        added = len({u for u, _ in fused} - hpool)
        put("control:hybrid_top(100+added)", c, hyb, {u for u, _ in hyb[:POOL + added]})
        if oracle is not None:
            ok = oracle.get(c, set())
            oq = make_queries(r["claim"], pred, cfg["text_mode"], candidates=oracle_candidates(ok))
            otr = targeted_rank(idx, oq, rk["dense"][c], cfg["order"])
            of = fuse(hyb, otr, POOL, cfg["m"])
            put("ORACLE:targeted+prior", c, rerank_prior(of, lambda u, k=ok: float(cand_key(u) in k), LAMBDA),
                {u for u, _ in of})
        info[c] = {"queries": qs, "n_targeted_total": len(tr), "n_added": added,
                   "authority_candidates": primary_authority_candidates(pred),
                   "authority_situation": (pred or {}).get("authority_situation")}
    return R, P, info


def score(R, P, T, claims_key):
    out = {}
    for m in R:
        row = {}
        for key, name in (("gold", "Gold"), ("prim", "Prim")):
            cl = [c for c in T if T[c][key]]
            if not cl:
                continue
            for k in KS:
                row[f"{name}R@{k}"] = round(sum(bool(T[c][key] & {u for u, _ in R[m][c][:k]}) for c in cl) / len(cl), 3)
            rr = []
            for c in cl:
                v = 0.0
                for i, (u, _) in enumerate(R[m][c][:100], 1):
                    if u in T[c][key]:
                        v = 1 / i
                        break
                rr.append(v)
            row[f"{name}MRR@100"] = round(sum(rr) / len(cl), 3)
            row[f"{name}_claim_coverage"] = round(sum(bool(T[c][key] & P[m][c]) for c in cl) / len(cl), 3)
            ndocs = sum(len(T[c][key]) for c in cl)
            row[f"{name}_doc_coverage"] = round(sum(len(T[c][key] & P[m][c]) for c in cl) / ndocs, 3)
            row[f"n_{key}_claims"], row[f"n_{key}_docs"] = len(cl), ndocs
        row["mean_pool_size"] = round(sum(len(P[m][c]) for c in P[m]) / len(P[m]), 1)
        out[m] = row
    return out


def mcnemar(a, b):
    from validation_heldout import mcnemar as _m
    return _m(a, b)


def devgrid():
    sample, preds, rk = load_split("dev")
    T, _, _ = gold_truth("dev", sample)
    rows = []
    for tm in ("claim", "claim+entity", "fact+entity"):
        for order in ("rrf", "authority"):
            for m in (10, 20, 50):
                cfg = {"text_mode": tm, "order": order, "m": m}
                R, P, _ = build(sample, preds, rk, cfg, want=("grid",))
                s = score({k: R[k] for k in ("targeted", "hybrid+targeted", "hybrid+targeted+llm_authority")},
                          {k: P[k] for k in ("targeted", "hybrid+targeted", "hybrid+targeted+llm_authority")}, T, None)
                g = s["hybrid+targeted+llm_authority"]
                crit = round((g["GoldR@10"] + g["PrimR@10"]) / 2, 4)
                rows.append({**cfg, "criterion(G GoldR@10+PrimR@10)/2": crit,
                             **{f"G_{k}": v for k, v in g.items() if k.startswith(("Gold", "Prim"))},
                             "F_GoldR@10": s["hybrid+targeted"]["GoldR@10"], "E_PrimR@10": s["targeted"]["PrimR@10"],
                             "pool": g["mean_pool_size"]})
                print(json.dumps(rows[-1]), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "devgrid.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    best = max(rows, key=lambda x: (x["criterion(G GoldR@10+PrimR@10)/2"], -x["m"]))
    print("BEST (dev):", {k: best[k] for k in ("text_mode", "order", "m")})


def run(split):
    sample, preds, rk = load_split(split)
    T, oracle, olabel = gold_truth(split, sample)
    R, P, info = build(sample, preds, rk, FROZEN, oracle)
    table = score(R, P, T, None)
    gold_c = [c for c in T if T[c]["gold"]]
    tests = {}
    hit = lambda m, c, k: bool(T[c]["gold"] & {u for u, _ in R[m][c][:k]})
    cov = lambda m, c: bool(T[c]["gold"] & P[m][c])
    fam = [("GoldCoverage: hybrid+targeted vs size-matched control", [cov("control:hybrid_top(100+added)", c) for c in gold_c],
            [cov("hybrid+targeted", c) for c in gold_c]),
           ("GoldR@10: G vs D (hybrid+llm_authority)", [hit("hybrid+llm_authority", c, 10) for c in gold_c],
            [hit("hybrid+targeted+llm_authority", c, 10) for c in gold_c]),
           ("GoldR@10: G vs A (hybrid)", [hit("hybrid", c, 10) for c in gold_c],
            [hit("hybrid+targeted+llm_authority", c, 10) for c in gold_c])]
    from validation_heldout import boot_ci, holm
    res = []
    for name, a, b in fam:
        w, l, p = mcnemar(a, b)
        d, lo, hi = boot_ci(a, b)
        res.append({"test": name, "n": len(a), "wins": w, "losses": l, "p": round(p, 5), "diff": d, "CI95": [lo, hi]})
    for x, a in zip(res, holm([x["p"] for x in res])):
        x["p_holm"] = round(a, 5)
    tests["preregistered_family_holm"] = res
    # descriptive extra comparisons at other K
    extra = {}
    for k in (5, 20, 50):
        for ref in ("hybrid", "hybrid+llm_authority"):
            w, l, p = mcnemar([hit(ref, c, k) for c in gold_c], [hit("hybrid+targeted+llm_authority", c, k) for c in gold_c])
            extra[f"GoldR@{k} G vs {ref}"] = f"+{w}/-{l} p={p:.4f} (uncorrected, descriptive)"
    tests["descriptive"] = extra
    if any(T[c]["prim"] for c in T):
        prim_c = [c for c in T if T[c]["prim"]]
        ph = lambda m, c, k: bool(T[c]["prim"] & {u for u, _ in R[m][c][:k]})
        tests["primary_descriptive"] = {
            f"PrimR@{k} G vs {ref}": "+%d/-%d p=%.4f" % mcnemar([ph(ref, c, k) for c in prim_c],
                                                                [ph("hybrid+targeted+llm_authority", c, k) for c in prim_c])
            for k in (5, 10, 20) for ref in ("hybrid", "hybrid+llm_authority")}
        pc = lambda m: [bool(T[c]["prim"] & P[m][c]) for c in prim_c]
        tests["primary_descriptive"]["PrimCoverage hybrid+targeted vs control"] = \
            "+%d/-%d p=%.4f" % mcnemar(pc("control:hybrid_top(100+added)"), pc("hybrid+targeted"))
    # per-claim rows for error analysis
    per = []
    for r in sample:
        c = int(r["claim_id"])
        tgt = T[c]["prim"] or T[c]["gold"]
        def br(m, target=tgt):
            for i, (u, _) in enumerate(R[m][c], 1):
                if u in target:
                    return i
            return None
        pk = set().union(*[set(a["keys"]) for a in info[c]["authority_candidates"]]) if info[c]["authority_candidates"] else set()
        per.append({"claim_id": c, "label": T[c]["label"], "claim": r["claim"], "speaker": r.get("speaker_or_entity"),
                    "n_gold_reachable": len(T[c]["gold"]), "n_prim_reachable": len(T[c]["prim"]),
                    "target_used": "primary" if T[c]["prim"] else "gold",
                    "pred_authorities": " | ".join(f"{a['publisher']} {a['keys']}" for a in info[c]["authority_candidates"]),
                    "authority_situation": info[c]["authority_situation"],
                    "gold_keys": " ".join(sorted(T[c]["gold_keys"])),
                    "pred_hits_gold_publisher": bool(pk & T[c]["gold_keys"]),
                    "target_publishers": " ".join(sorted({cand_key(u) for u in tgt})),
                    "n_targeted_docs": info[c]["n_targeted_total"], "n_added": info[c]["n_added"],
                    **{f"rank_{m}": br(m) for m in ("hybrid", "hybrid+llm_authority", "targeted", "hybrid+targeted",
                                                     "hybrid+targeted+llm_authority", "ORACLE:targeted+prior")},
                    "rank_in_full_hybrid": br("hybrid"),
                    "top1_G": R["hybrid+targeted+llm_authority"][c][0][0] if R["hybrid+targeted+llm_authority"][c] else "",
                    "targeted_query": info[c]["queries"][0]["web_query"][:300] if info[c]["queries"] else ""})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"per_claim_{split}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(per[0]))
        w.writeheader()
        w.writerows(per)
    with gzip.open(OUT / f"rankings_{split}.jsonl.gz", "wt", encoding="utf-8") as fh:
        for m in R:
            for c in R[m]:
                fh.write(json.dumps({"method": m, "claim_id": c, "ranked": R[m][c][:100]}) + "\n")
    sit = Counter(info[c]["authority_situation"] for c in info)
    ncand = Counter(len(info[c]["authority_candidates"]) for c in info)
    here = Path(__file__).parent
    out = {"split": split, "config": FROZEN, "lambda": LAMBDA, "pool": POOL, "oracle_label": olabel,
           "script_sha256": {f: hashlib.sha256((here / f).read_bytes()).hexdigest()
                             for f in ("source_targeted.py", "source_targeted_eval.py")},
           "table": table, "tests": tests, "authority_situation": sit, "n_authority_candidates": ncand,
           "primary_available": any(T[c]["prim"] for c in T)}
    json.dump(out, open(OUT / f"results_{split}.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    {"devgrid": devgrid, "dev": lambda: run("dev"), "heldout": lambda: run("heldout")}[sys.argv[1]]()
