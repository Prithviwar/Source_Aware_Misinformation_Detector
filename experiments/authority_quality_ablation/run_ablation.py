"""Authority-quality ablation, Phase 1 (EXPLORATORY, not preregistered).

  python experiments/authority_quality_ablation/run_ablation.py

Ladder on the frozen held-out set, same hybrid top-100 pool, same rerank, lambda = 1:
  A0  no authority                      (= stored system A, 'hybrid')
  D1  predicted top-1 publisher keys    (new)
  D3  predicted top-3 publisher keys    (= stored system D, 'hybrid+llm_authority', reproduced)
  O   ORACLE gold publisher keys        (diagnostic only; uses gold; not deployable)

Read-only with respect to every existing file. Outputs go to results/authority_quality_ablation/ and the
script refuses to run if that directory already contains files. A reproduction gate must reproduce the
stored A and D rankings and table rows exactly before any new condition is scored.
No LLM calls; nothing is tuned.
"""
import csv
import datetime
import gzip
import hashlib
import json
import platform
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = EXP.parent
sys.path.insert(0, str(EXP))

import score_heldout_primary as SPH                     # noqa: E402
import source_targeted_eval as STE                      # noqa: E402
import validation_heldout as V                          # noqa: E402
from source_targeted import cand_key, primary_authority_candidates  # noqa: E402

OUT = ROOT / "results" / "authority_quality_ablation"
LOG = []
KS = (1, 5, 10, 20, 50, 100)
CONDS = ["A0", "D1", "D3", "O"]
INPUTS = {
    "sample": ROOT / "data/processed/averitec_heldout.jsonl",
    "predictions": ROOT / "results/heldout/authority_raw.jsonl",
    "hybrid_rankings": ROOT / "results/heldout/rankings_hybrid.jsonl.gz",
    "frozen_rankings_A_to_H": ROOT / "results/source_targeted/rankings_heldout.jsonl.gz",
    "frozen_table": ROOT / "results/source_targeted/results_heldout.json",
    "error_analysis_csv": ROOT / "results/source_targeted/error_analysis_heldout.csv",
    "ai_primary_results": ROOT / "results/heldout_ai_primary/MODEL_GENERATED_ai_primary_evidence_recall_heldout.json",
    "ai_primary_sheet": ROOT / "data/annotations/heldout_primary_package/ai/MODEL_GENERATED_heldout_primary_sheet_from_evidence_roles.csv",
    "ai_claim_labels": ROOT / "data/annotations/heldout_primary_package/ai/MODEL_GENERATED_claim_heldout_runA_CLAUDE_OPUS_5_5.csv",
    "code_this_script": Path(__file__).resolve(),
    "code_validation_heldout": EXP / "validation_heldout.py",
    "code_source_targeted_eval": EXP / "source_targeted_eval.py",
    "code_source_targeted": EXP / "source_targeted.py",
    "code_authority_retrieval": EXP / "authority_retrieval.py",
    "code_score_heldout_primary": EXP / "score_heldout_primary.py",
}


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def first_rank(ranking, target):
    return next((i for i, (u, _) in enumerate(ranking[:100], 1) if u in target), None)


def main():
    if OUT.exists() and any(OUT.iterdir()):
        sys.exit(f"REFUSED: {OUT} already contains files; nothing overwritten.")
    started = datetime.datetime.now().isoformat(timespec="seconds")
    log("authority_quality_ablation phase 1 | started", started, "| EXPLORATORY, not preregistered")
    prov = {k: {"path": str(v.relative_to(ROOT)), "sha256": sha(v)} for k, v in INPUTS.items()}

    # ---------------------------------------------------------------- frozen inputs (existing loaders)
    sample, preds, rk = STE.load_split("heldout")
    T, oracle, olabel = STE.gold_truth("heldout", sample)
    log(f"sample {len(sample)} claims | predictions {len(preds)} | gold-reachable {sum(bool(T[c]['gold']) for c in T)}")
    log("oracle definition:", olabel)

    # ---------------------------------------------------------------- rankings for the four conditions
    R = {m: {} for m in CONDS}
    P = {m: {} for m in CONDS}
    d1_info = {}
    for r in sample:
        c = int(r["claim_id"])
        pred = preds.get(c)
        hyb = rk["hybrid"][c]
        hpool = {u for u, _ in hyb[:V.POOL]}
        cands = primary_authority_candidates(pred) if pred else []
        # D3: exactly as source_targeted_eval.build() constructs 'hybrid+llm_authority'
        k3 = set().union(*[set(a["keys"]) for a in cands]) if cands else set()
        # D1: highest-ranked predicted entry with a usable publisher key
        k1 = set(cands[0]["keys"]) if cands else set()
        ko = oracle.get(c, set())
        R["A0"][c] = hyb
        R["D1"][c] = V.rerank(hyb, lambda u, k=k1: float(cand_key(u) in k))
        R["D3"][c] = V.rerank(hyb, lambda u, k=k3: float(cand_key(u) in k))
        R["O"][c] = V.rerank(hyb, lambda u, k=ko: float(cand_key(u) in k))
        for m in CONDS:
            P[m][c] = hpool
        d1_info[c] = {"n_usable_candidates": len(cands), "d1_source_rank": cands[0]["rank"] if cands else None,
                      "strict_rank1_usable": bool(cands) and cands[0]["rank"] == 1,
                      "n_keys_d1": len(k1), "n_keys_d3": len(k3), "n_keys_oracle": len(ko),
                      "predictor_label": (pred or {}).get("authority_situation")}

    # ---------------------------------------------------------------- REPRODUCTION GATE
    log("\n=== REPRODUCTION GATE ===")
    gate_ok = True
    frozen = {}
    with gzip.open(INPUTS["frozen_rankings_A_to_H"], "rt", encoding="utf-8") as fh:
        for x in map(json.loads, fh):
            if x["method"] in ("hybrid", "hybrid+llm_authority"):
                frozen.setdefault(x["method"], {})[x["claim_id"]] = [u for u, _ in x["ranked"]]
    for mine, theirs in (("A0", "hybrid"), ("D3", "hybrid+llm_authority")):
        mism = [c for c in frozen[theirs] if [u for u, _ in R[mine][c][:100]] != frozen[theirs][c]]
        ok = not mism and len(frozen[theirs]) == len(sample)
        gate_ok &= ok
        log(f"[gate] {mine} top-100 URL order vs stored '{theirs}' rankings: {len(frozen[theirs]) - len(mism)}/{len(frozen[theirs])} claims identical -> {'PASS' if ok else 'FAIL'}")
    stored = json.load(open(INPUTS["frozen_table"], encoding="utf-8"))["table"]
    got = STE.score({"hybrid": R["A0"], "hybrid+llm_authority": R["D3"]},
                    {"hybrid": P["A0"], "hybrid+llm_authority": P["D3"]}, T, "gold")
    for m in ("hybrid", "hybrid+llm_authority"):
        diffs = {k: (got[m].get(k), v) for k, v in stored[m].items() if got[m].get(k) != v}
        ok = not diffs
        gate_ok &= ok
        log(f"[gate] stored table row '{m}': {len(stored[m]) - len(diffs)}/{len(stored[m])} fields identical -> {'PASS' if ok else 'FAIL ' + str(diffs)}")
    # AI-primary rows (separate endpoint) must also reproduce
    ann, errs = SPH.read_sheet(INPUTS["ai_primary_sheet"])
    prim = {c: {u for u in T[c]["gold"] if cand_key(u) in ann[c]["keys"]}
            if ann[c]["situation"] not in SPH.EXCLUDED_SITUATIONS else set() for c in ann}
    Tp = {c: {"gold": set(), "prim": prim.get(c, set())} for c in T}
    ai_stored = json.load(open(INPUTS["ai_primary_results"], encoding="utf-8"))["main"]["table"]
    ai_got = STE.score({"hybrid": R["A0"], "hybrid+llm_authority": R["D3"]},
                       {"hybrid": P["A0"], "hybrid+llm_authority": P["D3"]}, Tp, "prim")
    for m in ("hybrid", "hybrid+llm_authority"):
        keys = [k for k in ai_stored[m] if k != "n_claims"]
        diffs = {k: (ai_got[m].get(k), ai_stored[m][k]) for k in keys if ai_got[m].get(k) != ai_stored[m][k]}
        ok = not diffs and ai_got[m]["n_prim_claims"] == ai_stored[m]["n_claims"]
        gate_ok &= ok
        log(f"[gate] AI-primary stored row '{m}': {len(keys) - len(diffs)}/{len(keys)} fields identical, n={ai_got[m]['n_prim_claims']} -> {'PASS' if ok else 'FAIL ' + str(diffs)}")
    log("REPRODUCTION GATE:", "PASS" if gate_ok else "FAIL")
    OUT.mkdir(parents=True, exist_ok=False)
    meta = {"experiment": "authority_quality_ablation_phase1", "status": "EXPLORATORY - not preregistered",
            "started": started, "git_commit": "not available: project directory is not a git repository; "
            "SHA-256 of code and inputs recorded instead", "python": platform.python_version(),
            "sample_seed": V.SEED_SAMPLE, "bootstrap_seed": V.SEED_BOOT, "bootstrap_resamples": V.BOOT,
            "lambda": V.LAMBDA, "pool": V.POOL, "authority_model": "claude-opus-5-5 (frozen L+Wctx predictions; 0 new calls)",
            "retrieval": "hybrid = RRF(k=60) of BM25 (bm25s) and dense all-MiniLM-L6-v2 (frozen rankings)",
            "denominator_main": "human-gold reachable claims", "provenance": prov, "gate_pass": gate_ok,
            "outputs": str(OUT.relative_to(ROOT))}
    if not gate_ok:
        json.dump(meta, open(OUT / "summary.json", "w", encoding="utf-8"), indent=1)
        (OUT / "log.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
        sys.exit("STOPPED: reproduction gate failed; no new condition scored.")

    # ---------------------------------------------------------------- new conditions: human-gold endpoint
    log("\n=== HUMAN-GOLD ENDPOINT (n = claims with reachable gold) ===")
    table = STE.score(R, P, T, "gold")
    gold_claims = sorted(c for c in T if T[c]["gold"])
    cols = [f"GoldR@{k}" for k in KS] + ["GoldMRR@100", "Gold_claim_coverage", "n_gold_claims"]
    log("cond | " + " | ".join(cols))
    for m in CONDS:
        log(m, "|", " | ".join(str(table[m][k]) for k in cols))
    d1_unusable = [c for c in sorted(d1_info) if not d1_info[c]["strict_rank1_usable"]]
    log(f"D1 definition check: strict rank-1 entry unusable for {len(d1_unusable)} of {len(sample)} claims "
        f"(in gold-reachable set: {len([c for c in d1_unusable if c in set(gold_claims)])}); "
        f"claims with no usable candidate at all: {[c for c in sorted(d1_info) if d1_info[c]['n_usable_candidates'] == 0]}")
    log("D1 fallback claims (claim: rank used):", {c: d1_info[c]["d1_source_rank"] for c in d1_unusable})

    # ---------------------------------------------------------------- paired tests
    def tests(target, claims, fam):
        out = []
        pairs = [("D1", "A0"), ("D3", "D1"), ("O", "D3"), ("O", "A0")]
        for k in (10, 5, 20):
            rows = []
            for b, a in pairs:
                ha = [first_rank(R[a][c], target[c]) is not None and first_rank(R[a][c], target[c]) <= k for c in claims]
                hb = [first_rank(R[b][c], target[c]) is not None and first_rank(R[b][c], target[c]) <= k for c in claims]
                w, l, p = V.mcnemar(ha, hb)
                d, lo, hi = V.boot_ci(ha, hb)
                rows.append({"endpoint": fam, "metric": f"R@{k}", "comparison": f"{b} vs {a}", "n": len(claims),
                             "wins": w, "losses": l, "ties": len(claims) - w - l, "p_exact_mcnemar": round(p, 5),
                             "diff": d, "ci95_low": lo, "ci95_high": hi})
            if k == 10:
                for row, adj in zip(rows, V.holm([x["p_exact_mcnemar"] for x in rows])):
                    row["p_holm_within_new_family"] = round(adj, 5)
                    row["family"] = f"AQA-P1 ({fam}, R@10, 4 tests) - exploratory, NOT the preregistered family"
            else:
                for row in rows:
                    row["p_holm_within_new_family"] = ""
                    row["family"] = "descriptive, uncorrected"
            out += rows
        return out

    gold_tests = tests({c: T[c]["gold"] for c in T}, gold_claims, "human-gold")
    log("\n=== PAIRED TESTS, human-gold (exploratory) ===")
    for t in gold_tests:
        log(f"{t['metric']:5} {t['comparison']:9} +{t['wins']}/-{t['losses']}/={t['ties']} p={t['p_exact_mcnemar']} "
            f"holm={t['p_holm_within_new_family']} diff={t['diff']} CI[{t['ci95_low']}, {t['ci95_high']}]")

    # ---------------------------------------------------------------- AI-primary endpoint (separate)
    ai_claims = sorted(c for c in Tp if Tp[c]["prim"])
    ai_table = STE.score(R, P, Tp, "prim")
    log(f"\n=== AI-PRIMARY ENDPOINT (separate, exploratory; n={len(ai_claims)}) ===")
    ai_cols = ["PrimR@1", "PrimR@5", "PrimR@10", "PrimR@20", "PrimR@50", "PrimR@100", "PrimMRR@100", "Prim_claim_coverage"]
    for m in CONDS:
        log(m, "|", " | ".join(str(ai_table[m][k]) for k in ai_cols))
    ai_tests = tests({c: Tp[c]["prim"] for c in Tp}, ai_claims, "AI-primary")
    for t in ai_tests:
        if t["metric"] == "R@10":
            log(f"{t['metric']:5} {t['comparison']:9} +{t['wins']}/-{t['losses']}/={t['ties']} p={t['p_exact_mcnemar']} "
                f"holm={t['p_holm_within_new_family']} diff={t['diff']} CI[{t['ci95_low']}, {t['ci95_high']}]")

    # ---------------------------------------------------------------- strata (descriptive)
    err = {int(x["claim_id"]): x for x in csv.DictReader(open(INPUTS["error_analysis_csv"], encoding="utf-8"))}
    ai_lab = {int(x["claim_id"]): x["authority_situation"] for x in csv.DictReader(open(INPUTS["ai_claim_labels"], encoding="utf-8"))}
    recomputed = {c: len({cand_key(u) for u in T[c]["gold"]}) for c in gold_claims}
    agree = sum(int(err[c]["n_gold_publishers"]) == recomputed[c] for c in gold_claims)
    log(f"\nstrata check: stored n_gold_publishers equals recomputation for {agree}/{len(gold_claims)} claims")
    strat_defs = {
        "gold_publishers (from human gold)": lambda c: "1 publisher" if int(err[c]["n_gold_publishers"]) == 1 else ">=2 publishers",
        "predictor_label (MODEL OUTPUT)": lambda c: d1_info[c]["predictor_label"] or "missing",
        "ai_claim_label (MODEL_GENERATED)": lambda c: ai_lab.get(c, "missing"),
        "predicted_matches_gold_publisher (stored flag)": lambda c: "match" if err[c]["auth_any_gold_key"] == "True" else "no match",
    }
    strata_rows = []
    log("\n=== STRATA (descriptive; human-gold hits at R@10 and R@20) ===")
    for name, fn in strat_defs.items():
        groups = {}
        for c in gold_claims:
            groups.setdefault(fn(c), []).append(c)
        for g, cs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            row = {"stratifier": name, "group": g, "n": len(cs)}
            for m in CONDS:
                for k in (10, 20):
                    h = sum((first_rank(R[m][c], T[c]["gold"]) or 999) <= k for c in cs)
                    row[f"{m}_hits@{k}"] = h
                    row[f"{m}_R@{k}"] = round(h / len(cs), 3)
            strata_rows.append(row)
            log(f"{name:48} {g:34} n={len(cs):3d} | R@10 " + " ".join(f"{m}={row[m + '_R@10']}" for m in CONDS)
                + " | R@20 " + " ".join(f"{m}={row[m + '_R@20']}" for m in CONDS))

    # ---------------------------------------------------------------- per-claim records
    per_claim = []
    for c in sorted(d1_info):
        rec = {"claim_id": c, "gold_reachable": bool(T[c]["gold"]), "ai_primary_eligible": c in set(ai_claims),
               **{k: v for k, v in d1_info[c].items()},
               "n_gold_publishers": err[c]["n_gold_publishers"] if c in err else "",
               "predicted_matches_gold_publisher": err[c]["auth_any_gold_key"] if c in err else "",
               "ai_claim_label": ai_lab.get(c, "")}
        for m in CONDS:
            rec[f"{m}_first_gold_rank"] = first_rank(R[m][c], T[c]["gold"]) if T[c]["gold"] else ""
            rec[f"{m}_first_ai_primary_rank"] = first_rank(R[m][c], Tp[c]["prim"]) if Tp[c]["prim"] else ""
        per_claim.append(rec)

    # ---------------------------------------------------------------- write outputs (new files only)
    def wcsv(name, rows):
        with open(OUT / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    wcsv("per_system_human_gold.csv", [{"condition": m, **{k: table[m][k] for k in cols}} for m in CONDS])
    wcsv("per_system_ai_primary.csv", [{"condition": m, **{k: ai_table[m][k] for k in ai_cols}, "n": len(ai_claims)} for m in CONDS])
    wcsv("tests.csv", gold_tests + ai_tests)
    wcsv("strata.csv", strata_rows)
    wcsv("per_claim.csv", per_claim)
    meta.update({"finished": datetime.datetime.now().isoformat(timespec="seconds"),
                 "oracle_label": olabel + " -- DIAGNOSTIC ONLY",
                 "human_gold": {m: table[m] for m in CONDS}, "ai_primary": {m: ai_table[m] for m in CONDS},
                 "d1_strict_rank1_unusable_claims": d1_unusable,
                 "tests_human_gold": gold_tests, "tests_ai_primary": ai_tests, "strata": strata_rows})
    json.dump(meta, open(OUT / "summary.json", "w", encoding="utf-8"), indent=1)
    (OUT / "log.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    log("\nwrote:", ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
