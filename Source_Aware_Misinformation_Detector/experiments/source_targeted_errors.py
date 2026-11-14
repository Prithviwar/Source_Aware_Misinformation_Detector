"""Error analysis of the frozen source-targeted run (read-only: re-uses saved rankings, nothing is re-ranked).

  python source_targeted_errors.py heldout|dev

Reads results/source_targeted/rankings_<split>.jsonl.gz (top-100 per method, written by source_targeted_eval.py),
the frozen hybrid full ranking, the frozen L+Wctx predictions, and gold (scoring only).
G = hybrid+targeted+llm_authority (proposed pipeline), D = hybrid+llm_authority.
"""
import csv
import gzip
import json
import sys
from collections import Counter

from source_targeted import cand_key, primary_authority_candidates
from source_targeted_eval import OUT, gold_truth, load_split

G, D, F = "hybrid+targeted+llm_authority", "hybrid+llm_authority", "hybrid+targeted"


def main(split):
    sample, preds, rk = load_split(split)
    T, _, _ = gold_truth(split, sample)
    R = {}
    with gzip.open(OUT / f"rankings_{split}.jsonl.gz", "rt", encoding="utf-8") as fh:
        for x in map(json.loads, fh):
            R.setdefault(x["method"], {})[x["claim_id"]] = [u for u, _ in x["ranked"]]
    hyb_full = {c: [u for u, _ in v] for c, v in rk["hybrid"].items()}

    def best(lst, tgt):
        return next((i for i, u in enumerate(lst, 1) if u in tgt), None)

    rows, ex = [], {}
    for r in sample:
        c = int(r["claim_id"])
        pred = preds.get(c)
        cands = primary_authority_candidates(pred) if pred else []
        pk = set().union(*[set(a["keys"]) for a in cands]) if cands else set()
        gold, prim = T[c]["gold"], T[c]["prim"]
        row = {"claim_id": c, "label": T[c]["label"], "n_gold_web": len(T[c]["gold_all"]), "n_gold_reachable": len(gold),
               "n_gold_empty": len(T[c]["gold_all"] - gold), "n_prim_reachable": len(prim),
               "authority_situation": (pred or {}).get("authority_situation"),
               "n_gold_publishers": len({cand_key(u) for u in gold})}
        if gold:
            auth_gold = {u for u in gold if cand_key(u) in pk}        # reachable gold docs from a predicted publisher
            row.update({
                "auth_any_gold_key": bool(pk & T[c]["gold_keys"]),
                "auth_reachable_gold": bool(auth_gold),
                "rank_full_hybrid": best(hyb_full[c], gold),
                "rank_D": best(R[D][c], gold), "rank_G": best(R[G][c], gold),
                "authgold_in_F_pool": bool(auth_gold & set(R[F][c])),
                "authgold_rank_G": best(R[G][c], auth_gold) if auth_gold else None,
                "G_top10_from_pred_publisher": sum(cand_key(u) in pk for u in R[G][c][:10]),
                "G_top10_added_by_targeting": sum(u not in set(hyb_full[c][:100]) for u in R[G][c][:10]),
            })
            if prim:
                sec = gold - prim
                row["rank_G_prim"], row["rank_G_nonprim"] = best(R[G][c], prim), best(R[G][c], sec) if sec else None
                row["rank_full_hybrid_prim"] = best(hyb_full[c], prim)
        rows.append(row)

    g = [x for x in rows if x["n_gold_reachable"]]
    hit = lambda x, k="rank_G": x[k] is not None and x[k] <= 10
    out = {"split": split, "n_claims": len(rows), "n_gold_reachable_claims": len(g)}

    # 1. authority correct, retrieval fails
    ac = [x for x in g if x["auth_reachable_gold"]]
    acf = [x for x in ac if not hit(x)]
    out["1_authority_correct_retrieval_fails"] = {
        "def": "a reachable gold doc is from a predicted top-3 publisher, but G has no gold in top-10",
        "authority_correct_reachable": len(ac), "G_hit@10_among_them": sum(hit(x) for x in ac),
        "fails": len(acf),
        "fails_authgold_not_in_F_pool": sum(not x["authgold_in_F_pool"] for x in acf),
        "fails_authgold_in_pool_ranked_below_10": sum(x["authgold_in_F_pool"] for x in acf),
        "median_G_top10_from_pred_publisher_in_fails": sorted(x["G_top10_from_pred_publisher"] for x in acf)[len(acf) // 2] if acf else None,
        "examples": [x["claim_id"] for x in acf[:8]]}
    # 2. authority wrong
    aw = [x for x in g if not x["auth_any_gold_key"]]
    out["2_authority_wrong"] = {
        "def": "no predicted top-3 publisher key equals any human-gold publisher (lower bound: gold incl. news/fact-check)",
        "n": len(aw), "G_hit@10": sum(hit(x) for x in aw), "D_hit@10": sum(hit(x, "rank_D") for x in aw),
        "hybrid_hit@10": sum(x["rank_full_hybrid"] is not None and x["rank_full_hybrid"] <= 10 for x in aw),
        "authority_matches_only_empty_gold": sum(x["auth_any_gold_key"] and not x["auth_reachable_gold"] for x in g)}
    # 3. outside ordinary pool
    op = [x for x in g if x["rank_full_hybrid"] is None or x["rank_full_hybrid"] > 100]
    out["3_gold_outside_hybrid_top100"] = {
        "n": len(op), "of": len(g),
        "gold_in_G_top100_after_targeting": sum(x["rank_G"] is not None for x in op),
        "then_G_hit@10": sum(hit(x) for x in op),
        "authority_correct_among_them": sum(x["auth_reachable_gold"] for x in op)}
    if split == "dev":
        pr = [x for x in g if x["n_prim_reachable"]]
        opp = [x for x in pr if x["rank_full_hybrid_prim"] is None or x["rank_full_hybrid_prim"] > 100]
        out["3b_primary_outside_hybrid_top100"] = {"n": len(opp), "of": len(pr),
                                                  "brought_into_G_top100": sum(x["rank_G_prim"] is not None for x in opp),
                                                  "then_G_prim_hit@10": sum(hit(x, "rank_G_prim") for x in opp)}
        both = [x for x in pr if x.get("rank_G_nonprim") is not None]
        rank_or = lambda v: v if v is not None else 10**6
        out["4_secondary_outranks_primary"] = {
            "def": "claims with reachable pilot-primary AND non-primary gold; best non-primary gold ranks above best primary in G",
            "n_claims_with_both": len(both),
            "secondary_above_primary": sum(rank_or(x["rank_G_nonprim"]) < rank_or(x["rank_G_prim"]) for x in both),
            "primary_above_secondary": sum(rank_or(x["rank_G_prim"]) < rank_or(x["rank_G_nonprim"]) for x in both)}
    else:
        out["4_secondary_outranks_primary"] = "N/A: no held-out primary annotations (heldout_annotator_template.csv is unfilled)"
    # 5. multiple authorities
    by = {}
    for s in ("multiple_legitimate_authorities", "single_clear_authority", "no_clear_authority"):
        xs = [x for x in g if x["authority_situation"] == s]
        by[s] = {"n": len(xs), "G_hit@10": sum(hit(x) for x in xs), "D_hit@10": sum(hit(x, "rank_D") for x in xs),
                 "authority_correct": sum(x["auth_any_gold_key"] for x in xs)}
    out["5_multiple_legitimate_authorities"] = {
        "by_llm_authority_situation": by,
        "claims_with_>=2_reachable_gold_publishers": sum(x["n_gold_publishers"] >= 2 for x in g)}
    # 6. missing / empty
    out["6_missing_or_empty_gold"] = {
        "claims_no_web_gold": sum(x["n_gold_web"] == 0 for x in rows),
        "claims_web_gold_all_empty": sum(x["n_gold_web"] > 0 and x["n_gold_reachable"] == 0 for x in rows),
        "gold_urls_total": sum(x["n_gold_web"] for x in rows), "gold_urls_empty": sum(x["n_gold_empty"] for x in rows)}
    # G vs D losses: mechanism
    losses = [x for x in g if hit(x, "rank_D") and not hit(x)]
    wins = [x for x in g if hit(x) and not hit(x, "rank_D")]
    out["G_vs_D"] = {"wins": len(wins), "losses": len(losses),
                     "losses_mean_G_top10_added_by_targeting": round(sum(x["G_top10_added_by_targeting"] for x in losses) / max(1, len(losses)), 2),
                     "losses_with_>=1_targeted_doc_in_G_top10": sum(x["G_top10_added_by_targeting"] > 0 for x in losses),
                     "losses_authority_correct": sum(x["auth_reachable_gold"] for x in losses),
                     "loss_examples": [x["claim_id"] for x in losses[:10]]}
    json.dump(out, open(OUT / f"error_analysis_{split}.json", "w", encoding="utf-8"), indent=1)
    with open(OUT / f"error_analysis_{split}.csv", "w", newline="", encoding="utf-8") as fh:
        keys = sorted({k for x in rows for k in x}, key=lambda k: list(rows[0]).index(k) if k in rows[0] else 99)
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
