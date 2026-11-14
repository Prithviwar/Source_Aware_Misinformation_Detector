"""ESA reproduction check (read-only with respect to all frozen files).

  python experiments/esa_nov2026/reproduce_check.py            # hashes + re-scoring of frozen rankings
  python experiments/esa_nov2026/reproduce_check.py --live 5   # + recompute BM25/dense live for 5 claims per split

1. Hash gate: frozen scripts/rankings vs the SHA-256 values recorded in the preregistrations.
   Scripts are compared after CRLF->LF normalisation (git core.autocrlf=true on this machine).
2. Re-scoring: systems A (hybrid), B (+generic prior), C (+heuristic prior), D (+frozen LLM prior)
   are rebuilt from the FROZEN full rankings and FROZEN predictions with the FROZEN functions,
   scored with the frozen `source_targeted_eval.score`, and compared to the published tables
   results/source_targeted/results_{heldout,dev}.json. No retrieval is re-run in this step.
3. Optional live check: BM25 and MiniLM rankings are recomputed with the frozen `rank_bm25` /
   `rank_dense` for a few claims and compared with the stored rankings.

Output: results/esa_nov2026/reproduction/reproduction_check.json
"""
import argparse
import json
import time

from esa_common import (ROOT, assert_allowed, claims, load_frozen_predictions, load_frozen_rankings, out_dir,
                        sha256_lf, sha256_raw)

RECORDED = {  # path -> (recorded sha256, where recorded, compare mode)
    "experiments/validation_heldout.py": ("304984b62945def7ecbfeb49a7c5c4e4ff68b4d13f080e4bed9465a6235dfbc5",
                                          "docs/validation_preregistration.md L76", "lf"),
    "experiments/source_targeted.py": ("6ec3172da035e815b275224742f9bf0a64482b955748c5dfaafeab85dcbba223",
                                       "docs/source_targeted_preregistration.md L66", "lf"),
    "experiments/source_targeted_eval.py": ("a686a075471b2fcb0ed5658a2fb372fc384d8f4f3437512e44f87fb386379e04",
                                            "docs/source_targeted_preregistration.md L67", "lf"),
    "experiments/score_heldout_primary.py": ("114bf0cac69cce3d43f718360852568199f5af4abb660a85cf924a4f7d046ad2",
                                             "docs/source_targeted_preregistration.md L83", "lf"),
    "results/source_targeted/rankings_heldout.jsonl.gz": (
        "9105a5da66a287de70fdc6e7e9b5135200589d58c542d61787e7ed883cb66558",
        "docs/source_targeted_preregistration.md L85", "raw"),
}
RECORDED_PREFIX = {  # only prefix...suffix recorded
    "experiments/authority_resolution.py": ("58714a83", "0e97", "docs/validation_preregistration.md L78"),
    "experiments/authority_retrieval.py": ("ac4c2e80", "9312", "docs/validation_preregistration.md L78"),
    "experiments/baseline_retrieval.py": ("2730f0b3", "bd9b", "docs/validation_preregistration.md L78"),
}
COLS = ("GoldR@1", "GoldR@3", "GoldR@5", "GoldR@10", "GoldR@20", "GoldR@50", "GoldR@100", "GoldMRR@100",
        "Gold_claim_coverage", "Gold_doc_coverage", "n_gold_claims", "n_gold_docs")
SYSTEMS = {"A": "hybrid", "B": "hybrid+generic", "C": "hybrid+heuristic", "D": "hybrid+llm_authority",
           "bm25": "bm25", "dense": "dense"}


def hash_gate():
    rows, ok = [], True
    for rel, (h, where, mode) in RECORDED.items():
        p = ROOT / rel
        got = sha256_lf(p) if mode == "lf" else sha256_raw(p)
        rows.append({"file": rel, "recorded": h, "observed": got, "mode": mode, "match": got == h, "recorded_in": where})
        ok &= got == h
    for rel, (pre, suf, where) in RECORDED_PREFIX.items():
        p = ROOT / rel
        a, b = sha256_raw(p), sha256_lf(p)
        m = any(x.startswith(pre) and x.endswith(suf) for x in (a, b))
        rows.append({"file": rel, "recorded": f"{pre}...{suf}", "observed_raw": a, "observed_lf": b,
                     "match": m, "recorded_in": where})
        ok &= m
    return ok, rows


def rescore(split):
    import validation_heldout as V
    from authority_retrieval import claim_entities, entity_keys, full_prior, generic_prior
    from source_targeted import cand_key, primary_authority_candidates
    from source_targeted_eval import score
    sample = [r for r in claims().values() if r["split"] == split]
    rk = load_frozen_rankings(split)
    preds = load_frozen_predictions(split)
    T = V.gold_info(sample, None)
    R, P = {}, {}
    for r in sample:
        c = int(r["claim_id"])
        hyb = rk["hybrid"][c]
        hpool = {u for u, _ in hyb[:100]}
        pk = set().union(*[set(a["keys"]) for a in primary_authority_candidates(preds.get(c))]) if c in preds else set()
        ek, iso = entity_keys(claim_entities(r)), r.get("location_ISO_code")
        for name, ranking, pool in (
                ("bm25", rk["bm25"][c], {u for u, _ in rk["bm25"][c][:100]}),
                ("dense", rk["dense"][c], {u for u, _ in rk["dense"][c][:100]}),
                ("hybrid", hyb, hpool),
                ("hybrid+generic", V.rerank(hyb, generic_prior), hpool),
                ("hybrid+heuristic", V.rerank(hyb, lambda u: full_prior(u, ek, iso)), hpool),
                ("hybrid+llm_authority", V.rerank(hyb, lambda u: float(cand_key(u) in pk)), hpool)):
            R.setdefault(name, {})[c] = ranking
            P.setdefault(name, {})[c] = pool
    got = score(R, P, T, None)
    ref_path = ROOT / "results" / "source_targeted" / f"results_{'heldout' if split == 'heldout200' else 'dev'}.json"
    ref = json.load(open(ref_path, encoding="utf-8"))["table"]
    comp, all_ok = {}, True
    for sid, m in SYSTEMS.items():
        rows = {}
        for col in COLS:
            a, b = got[m].get(col), ref.get(m, {}).get(col)
            if b is None:
                continue
            rows[col] = {"recomputed": a, "published": b, "match": a == b}
            all_ok &= a == b
        comp[f"{sid} ({m})"] = rows
    return all_ok, comp, str(ref_path.relative_to(ROOT))


def live_check(split, n):
    from baseline_retrieval import rank_bm25, rank_dense, retrieval_corpus
    rk = load_frozen_rankings(split)
    ids = sorted(c for c, r in claims().items() if r["split"] == split)[:n]
    res = []
    for c in ids:
        row = assert_allowed(c)
        docs = retrieval_corpus(c)
        t0 = time.time()
        b = rank_bm25(row["claim"], docs)
        d = rank_dense(row["claim"], docs)
        fused = {}
        for lst in (b, d):
            for rank, (u, _) in enumerate(lst, 1):
                fused[u] = fused.get(u, 0.0) + 1.0 / (60 + rank)
        h = sorted(fused.items(), key=lambda x: -x[1])
        out = {"claim_id": c, "split": split, "n_docs": len(docs), "seconds": round(time.time() - t0, 1)}
        for m, live in (("bm25", b), ("dense", d), ("hybrid", h)):
            st = [u for u, _ in rk[m][c][:100]]
            lv = [u for u, _ in live[:100]]
            out[m] = {"top100_identical_order": st == lv, "top10_identical_order": st[:10] == lv[:10],
                      "top100_set_overlap": len(set(st) & set(lv))}
        res.append(out)
        print(f"  live {split} claim {c}: " + ", ".join(f"{m} top100 same order={out[m]['top100_identical_order']}"
                                                    for m in ("bm25", "dense", "hybrid")), flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", type=int, default=0, help="recompute BM25/dense for N claims per split")
    a = ap.parse_args()
    report = {"note": "Read-only reproduction check. No frozen file is modified. No LLM call."}
    ok, rows = hash_gate()
    report["hash_gate"] = {"all_match": ok, "files": rows}
    print(f"hash gate: {'PASS' if ok else 'FAIL'}")
    for r in rows:
        print(f"  {'ok ' if r['match'] else 'BAD'} {r['file']}")
    report["rescoring"] = {}
    for split in ("dev120", "heldout200"):
        t0 = time.time()
        sok, comp, ref = rescore(split)
        report["rescoring"][split] = {"all_match": sok, "reference": ref, "systems": comp}
        print(f"re-scoring {split} vs {ref}: {'PASS (all values identical)' if sok else 'MISMATCH'} "
              f"({time.time() - t0:.0f}s)")
        for sid, cols in comp.items():
            print(f"  {sid:28s} R@10 {cols['GoldR@10']['recomputed']} (published {cols['GoldR@10']['published']})"
                  f"  n={cols['n_gold_claims']['recomputed']}")
    if a.live:
        report["live_retrieval"] = [x for s in ("dev120", "heldout200") for x in live_check(s, a.live)]
    p = out_dir("reproduction") / "reproduction_check.json"
    json.dump(report, open(p, "w", encoding="utf-8"), indent=1)
    print(f"-> {p}")


if __name__ == "__main__":
    main()
