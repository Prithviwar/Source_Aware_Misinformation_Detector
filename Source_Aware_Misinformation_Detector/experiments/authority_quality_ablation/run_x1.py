"""Phase 2 step 2: score A0, D1 and X1 on the matched set S (human-gold endpoint). EXPLORATORY.

Refuses to run unless (1) the saved X1 assignment matches its recorded SHA-256 and is read-only,
(2) the reproduction gate passes: A0 equals the stored system A rankings and D1 reproduces the Phase 1 D1
per-claim gold ranks. The assignment hash is checked again after scoring. Refuses to overwrite outputs.
"""
import csv
import datetime
import gzip
import hashlib
import json
import os
import platform
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
import source_targeted_eval as STE  # noqa: E402
import validation_heldout as V  # noqa: E402
from source_targeted import cand_key, primary_authority_candidates  # noqa: E402

OUT = ROOT / "results" / "authority_quality_ablation_phase2"
ASSIGN = OUT / "x1_assignment.csv"
P1 = ROOT / "results" / "authority_quality_ablation" / "per_claim.csv"
CONDS = ["A0", "D1", "X1"]
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def first_rank(ranking, target):
    return next((i for i, (u, _) in enumerate(ranking[:100], 1) if u in target), None)


def main():
    if (OUT / "summary.json").exists():
        sys.exit("REFUSED: Phase 2 outputs already exist; nothing overwritten.")
    started = datetime.datetime.now().isoformat(timespec="seconds")
    log("authority_quality_ablation phase 2 (matched mismatched-authority perturbation) | started", started,
        "| EXPLORATORY, not preregistered")

    # ---- assignment integrity
    recorded = (OUT / "x1_assignment.sha256").read_text(encoding="utf-8").split()[0]
    actual = sha(ASSIGN)
    ro = not (os.stat(ASSIGN).st_mode & 0o200)
    log(f"[assignment] recorded SHA-256 {recorded} | actual {actual} | match={recorded == actual} | read-only={ro}")
    if recorded != actual or not ro:
        sys.exit("STOPPED: assignment hash mismatch or file writable.")
    assign = {int(r["claim_id"]): r for r in csv.DictReader(open(ASSIGN, encoding="utf-8"))}
    S = sorted(c for c, r in assign.items() if r["x1_key"])

    sample, preds, rk = STE.load_split("heldout")
    T, _, _ = STE.gold_truth("heldout", sample)
    R = {m: {} for m in CONDS}
    P = {m: {} for m in CONDS}
    for r in sample:
        c = int(r["claim_id"])
        hyb = rk["hybrid"][c]
        cands = primary_authority_candidates(preds.get(c))
        k1 = set(cands[0]["keys"]) if cands else set()
        R["A0"][c] = hyb
        R["D1"][c] = V.rerank(hyb, lambda u, k=k1: float(cand_key(u) in k))
        if c in assign and assign[c]["x1_key"]:
            kx = {assign[c]["x1_key"]}
            R["X1"][c] = V.rerank(hyb, lambda u, k=kx: float(cand_key(u) in k))
        for m in CONDS:
            P[m][c] = {u for u, _ in hyb[:V.POOL]}

    # ---- reproduction gate
    log("\n=== REPRODUCTION GATE ===")
    frozen = {}
    with gzip.open(ROOT / "results/source_targeted/rankings_heldout.jsonl.gz", "rt", encoding="utf-8") as fh:
        for x in map(json.loads, fh):
            if x["method"] == "hybrid":
                frozen[x["claim_id"]] = [u for u, _ in x["ranked"]]
    a_ok = all([u for u, _ in R["A0"][c][:100]] == frozen[c] for c in frozen) and len(frozen) == 200
    log(f"[gate] A0 top-100 URL order vs stored system A: {'PASS' if a_ok else 'FAIL'} (200 claims)")
    p1 = {int(r["claim_id"]): r for r in csv.DictReader(open(P1, encoding="utf-8"))}
    d1_bad = [c for c in p1 if p1[c]["gold_reachable"] == "True"
              and str(first_rank(R["D1"][c], T[c]["gold"]) or "") != p1[c]["D1_first_gold_rank"]]
    a0_bad = [c for c in p1 if p1[c]["gold_reachable"] == "True"
              and str(first_rank(R["A0"][c], T[c]["gold"]) or "") != p1[c]["A0_first_gold_rank"]]
    d1_ok, a0p_ok = not d1_bad, not a0_bad
    log(f"[gate] D1 per-claim first-gold rank vs Phase 1 D1: {'PASS' if d1_ok else 'FAIL ' + str(d1_bad[:10])} (167 claims)")
    log(f"[gate] A0 per-claim first-gold rank vs Phase 1 A0: {'PASS' if a0p_ok else 'FAIL ' + str(a0_bad[:10])} (167 claims)")
    s_ok = all(T[c]["gold"] for c in S) and len(S) == 79
    log(f"[gate] analysis set S: {len(S)} claims, all gold-reachable: {'PASS' if s_ok else 'FAIL'}")
    gate = a_ok and d1_ok and a0p_ok and s_ok
    log("REPRODUCTION GATE:", "PASS" if gate else "FAIL")
    if not gate:
        (OUT / "log.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
        sys.exit("STOPPED: gate failed; nothing scored.")

    # ---- scoring on S
    TS = {c: T[c] for c in S}
    RS = {m: {c: R[m][c] for c in S} for m in CONDS}
    PS = {m: {c: P[m][c] for c in S} for m in CONDS}
    table = STE.score(RS, PS, TS, "gold")
    cols = ["GoldR@1", "GoldR@5", "GoldR@10", "GoldR@20", "GoldR@50", "GoldR@100", "GoldMRR@100",
            "Gold_claim_coverage", "n_gold_claims"]
    log(f"\n=== HUMAN-GOLD ENDPOINT on S (n={len(S)}) ===")
    log("cond | " + " | ".join(cols))
    for m in CONDS:
        log(m, "|", " | ".join(str(table[m][k]) for k in cols))

    tests = []
    for k in (10, 5, 20):
        rows = []
        for b, a in (("D1", "A0"), ("X1", "A0"), ("X1", "D1")):
            ha = [(first_rank(R[a][c], T[c]["gold"]) or 999) <= k for c in S]
            hb = [(first_rank(R[b][c], T[c]["gold"]) or 999) <= k for c in S]
            w, l, p = V.mcnemar(ha, hb)
            d, lo, hi = V.boot_ci(ha, hb)
            rows.append({"metric": f"R@{k}", "comparison": f"{b} vs {a}", "n": len(S), "wins": w, "losses": l,
                         "ties": len(S) - w - l, "p_exact_mcnemar": round(p, 5), "diff": d, "ci95_low": lo, "ci95_high": hi})
        if k == 10:
            for row, adj in zip(rows, V.holm([x["p_exact_mcnemar"] for x in rows])):
                row["p_holm"] = round(adj, 5)
                row["family"] = "AQA-P2 (R@10, 3 tests, Holm within this family only) - EXPLORATORY, not preregistered"
        else:
            for row in rows:
                row["p_holm"] = ""
                row["family"] = "descriptive, uncorrected - EXPLORATORY"
        tests += rows
    log("\n=== PAIRED TESTS on S (exploratory) ===")
    for t in tests:
        log(f"{t['metric']:5} {t['comparison']:9} +{t['wins']}/-{t['losses']}/={t['ties']} p={t['p_exact_mcnemar']} "
            f"holm={t['p_holm']} diff={t['diff']} CI[{t['ci95_low']}, {t['ci95_high']}]")

    # ---- per-claim records and ranking changes
    err = {int(x["claim_id"]): x for x in csv.DictReader(open(ROOT / "results/source_targeted/error_analysis_heldout.csv", encoding="utf-8"))}
    per_claim = []
    for c in S:
        ra, rd, rx = (first_rank(R[m][c], T[c]["gold"]) for m in CONDS)
        top10_a = [u for u, _ in R["A0"][c][:10]]
        top10_x = [u for u, _ in R["X1"][c][:10]]
        per_claim.append({"claim_id": c, **{k: assign[c][k] for k in ("d1_category", "d1_pool_docs", "x1_key",
                          "x1_category", "x1_pool_docs", "doc_gap", "tie_size")},
                          "predicted_matches_gold_publisher": err[c]["auth_any_gold_key"],
                          "A0_first_gold_rank": ra or "", "D1_first_gold_rank": rd or "", "X1_first_gold_rank": rx or "",
                          "X1_minus_A0_rank_shift": (rx or 101) - (ra or 101),
                          "X1_top10_docs_replaced": len(set(top10_a) - set(top10_x))})
    big = [r for r in per_claim if abs(r["X1_minus_A0_rank_shift"]) >= 5
           or ((r["A0_first_gold_rank"] or 999) <= 10) != ((r["X1_first_gold_rank"] or 999) <= 10)]
    log(f"\nclaims where X1 moved the first gold document by >=5 ranks or across the top-10 boundary: {len(big)}")
    for r in big:
        log(f"  claim {r['claim_id']}: A0 {r['A0_first_gold_rank'] or '>100'} -> X1 {r['X1_first_gold_rank'] or '>100'} "
            f"(D1 {r['D1_first_gold_rank'] or '>100'}), x1={r['x1_key']} ({r['x1_pool_docs']} docs, gap {r['doc_gap']}), "
            f"top-10 docs replaced {r['X1_top10_docs_replaced']}")
    log("descriptive by stored flag (predicted publisher matches a gold publisher), R@10 hits:")
    for g in ("True", "False"):
        cs = [c for c in S if err[c]["auth_any_gold_key"] == g]
        log(f"  flag={g:5} n={len(cs):2d} | " + " ".join(
            f"{m}={sum((first_rank(R[m][c], T[c]['gold']) or 999) <= 10 for c in cs)}" for m in CONDS))

    # ---- integrity after scoring
    after = sha(ASSIGN)
    log(f"\n[assignment] SHA-256 after scoring {after} | unchanged={after == recorded}")
    if after != recorded:
        sys.exit("STOPPED: assignment changed during scoring.")

    def wcsv(name, rows):
        with open(OUT / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    wcsv("per_system.csv", [{"condition": m, **{k: table[m][k] for k in cols}} for m in CONDS])
    wcsv("tests.csv", tests)
    wcsv("per_claim.csv", per_claim)
    inputs = {k: ROOT / v for k, v in {
        "sample": "data/processed/averitec_heldout.jsonl", "predictions": "results/heldout/authority_raw.jsonl",
        "hybrid_rankings": "results/heldout/rankings_hybrid.jsonl.gz",
        "frozen_rankings": "results/source_targeted/rankings_heldout.jsonl.gz",
        "error_analysis_csv": "results/source_targeted/error_analysis_heldout.csv",
        "phase1_per_claim": "results/authority_quality_ablation/per_claim.csv",
        "x1_assignment": "results/authority_quality_ablation_phase2/x1_assignment.csv",
        "code_build_x1": "experiments/authority_quality_ablation/build_x1_assignment.py",
        "code_run_x1": "experiments/authority_quality_ablation/run_x1.py",
        "code_validation_heldout": "experiments/validation_heldout.py",
        "code_source_targeted_eval": "experiments/source_targeted_eval.py",
        "code_source_targeted": "experiments/source_targeted.py",
        "code_authority_retrieval": "experiments/authority_retrieval.py"}.items()}
    summary = {"experiment": "authority_quality_ablation_phase2_matched_mismatch",
               "status": "EXPLORATORY - not preregistered; X1 is a deliberately mismatched authority perturbation",
               "started": started, "finished": datetime.datetime.now().isoformat(timespec="seconds"),
               "git": "experiment code is outside any git repository; nested repo Source_Aware_Misinformation_Detector "
                      "(manuscript only) at HEAD e7d3cd0; SHA-256 provenance below",
               "python": platform.python_version(), "lambda": V.LAMBDA, "pool": V.POOL, "seed_x1_tiebreak": 2029,
               "bootstrap_seed": V.SEED_BOOT, "sample_seed": V.SEED_SAMPLE,
               "denominator": f"S: {len(S)} gold-reachable claims whose D1 publisher has >=1 doc in the frozen hybrid top-100",
               "x1_assignment_sha256": recorded,
               "provenance": {k: {"path": str(v.relative_to(ROOT)), "sha256": sha(v)} for k, v in inputs.items()},
               "results": {m: table[m] for m in CONDS}, "tests": tests,
               "claims_with_substantial_x1_change": [r["claim_id"] for r in big]}
    json.dump(summary, open(OUT / "summary.json", "w", encoding="utf-8"), indent=1)
    (OUT / "log.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    log("wrote:", ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
