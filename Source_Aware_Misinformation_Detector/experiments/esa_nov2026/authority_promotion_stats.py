"""Quantify the publisher-level binary-boost limitation from FROZEN rankings/predictions (exploratory).

  python experiments/esa_nov2026/authority_promotion_stats.py

For priors B (generic), C (heuristic) and D (frozen LLM top-3 publishers) on the hybrid top-100:
  * promoted     = a document in the reranked top-10 whose hybrid rank was > 10;
  * deep-promoted= ... whose hybrid rank was > 50 (very low relevance score, lifted only by the prior);
  * non-gold     = not an AVeriTeC evidence document (it MAY still be relevant: negatives are unlabelled).
Also per-claim win/loss of best gold rank vs hybrid, and claims where gold was in the hybrid top-10
but was pushed out by boosted documents ("displacement").
Writes results/esa_nov2026/authority/promotion_stats.json and per_claim.csv. No LLM calls.
"""
import csv
import json

from esa_common import claims, load_frozen_predictions, load_frozen_rankings, out_dir


def main():
    import validation_heldout as V
    from authority_retrieval import claim_entities, entity_keys, full_prior, generic_prior
    from source_targeted import cand_key, primary_authority_candidates
    res, rows = {}, []
    for split in ("heldout200", "dev120"):
        sample = [r for r in claims().values() if r["split"] == split]
        T = V.gold_info(sample, None)
        rk = load_frozen_rankings(split)
        preds = load_frozen_predictions(split)
        ev = [int(r["claim_id"]) for r in sample if T[int(r["claim_id"])]["gold"]]
        agg = {}
        for r in sample:
            c = int(r["claim_id"])
            if c not in ev:
                continue
            hyb = rk["hybrid"][c]
            hr = {u: i for i, (u, _) in enumerate(hyb[:100], 1)}
            g = T[c]["gold"]
            pk = set().union(*[set(a["keys"]) for a in primary_authority_candidates(preds.get(c))]) if c in preds else set()
            ek, iso = entity_keys(claim_entities(r)), r.get("location_ISO_code")
            fns = {"B_generic": generic_prior, "C_heuristic": lambda u: full_prior(u, ek, iso),
                   "D_llm": lambda u: float(cand_key(u) in pk)}
            base_top = [u for u, _ in hyb[:10]]
            base_best = next((i for i, (u, _) in enumerate(hyb[:100], 1) if u in g), 101)
            row = {"split": split, "claim_id": c, "hybrid_best_gold_rank": base_best,
                   "claim": r["claim"][:140], "claim_types": "|".join(r.get("claim_types") or []),
                   "llm_top3": " | ".join(t.get("publisher") or "" for t in ((preds.get(c) or {}).get("top3") or [])[:3]),
                   "n_pool_docs_from_llm_publishers": sum(cand_key(u) in pk for u, _ in hyb[:100])}
            for s, fn in fns.items():
                rr = V.rerank(hyb, fn)
                top = [u for u, _ in rr[:10]]
                prom = [u for u in top if hr[u] > 10]
                deep = [u for u in top if hr[u] > 50]
                best = next((i for i, (u, _) in enumerate(rr[:100], 1) if u in g), 101)
                displaced = bool(g & set(base_top)) and not (g & set(top))
                a = agg.setdefault(s, {"claims": 0, "promoted_docs": 0, "promoted_non_gold": 0, "deep_docs": 0,
                                       "deep_non_gold": 0, "claims_ge5_promoted_non_gold": 0,
                                       "claims_with_any_deep_non_gold": 0, "displacement_claims": 0,
                                       "win": 0, "loss": 0, "tie": 0})
                a["claims"] += 1
                a["promoted_docs"] += len(prom)
                a["promoted_non_gold"] += sum(u not in g for u in prom)
                a["deep_docs"] += len(deep)
                a["deep_non_gold"] += sum(u not in g for u in deep)
                a["claims_ge5_promoted_non_gold"] += sum(u not in g for u in prom) >= 5
                a["claims_with_any_deep_non_gold"] += any(u not in g for u in deep)
                a["displacement_claims"] += displaced
                a["win" if best < base_best else "loss" if best > base_best else "tie"] += 1
                row.update({f"{s}_best_gold_rank": best, f"{s}_promoted_into_top10": len(prom),
                            f"{s}_promoted_non_gold": sum(u not in g for u in prom),
                            f"{s}_deep_promoted": len(deep), f"{s}_displaced_gold": displaced})
            rows.append(row)
        res[split] = {"n_claims_with_reachable_gold": len(ev), "by_prior": agg}
        print(f"== {split} (n = {len(ev)} claims with reachable gold) ==")
        for s, a in agg.items():
            print(f"  {s:12s} promoted-into-top10 docs {a['promoted_docs']} (non-gold {a['promoted_non_gold']}); "
                  f"from below rank 50: {a['deep_docs']} (non-gold {a['deep_non_gold']}); "
                  f"claims with >=5 promoted non-gold: {a['claims_ge5_promoted_non_gold']}; "
                  f"gold displaced from top-10: {a['displacement_claims']}; best-gold-rank W/L/T "
                  f"{a['win']}/{a['loss']}/{a['tie']}")
    d = out_dir("authority")
    json.dump({"status": "exploratory, descriptive; frozen inputs; sets already used", "note": __doc__, "results": res},
              open(d / "promotion_stats.json", "w", encoding="utf-8"), indent=1)
    with open(d / "per_claim.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"-> {d / 'promotion_stats.json'}")


if __name__ == "__main__":
    main()
