"""Descriptive paired comparisons within strata (EXPLORATORY, uncorrected).

Reads results/authority_quality_ablation/per_claim.csv (written by run_ablation.py) and writes
results/authority_quality_ablation/strata_paired.csv. Refuses to overwrite an existing output.
"""
import csv
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
import validation_heldout as V  # noqa: E402

OUT = ROOT / "results" / "authority_quality_ablation"
dst = OUT / "strata_paired.csv"
if dst.exists():
    sys.exit(f"REFUSED: {dst} exists")
rows = [r for r in csv.DictReader(open(OUT / "per_claim.csv", encoding="utf-8")) if r["gold_reachable"] == "True"]
hit = lambda r, m, k=10: r[f"{m}_first_gold_rank"] not in ("", None) and int(r[f"{m}_first_gold_rank"]) <= k
strata = {
    "predicted_matches_gold_publisher (stored flag)": lambda r: "match" if r["predicted_matches_gold_publisher"] == "True" else "no match",
    "gold_publishers (from human gold)": lambda r: "1 publisher" if int(r["n_gold_publishers"]) == 1 else ">=2 publishers",
}
out = []
for name, fn in strata.items():
    for g in sorted({fn(r) for r in rows}):
        cs = [r for r in rows if fn(r) == g]
        for b, a in (("D1", "A0"), ("D3", "A0"), ("D3", "D1"), ("O", "D3")):
            ha, hb = [hit(r, a) for r in cs], [hit(r, b) for r in cs]
            w, l, p = V.mcnemar(ha, hb)
            d, lo, hi = V.boot_ci(ha, hb)
            out.append({"stratifier": name, "group": g, "n": len(cs), "metric": "R@10", "comparison": f"{b} vs {a}",
                        "wins": w, "losses": l, "ties": len(cs) - w - l, "p_exact_mcnemar_uncorrected": round(p, 5),
                        "diff": d, "ci95_low": lo, "ci95_high": hi, "status": "descriptive, exploratory, uncorrected"})
            print(f"{name:48} {g:15} n={len(cs):3d} {b} vs {a}: +{w}/-{l}/={len(cs) - w - l} p={round(p, 4)} "
                  f"diff={d} CI[{lo}, {hi}]")
with open(dst, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)
print("wrote", dst.relative_to(ROOT))
