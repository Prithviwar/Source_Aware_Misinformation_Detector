"""Phase 2 tie-break robustness check (DESCRIPTIVE ONLY; no hypothesis tests; not a new statistical family).

Rebuilds the X1 assignment in memory for the pre-declared seeds 2029-2048, varying ONLY the tie-break among
equally matched eligible publishers (same E1-E4 rules and closest-document-count criterion as
build_x1_assignment.py), and scores X1 on the same analysis set S.

Gate: at seed 2029 the in-memory assignment must equal the locked results/authority_quality_ablation_phase2/
x1_assignment.csv (whose recorded SHA-256 is verified), and the seed-2029 X1 row must equal the stored
Phase 2 per_system.csv. The primary Phase 2 result (seed 2029) is NOT rerun or modified.
Writes only to results/authority_quality_ablation_phase2_seeds/ and refuses to overwrite.
"""
import csv
import datetime
import hashlib
import json
import random
import statistics
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
import source_targeted_eval as STE  # noqa: E402
import validation_heldout as V  # noqa: E402
from authority_retrieval import generic_prior  # noqa: E402
from source_targeted import cand_key, primary_authority_candidates  # noqa: E402

SEEDS = list(range(2029, 2049))
CAT = {1.0: "government/intergovernmental", 0.8: "academic", 0.6: "major news", 0.5: "reference",
       0.3: "other/unknown", 0.2: "platform/blog"}
P2 = ROOT / "results" / "authority_quality_ablation_phase2"
OUT = ROOT / "results" / "authority_quality_ablation_phase2_seeds"
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def first_rank(ranking, target):
    return next((i for i, (u, _) in enumerate(ranking[:100], 1) if u in target), None)


def main():
    if OUT.exists() and any(OUT.iterdir()):
        sys.exit(f"REFUSED: {OUT} not empty")
    started = datetime.datetime.now().isoformat(timespec="seconds")
    log("Phase 2 tie-break robustness (descriptive) | started", started, "| seeds", SEEDS[0], "-", SEEDS[-1])
    recorded = (P2 / "x1_assignment.sha256").read_text(encoding="utf-8").split()[0]
    locked_sha = hashlib.sha256((P2 / "x1_assignment.csv").read_bytes()).hexdigest()
    locked = {int(r["claim_id"]): r for r in csv.DictReader(open(P2 / "x1_assignment.csv", encoding="utf-8"))}
    log(f"[locked assignment] recorded {recorded} | actual {locked_sha} | match={recorded == locked_sha}")
    if recorded != locked_sha:
        sys.exit("STOPPED: locked assignment hash mismatch")

    sample, preds, rk = STE.load_split("heldout")
    T, _, _ = STE.gold_truth("heldout", sample)
    # eligibility per claim (seed-independent), identical rules to build_x1_assignment.py
    elig, d1docs, S = {}, {}, []
    for c in sorted(c for c in T if T[c]["gold"]):
        cands = primary_authority_candidates(preds.get(c))
        top1 = set(cands[0]["keys"]) if cands else set()
        top3 = set().union(*[set(a["keys"]) for a in cands]) if cands else set()
        pool = rk["hybrid"][c][:100]
        n1 = sum(cand_key(u) in top1 for u, _ in pool)
        if n1 == 0:
            continue
        d1_cat = CAT[generic_prior(next(u for u, _ in pool if cand_key(u) in top1))]
        gold_pub = {cand_key(u) for u in T[c]["gold"]}
        pubs = {}
        for u, _ in pool:
            k = cand_key(u)
            pubs.setdefault(k, {"n": 0, "url": u})
            pubs[k]["n"] += 1
        e = {k: v["n"] for k, v in pubs.items()
             if k not in gold_pub and k not in top3 and CAT[generic_prior(v["url"])] == d1_cat}
        best = min(abs(n - n1) for n in e.values())
        elig[c] = sorted(k for k, n in e.items() if abs(n - n1) == best)
        d1docs[c] = (n1, {k: e[k] for k in elig[c]})
        S.append(c)

    A0 = {c: rk["hybrid"][c] for c in S}
    D1 = {}
    for c in S:
        cands = primary_authority_candidates(preds.get(c))
        k1 = set(cands[0]["keys"])
        D1[c] = V.rerank(rk["hybrid"][c], lambda u, k=k1: float(cand_key(u) in k))
    TS = {c: T[c] for c in S}
    pool = {c: {u for u, _ in rk["hybrid"][c][:V.POOL]} for c in S}
    stored = {r["condition"]: r for r in csv.DictReader(open(P2 / "per_system.csv", encoding="utf-8"))}
    cols = ["GoldR@1", "GoldR@5", "GoldR@10", "GoldR@20", "GoldR@50", "GoldR@100", "GoldMRR@100", "Gold_claim_coverage"]
    hitA = {c: (first_rank(A0[c], T[c]["gold"]) or 999) <= 10 for c in S}
    hitD = {c: (first_rank(D1[c], T[c]["gold"]) or 999) <= 10 for c in S}

    rows, assignments = [], {}
    for s in SEEDS:
        pick = {c: random.Random(s * 100000 + c).choice(elig[c]) for c in S}
        assignments[s] = pick
        X1 = {c: V.rerank(rk["hybrid"][c], lambda u, k=pick[c]: float(cand_key(u) == k)) for c in S}
        tab = STE.score({"X1": X1}, {"X1": pool}, TS, "gold")["X1"]
        gaps = [d1docs[c][1][pick[c]] - d1docs[c][0] for c in S]
        hitX = {c: (first_rank(X1[c], T[c]["gold"]) or 999) <= 10 for c in S}
        xa_w = sum(hitX[c] and not hitA[c] for c in S); xa_l = sum(hitA[c] and not hitX[c] for c in S)
        xd_w = sum(hitX[c] and not hitD[c] for c in S); xd_l = sum(hitD[c] and not hitX[c] for c in S)
        changed = sum(pick[c] != locked[c]["x1_key"] for c in S)
        row = {"seed": s, "primary": s == 2029, "picks_differing_from_seed2029": changed,
               "exact_doc_count_matches": sum(g == 0 for g in gaps), "non_exact": sum(g != 0 for g in gaps),
               "abs_gap_median": statistics.median(abs(g) for g in gaps), "abs_gap_mean": round(statistics.mean(abs(g) for g in gaps), 2),
               "abs_gap_max": max(abs(g) for g in gaps), "signed_gap_mean": round(statistics.mean(gaps), 2),
               "x1_fewer_docs": sum(g < 0 for g in gaps), "x1_more_docs": sum(g > 0 for g in gaps),
               **{k: tab[k] for k in cols},
               "X1_vs_A0_R@10_wins": xa_w, "X1_vs_A0_R@10_losses": xa_l, "X1_vs_A0_R@10_diff": round((xa_w - xa_l) / len(S), 4),
               "X1_vs_D1_R@10_wins": xd_w, "X1_vs_D1_R@10_losses": xd_l, "X1_vs_D1_R@10_diff": round((xd_w - xd_l) / len(S), 4)}
        rows.append(row)

    # gate on seed 2029
    g_assign = all(assignments[2029][c] == locked[c]["x1_key"] for c in S) and len(S) == len(locked) == 79
    r29 = rows[0]
    g_table = all(abs(float(stored["X1"][k]) - r29[k]) < 1e-9 for k in cols)
    log(f"[gate] seed-2029 in-memory assignment equals locked assignment (79 claims): {'PASS' if g_assign else 'FAIL'}")
    log(f"[gate] seed-2029 X1 metrics equal stored Phase 2 X1 row: {'PASS' if g_table else 'FAIL'}")
    if not (g_assign and g_table):
        sys.exit("STOPPED: gate failed")

    log("\nseed | differs | exact | non-exact | |gap| med/mean/max | signed mean | R@1 R@5 R@10 R@20 R@50 R@100 | MRR | cov | X1-A0 R@10 (w/l, diff) | X1-D1 R@10 (w/l, diff)")
    for r in rows:
        log(f"{r['seed']}{'*' if r['primary'] else ' '} | {r['picks_differing_from_seed2029']:2d} | {r['exact_doc_count_matches']} | {r['non_exact']} | "
            f"{r['abs_gap_median']}/{r['abs_gap_mean']}/{r['abs_gap_max']} | {r['signed_gap_mean']} | "
            + " ".join(str(r[k]) for k in cols[:6]) + f" | {r['GoldMRR@100']} | {r['Gold_claim_coverage']} | "
            f"+{r['X1_vs_A0_R@10_wins']}/-{r['X1_vs_A0_R@10_losses']} {r['X1_vs_A0_R@10_diff']} | "
            f"+{r['X1_vs_D1_R@10_wins']}/-{r['X1_vs_D1_R@10_losses']} {r['X1_vs_D1_R@10_diff']}")
    summ = {}
    for k in cols + ["X1_vs_A0_R@10_diff", "X1_vs_D1_R@10_diff", "picks_differing_from_seed2029", "signed_gap_mean"]:
        v = [r[k] for r in rows]
        summ[k] = {"min": min(v), "max": max(v), "mean": round(statistics.mean(v), 4), "sd": round(statistics.pstdev(v), 4)}
    log("\nrange over 20 seeds (min / max / mean / sd):")
    for k, v in summ.items():
        log(f"  {k:32} {v['min']} / {v['max']} / {v['mean']} / {v['sd']}")
    log(f"\nreference (fixed across seeds): A0 R@10 {stored['A0']['GoldR@10']}, D1 R@10 {stored['D1']['GoldR@10']}")

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "seeds.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(OUT / "assignments_by_seed.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["claim_id", "tie_size"] + [f"seed_{s}" for s in SEEDS])
        for c in S:
            w.writerow([c, len(elig[c])] + [assignments[s][c] for s in SEEDS])
    json.dump({"analysis": "Phase 2 tie-break robustness - DESCRIPTIVE ONLY, no hypothesis tests, not a statistical family",
               "primary_seed": 2029, "primary_result_unchanged": True, "seeds": SEEDS, "started": started,
               "finished": datetime.datetime.now().isoformat(timespec="seconds"),
               "locked_assignment_sha256": recorded, "gate_pass": True, "rows": rows, "range": summ,
               "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
              open(OUT / "summary.json", "w", encoding="utf-8"), indent=1)
    (OUT / "log.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    log("wrote:", ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
