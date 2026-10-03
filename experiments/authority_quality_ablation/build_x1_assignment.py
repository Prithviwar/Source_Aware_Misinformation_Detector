"""Phase 2 step 1: build the X1 assignment (matched mismatched-authority perturbation). EXPLORATORY.

Uses only: frozen predictions, the frozen hybrid top-100 pool (membership and document counts), the
existing claim-independent generic-prior categories, and reachable human-gold publishers (for exclusion
rule E2 only). It uses no reranked ranks, no R@K, no MRR and no X1 result. Writes
results/authority_quality_ablation_phase2/x1_assignment.csv and its SHA-256, makes both read-only, and
refuses to overwrite.

Analysis set S: gold-reachable claims whose D1 publisher (top-1 predicted keys) has >=1 doc in the pool.
Eligibility for X1 (all must hold):
  E1 publisher key has >=1 document in the claim's frozen hybrid top-100 pool
  E2 publisher is not a reachable human-gold publisher of the claim
  E3 publisher is not among the claim's predicted top-3 publisher keys
  E4 publisher has the same generic-prior category as the claim's D1 publisher
Selection: eligible publisher whose pool document count is closest to D1's; ties broken by
random.Random(2029 * 100000 + claim_id).choice(sorted(tied_keys)).
"""
import csv
import hashlib
import os
import random
import stat
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
import source_targeted_eval as STE  # noqa: E402
from authority_retrieval import generic_prior  # noqa: E402
from source_targeted import cand_key, primary_authority_candidates  # noqa: E402

SEED_X = 2029
CAT = {1.0: "government/intergovernmental", 0.8: "academic", 0.6: "major news", 0.5: "reference",
       0.3: "other/unknown", 0.2: "platform/blog"}
OUT = ROOT / "results" / "authority_quality_ablation_phase2"
DST = OUT / "x1_assignment.csv"


def main():
    if DST.exists():
        sys.exit(f"REFUSED: {DST} exists; the assignment is never rebuilt.")
    sample, preds, rk = STE.load_split("heldout")
    T, _, _ = STE.gold_truth("heldout", sample)
    rows = []
    for c in sorted(c for c in T if T[c]["gold"]):
        cands = primary_authority_candidates(preds.get(c))
        top1 = set(cands[0]["keys"]) if cands else set()
        top3 = set().union(*[set(a["keys"]) for a in cands]) if cands else set()
        pool = rk["hybrid"][c][:100]
        d1_docs = sum(cand_key(u) in top1 for u, _ in pool)
        if d1_docs == 0:
            continue                                            # not in S: D1 cannot change the ranking
        d1_url = next(u for u, _ in pool if cand_key(u) in top1)
        d1_cat = CAT[generic_prior(d1_url)]
        gold_pub = {cand_key(u) for u in T[c]["gold"]}          # reachable human-gold publishers (E2)
        pubs = {}
        for u, _ in pool:
            k = cand_key(u)
            pubs.setdefault(k, {"n": 0, "url": u})
            pubs[k]["n"] += 1
        elig = {k: v for k, v in pubs.items()
                if k not in gold_pub and k not in top3 and CAT[generic_prior(v["url"])] == d1_cat}
        if not elig:
            rows.append({"claim_id": c, "in_S": True, "x1_key": "", "note": "no eligible publisher"})
            continue
        best = min(abs(v["n"] - d1_docs) for v in elig.values())
        tied = sorted(k for k, v in elig.items() if abs(v["n"] - d1_docs) == best)
        x1 = random.Random(SEED_X * 100000 + c).choice(tied)
        rows.append({"claim_id": c, "in_S": True, "d1_keys": " ".join(sorted(top1)), "d1_category": d1_cat,
                     "d1_pool_docs": d1_docs, "x1_key": x1, "x1_category": CAT[generic_prior(elig[x1]["url"])],
                     "x1_pool_docs": elig[x1]["n"], "doc_gap": elig[x1]["n"] - d1_docs, "abs_doc_gap": best,
                     "tie_size": len(tied), "n_eligible": len(elig),
                     "x1_matches_nonreachable_gold_key": x1 in set(T[c]["gold_keys"]),
                     "note": ""})
    OUT.mkdir(parents=True, exist_ok=True)
    fields = list(max(rows, key=len).keys())
    with open(DST, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    digest = hashlib.sha256(DST.read_bytes()).hexdigest()
    (OUT / "x1_assignment.sha256").write_text(f"{digest}  x1_assignment.csv\n", encoding="utf-8")
    for p in (DST, OUT / "x1_assignment.sha256"):
        os.chmod(p, stat.S_IREAD)                               # read-only: cannot change after scoring begins
    print(f"S = {len(rows)} claims | assigned {sum(bool(r['x1_key']) for r in rows)} | SHA-256 {digest}")


if __name__ == "__main__":
    main()
