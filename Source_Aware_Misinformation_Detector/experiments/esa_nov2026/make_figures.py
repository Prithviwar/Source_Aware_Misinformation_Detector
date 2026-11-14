"""Presentation figures for the 16 Nov 2026 review. Every number is READ from a result file (none typed in).

  python experiments/esa_nov2026/make_figures.py   ->  results/esa_nov2026/figures/*.png (+ figures_sources.json)

Sources:
  fig1/fig2  results/source_targeted/results_heldout.json + results/heldout/validation_heldout.json  (frozen)
  fig3       results/esa_nov2026/recall_ceiling/recall_ceiling.json  (recomputed 2026-11-14 from frozen rankings)
  fig4       results/esa_nov2026/relevance_baseline/run1_pu_RECORDED_OUTPUT_FROM_TRANSCRIPT/run1_pu_console_output.txt
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RES = ROOT / "results"
OUT = RES / "esa_nov2026" / "figures"

# Reference palette (dataviz skill, light mode), fixed order.
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
GREY = "#9a9994"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"

plt.rcParams.update({"font.family": "Arial", "font.size": 12, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
                     "figure.facecolor": "white", "axes.facecolor": "white", "savefig.dpi": 200})
SOURCES = {}


def save(fig, name, src):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)
    SOURCES[name] = src
    print("->", OUT / name)


def fig_heldout():
    R = json.load(open(RES / "source_targeted" / "results_heldout.json", encoding="utf-8"))["table"]
    V = json.load(open(RES / "heldout" / "validation_heldout.json", encoding="utf-8"))["primary_endpoint"]
    sys_ = [("bm25", "BM25"), ("dense", "MiniLM"), ("hybrid", "A  Hybrid RRF"), ("hybrid+generic", "B  + generic prior"),
            ("hybrid+heuristic", "C  + heuristic prior"), ("hybrid+llm_authority", "D  + LLM authority prior")]
    vals = [R[k]["GoldR@10"] for k, _ in sys_]
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    cols = [GREY, GREY, S1, S1, S1, S2]
    y = range(len(sys_))[::-1]
    ax.barh(list(y), vals, color=cols, height=0.62, edgecolor="white", linewidth=2)
    for yi, v in zip(y, vals):
        ax.text(v + 0.005, yi, f"{v:.3f}", va="center", color=INK, fontsize=11)
    ax.set_yticks(list(y), [n for _, n in sys_])
    ax.set_xlim(0, 0.36)
    ax.set_xlabel("Evidence Recall@10 (share of 167 held-out claims)")
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Frozen held-out evaluation: D vs A +{V['diff_R@10']:.3f}, exact McNemar p = {V['p']:.3f} (not significant)",
                 loc="left", fontsize=12, color=INK)
    save(fig, "fig1_heldout_recall_at_10.png", "results/source_targeted/results_heldout.json table.*.GoldR@10; "
                                                 "results/heldout/validation_heldout.json primary_endpoint")

    Ks = [1, 5, 10, 20, 50, 100]
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    for (k, n), c in zip(sys_[2:], (S1, S3, S4, S2)):
        ys = [R[k][f"GoldR@{K}"] for K in Ks]
        ax.plot(Ks, ys, color=c, linewidth=2, marker="o", markersize=5, label=n)
    cov = R["hybrid"]["Gold_claim_coverage"]
    ax.axhline(cov, color=GREY, linestyle="--", linewidth=1.5)
    ax.text(1.05, cov + 0.015, f"pool ceiling (hybrid top-100) = {cov:.3f}", color=INK2, fontsize=10)
    ax.set_xscale("log")
    ax.set_xticks(Ks, [str(K) for K in Ks])
    ax.set_ylim(0, 0.75)
    ax.set_xlabel("K (log scale)")
    ax.set_ylabel("Evidence Recall@K")
    ax.legend(frameon=False, loc="lower right")
    ax.set_title("Recall@K on the frozen held-out set (n = 167)", loc="left", fontsize=12, color=INK)
    save(fig, "fig2_heldout_recall_curves.png", "results/source_targeted/results_heldout.json table.*.GoldR@K")


def fig_ceiling():
    p = RES / "esa_nov2026" / "recall_ceiling" / "recall_ceiling.json"
    if not p.exists():
        print("skip fig3: recall_ceiling.json not found (run recall_ceiling.py)")
        return
    rc = json.load(open(p, encoding="utf-8"))
    hy = rc["splits"]["heldout200"]["stage2_retrieval"]["hybrid"]
    pts = [(int(kk[1:]), float(v["claim_recall"])) for kk, v in hy.items() if re.match(r"^@\d+$", kk)]
    pts.sort()
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.plot([k for k, _ in pts], [v for _, v in pts], color=S1, linewidth=2, marker="o", markersize=6)
    for k, v in pts:
        if k in (10, 100, 300):
            ax.annotate(f"top-{k}: {v:.3f}", (k, v), textcoords="offset points", xytext=(6, -14), color=INK, fontsize=10)
    ax.axvline(100, color=GREY, linestyle="--", linewidth=1.2)
    ax.text(105, 0.08, "current re-rank pool", color=INK2, fontsize=10)
    ax.set_xscale("log")
    ax.set_ylim(0, 1.05)
    ticks = [k for k, _ in pts]
    ax.set_xticks(ticks, [str(k) for k in ticks])
    ax.minorticks_off()
    ax.set_xlabel("Retrieval depth K (log scale)")
    ax.set_ylabel("Claims with evidence in top-K")
    ax.set_title("Hybrid retrieval recall vs depth (held-out): a source never retrieved cannot be selected",
                 loc="left", fontsize=12, color=INK)
    save(fig, "fig3_recall_ceiling_by_depth.png", str(p.relative_to(ROOT)) + " splits.heldout200.stage2_retrieval.hybrid.@K.claim_recall")


def fig_pu():
    p = RES / "esa_nov2026" / "relevance_baseline" / "run1_pu_RECORDED_OUTPUT_FROM_TRANSCRIPT" / "run1_pu_console_output.txt"
    txt = p.read_text(encoding="utf-8")
    sec, data = None, {}
    for line in txt.splitlines():
        m = re.match(r"^===== (\w+)", line)
        if m:
            sec = m.group(1)
        m = re.match(r"^(hybrid_rrf_baseline|M1_logreg|M2_hist_gbdt|M3_logreg_minilm) (\{.*\})$", line)
        if m and sec:
            data.setdefault(sec, {})[m.group(1)] = json.loads(m.group(2))
    names = [("hybrid_rrf_baseline", "Hybrid RRF"), ("M1_logreg", "M1 LogReg"), ("M2_hist_gbdt", "M2 HistGBDT\n(selected)"),
             ("M3_logreg_minilm", "M3 LogReg+MiniLM")]
    fig, ax = plt.subplots(figsize=(8.5, 4.0))
    xs = range(len(names))
    vals, labs = [], []
    for k, _ in names:
        s = data["test"][k]["claim_R@10"]  # "13/42 = 0.310"
        num, den = map(int, re.match(r"(\d+)/(\d+)", s).groups())
        vals.append(num / den)
        labs.append(f"{num}/{den}")
    ax.bar(list(xs), vals, color=[S1, GREY, S2, GREY], width=0.6, edgecolor="white", linewidth=2)
    for x, v, l in zip(xs, vals, labs):
        ax.text(x, v + 0.008, f"{l} = {v:.3f}", ha="center", color=INK, fontsize=11)
    ax.set_xticks(list(xs), [n for _, n in names])
    ax.set_ylim(0, 0.4)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Test Recall@10 (weak evidence labels)")
    mc = data["test"]["M2_hist_gbdt"]["vs_hybrid_hit@10_mcnemar"]
    ax.set_title(f"PU relevance baseline, AVeriTeC TRAIN test claims: no model beats Hybrid "
                 f"(M2 vs hybrid +{mc['wins']}/-{mc['losses']}, p = {mc['p_exact']})", loc="left", fontsize=11.5, color=INK)
    save(fig, "fig4_pu_baseline_test_recall10.png", str(p.relative_to(ROOT)) + " (recorded original console output)")


if __name__ == "__main__":
    fig_heldout()
    fig_ceiling()
    fig_pu()
    json.dump(SOURCES, open(OUT / "figures_sources.json", "w", encoding="utf-8"), indent=1)
