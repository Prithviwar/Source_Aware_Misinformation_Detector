"""Stage-wise recall decomposition from FROZEN rankings (exploratory, descriptive).

  python experiments/esa_nov2026/recall_ceiling.py

Uses only: the 120 development + 200 held-out claims, their knowledge-store extracts, the
frozen full BM25/dense/hybrid rankings and the frozen LLM predictions. No retrieval is re-run,
no LLM is called, nothing frozen is written. Reserved-180 claims and sealed gold are not touched.

STATUS OF THESE NUMBERS: new descriptive measurements (Nov 2026) on sets that were ALREADY USED
in the frozen study. They are exploratory, not preregistered, and not a new held-out test.
"Gold" = AVeriTeC annotator evidence URLs (fact-checker citations; include news and fact-check
pages). They measure EVIDENCE RECALL, not authority recall.

Definitions (per split; c ranges over claims, G(c) = reachable gold docs of claim c,
W(c) = all web gold URLs of claim c, top_K(c) = first K documents of a ranking):
  collection coverage (claim)  = |{c : G(c) != {}}| / |{c : W(c) != {}}|
  collection coverage (doc)    = sum |G(c)| / sum |W(c)|
  claim-level Recall@K         = |{c in C_eval : G(c) & top_K(c) != {}}| / |C_eval|,  C_eval = {c : G(c) != {}}
                                 (= the project's historical R@K / hit rate)
  document-level Recall@K      = sum_c |G(c) & top_K(c)| / sum_c |G(c)|    (micro)
  macro document Recall@K      = mean_c |G(c) & top_K(c)| / |G(c)|
  end-to-end claim Recall@K    = same as claim-level but denominator {c : W(c) != {}} (counts collection loss)
  candidate-pool coverage      = claim-level Recall@100 of the hybrid ranking (the frozen rerank pool)
                                 = the ceiling for ANY reranker of that pool (rerank-only oracle)
"""
import json
import statistics

from esa_common import claims, load_frozen_predictions, load_frozen_rankings, out_dir

DEPTHS = (1, 5, 10, 20, 50, 100, 200, 300, 500, None)
RECON_HISTORICAL = {  # transcript-reconstructed, partly verified; NOT measured here
    "source": "storage/recovery_staging/bottleneck_analysis/files/docs/authority_resolution_bottleneck_analysis.md "
              "(lines ~246-252); RESEARCH_PROPOSAL_INFORMATION_PACKAGE.md L185",
    "status": "RECONSTRUCTED, UNVERIFIED (lines 51-856 of the reconstructed report were never independently checked)",
    "held-out hybrid coverage": {"top100": 0.671, "top200": 0.850, "top300": 0.922},
}


def tag(k):
    return f"@{k}" if k else "@all"


def split_stats(split):
    import validation_heldout as V
    from authority_retrieval import generic_prior, full_prior, claim_entities, entity_keys
    from source_targeted import cand_key, primary_authority_candidates
    sample = [r for r in claims().values() if r["split"] == split]
    T = V.gold_info(sample, None)
    rk = load_frozen_rankings(split)
    preds = load_frozen_predictions(split)
    cids = [int(r["claim_id"]) for r in sample]
    web = [c for c in cids if T[c]["gold_all"]]
    ev = [c for c in cids if T[c]["gold"]]
    n_web_urls = sum(len(T[c]["gold_all"]) for c in cids)
    n_reach_urls = sum(len(T[c]["gold"]) for c in cids)
    sizes = [len(rk["hybrid"][c]) for c in cids]
    out = {"split": split, "n_claims": len(cids),
           "stage1_collection": {
               "claims_with_web_gold": len(web), "claims_with_reachable_gold": len(ev),
               "claim_coverage": f"{len(ev)}/{len(web)} = {len(ev) / len(web):.3f}",
               "web_gold_urls": n_web_urls, "reachable_gold_urls": n_reach_urls,
               "doc_coverage": f"{n_reach_urls}/{n_web_urls} = {n_reach_urls / n_web_urls:.3f}",
               "claims_without_any_web_gold": len(cids) - len(web),
               "note": "reachable = gold URL present in the claim's knowledge store with non-empty text"},
           "candidates_per_claim": {"min": min(sizes), "median": statistics.median(sizes), "max": max(sizes)},
           "stage2_retrieval": {}}
    for m in ("bm25", "dense", "hybrid"):
        row = {}
        for K in DEPTHS:
            top = {c: {u for u, _ in rk[m][c][:K]} for c in cids}
            hits = sum(bool(T[c]["gold"] & top[c]) for c in ev)
            found = sum(len(T[c]["gold"] & top[c]) for c in ev)
            row[tag(K)] = {
                "claim_recall": round(hits / len(ev), 3), "claim_hits": f"{hits}/{len(ev)}",
                "doc_recall_micro": round(found / n_reach_urls, 3), "doc_found": f"{found}/{n_reach_urls}",
                "doc_recall_macro": round(sum(len(T[c]["gold"] & top[c]) / len(T[c]["gold"]) for c in ev) / len(ev), 3),
                "end_to_end_claim_recall": f"{hits}/{len(web)} = {hits / len(web):.3f}"}
        out["stage2_retrieval"][m] = row
    pool_hits = sum(bool(T[c]["gold"] & {u for u, _ in rk["hybrid"][c][:100]}) for c in ev)
    out["stage3_candidate_pool"] = {
        "pool": "hybrid top-100 (frozen rerank pool)",
        "claim_coverage": f"{pool_hits}/{len(ev)} = {pool_hits / len(ev):.3f}",
        "meaning": "maximum claim-level Recall@K any reranker of this pool can reach (rerank-only oracle)",
        "claims_lost_before_reranking": len(ev) - pool_hits}
    # stage 4: authority prediction vs publishers of ALL human gold URLs (proxy; no authority labels exist)
    evald = [c for c in cids if c in preds and T[c]["gold_keys"]]
    keys = {c: set().union(*[set(a["keys"]) for a in primary_authority_candidates(preds[c])]) for c in preds}
    top1 = {c: set(primary_authority_candidates(preds[c])[0]["keys"]) if primary_authority_candidates(preds[c]) else set()
            for c in preds}
    t1 = sum(bool(top1[c] & T[c]["gold_keys"]) for c in evald)
    t3 = sum(bool(keys[c] & T[c]["gold_keys"]) for c in evald)
    in_pool = sum(any(cand_key(u) in keys.get(c, set()) for u, _ in rk["hybrid"][c][:100]) for c in ev)
    out["stage4_authority_classification_proxy"] = {
        "target": "publisher keys of ALL AVeriTeC gold URLs (news / fact-check publishers included) - a PROXY; "
                  "no human claim-specific authority labels exist, so true authority accuracy cannot be measured",
        "n": len(evald), "top1_match": f"{t1}/{len(evald)} = {t1 / len(evald):.3f}",
        "top3_match": f"{t3}/{len(evald)} = {t3 / len(evald):.3f}",
        "claims_where_a_predicted_publisher_has_a_doc_in_pool": f"{in_pool}/{len(ev)}"}
    # stage 5: final ranking (A, B, C, D on the hybrid top-100) and fraction of the pool ceiling achieved
    sysrank = {}
    for r in sample:
        c = int(r["claim_id"])
        hyb = rk["hybrid"][c]
        ek, iso = entity_keys(claim_entities(r)), r.get("location_ISO_code")
        sysrank.setdefault("A_hybrid", {})[c] = hyb
        sysrank.setdefault("B_generic", {})[c] = V.rerank(hyb, generic_prior)
        sysrank.setdefault("C_heuristic", {})[c] = V.rerank(hyb, lambda u: full_prior(u, ek, iso))
        sysrank.setdefault("D_llm", {})[c] = V.rerank(hyb, lambda u, k=keys.get(c, set()): float(cand_key(u) in k))
    fin = {}
    for s, R in sysrank.items():
        row = {}
        for K in (1, 5, 10, 20):
            h = sum(bool(T[c]["gold"] & {u for u, _ in R[c][:K]}) for c in ev)
            d = sum(len(T[c]["gold"] & {u for u, _ in R[c][:K]}) for c in ev)
            row[f"@{K}"] = {"claim_recall": f"{h}/{len(ev)} = {h / len(ev):.3f}",
                            "fraction_of_pool_ceiling": round(h / pool_hits, 3),
                            "doc_recall_micro": f"{d}/{n_reach_urls} = {d / n_reach_urls:.3f}"}
        fin[s] = row
    out["stage5_final_ranking"] = fin
    return out


def main():
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    res = {"status": "NEW descriptive measurement from frozen rankings (exploratory; sets already used; not preregistered)",
           "definitions": __doc__.split("Definitions")[1].strip(),
           "historical_reconstructed_for_comparison_only": RECON_HISTORICAL, "splits": {}}
    for split in ("heldout200", "dev120"):
        s = split_stats(split)
        res["splits"][split] = s
        print(f"\n===== {split} =====")
        print("Stage 1 collection:", s["stage1_collection"]["claim_coverage"], "claims;",
              s["stage1_collection"]["doc_coverage"], "gold URLs reachable")
        print("candidates/claim:", s["candidates_per_claim"])
        for m, row in s["stage2_retrieval"].items():
            print(f"Stage 2 {m:6s} claim R" + "  ".join(f"{k}={v['claim_recall']}" for k, v in row.items()))
            print(f"        {'':6s} doc   R" + "  ".join(f"{k}={v['doc_recall_micro']}" for k, v in row.items()))
        print("Stage 3 pool:", s["stage3_candidate_pool"]["claim_coverage"])
        print("Stage 4 authority proxy:", s["stage4_authority_classification_proxy"]["top1_match"], "top1;",
              s["stage4_authority_classification_proxy"]["top3_match"], "top3")
        for sname, row in s["stage5_final_ranking"].items():
            print(f"Stage 5 {sname:12s} R@10 {row['@10']['claim_recall']}  "
                  f"(fraction of pool ceiling {row['@10']['fraction_of_pool_ceiling']})")
    p = out_dir("recall_ceiling") / "recall_ceiling.json"
    json.dump(res, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"-> {p}")


if __name__ == "__main__":
    main()
