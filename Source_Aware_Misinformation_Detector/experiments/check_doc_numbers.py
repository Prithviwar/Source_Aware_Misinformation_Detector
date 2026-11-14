"""Validation step 1: check that numbers in the docs' results tables equal the
machine-readable results (rounded to the precision shown in the doc).

Checks
  experiment_results.md §4.1  (9 numeric columns)  vs results/retrieval_results.csv [reachable]
  feasibility_decision.md §6.1 (6 numeric columns) vs results/retrieval_results.csv [reachable]
  authority_resolution_study.md gold-recall table   vs results/predicted_authority_retrieval.json
Writes results/doc_number_check.json and prints every mismatch.
"""
import csv
import json
import re

from common import ROOT, RESULTS

DOCS = ROOT / "docs"
CSV = {r["method"]: r for r in csv.DictReader(open(RESULTS / "retrieval_results.csv", encoding="utf-8"))}

# doc row label (substring, matched in order) -> method key in retrieval_results.csv
ROWS_41 = [
    ("A. BM25**", "bm25"), ("A′. Dense", "dense"), ("A″. Hybrid", "hybrid"),
    ("B. BM25 + generic credibility", "bm25+generic_l0.25"), ("B. Dense + generic", "dense+generic_l0.25"),
    ("C. BM25 + entity", "bm25+entity_l0.25"), ("C. BM25 + claim", "bm25+claim_l0.25"),
    ("C. BM25 + full", "bm25+full_l0.25"), ("C. Dense + full", "dense+full_l0.25"),
    ("C. Hybrid + full", "hybrid+full_l0.25"), ("C*. BM25 + Wikidata", "bm25+wikidata_l0.25"),
    ("C*. Dense + Wikidata", "dense+wikidata_l0.25"),
    ("BM25 + generic, λ=1, all", "bm25+generic_l1.0_poolall"), ("BM25 + full, λ=1, all", "bm25+full_l1.0_poolall"),
    ("BM25 + Wikidata, λ=1, all", "bm25+wikidata_l1.0_poolall"),
    ("Oracle primary domain, λ=.25", "bm25+oracle_l0.25"), ("Oracle primary domain, λ=1, all", "bm25+oracle_l1.0_poolall"),
]
COLS_41 = ["R@5", "R@10", "R@20", "PrimR@5", "PrimR@10", "PrimR@20", "MRR", "PrimMRR", "PrimDomR@10"]
ROWS_61 = [
    ("| BM25 |", "bm25"), ("| Dense |", "dense"), ("| Hybrid |", "hybrid"),
    ("Generic credibility (BM25 base)", "bm25+generic_l0.25"), ("Generic credibility (dense base)", "dense+generic_l0.25"),
    ("Claim-specific authority, full (BM25 base)", "bm25+full_l0.25"),
    ("Claim-specific authority, full (dense base)", "dense+full_l0.25"),
    ("Claim-specific, entity only (BM25)", "bm25+entity_l0.25"), ("Claim-specific, Wikidata (BM25", "bm25+wikidata_l0.25"),
    ("full, λ=1, all candidates", "bm25+full_l1.0_poolall"), ("Oracle authority", "bm25+oracle_l1.0_poolall"),
]
COLS_61 = COLS_41[:6]


def cells(line):
    return [c.strip().strip("*") for c in line.strip().strip("|").split("|")]


def check_table(doc, rows, cols, section_start, section_end):
    text = open(DOCS / doc, encoding="utf-8").read()
    text = text[text.index(section_start):text.index(section_end)]
    out = []
    for label, method in rows:
        line = next((l for l in text.splitlines() if l.startswith("|") and label in l), None)
        if line is None:
            out.append({"doc": doc, "row": label, "problem": "row not found"})
            continue
        vals = cells(line)[1:1 + len(cols)]
        for col, v in zip(cols, vals):
            if not re.fullmatch(r"[0-9.]+", v):
                continue
            truth = float(CSV[method][f"{col}[reachable]"])
            nd = len(v.split(".")[1]) if "." in v else 0
            ok = abs(round(truth, nd) - float(v)) < 1e-9
            out.append({"doc": doc, "row": label, "method": method, "col": col, "doc_value": v,
                        "file_value": round(truth, 4), "ok": ok})
    return out


def check_predicted():
    js = json.load(open(RESULTS / "predicted_authority_retrieval.json"))["gold_recall_all_claims"]["conditions"]
    text = open(DOCS / "authority_resolution_study.md", encoding="utf-8").read()
    text = text[text.index("## Circularity-free check"):]
    out = []
    for line in text.splitlines():
        m = re.match(r"\| (BM25|Dense|Hybrid) \| (λ=.25, top-100|λ=1, top-100|λ=1, all candidates)", line)
        if not m:
            continue
        base = m.group(1).lower()
        tag = {"λ=.25, top-100": "l0.25", "λ=1, top-100": "l1.0", "λ=1, all candidates": "l1.0_poolall"}[m.group(2)]
        c = cells(line)
        for col_i, key in ((2, base), (3, f"{base}+generic_{tag}"), (4, f"{base}+predicted_{tag}")):
            if not c[col_i]:
                continue
            doc_vals = [float("0" + x.strip()) for x in c[col_i].split("/")]
            file_vals = [js[key][f"R@{k}"] for k in (5, 10, 20)]
            ok = all(abs(round(f, 2) - d) < 1e-9 for f, d in zip(file_vals, doc_vals))
            out.append({"doc": "authority_resolution_study.md", "row": line[:40], "method": key,
                        "doc_value": c[col_i], "file_value": file_vals, "ok": ok})
    return out


def main():
    res = check_table("experiment_results.md", ROWS_41, COLS_41, "### 4.1", "### 4.2")
    res += check_table("feasibility_decision.md", ROWS_61, COLS_61, "### 6.1", "### 6.2")
    res += check_predicted()
    bad = [r for r in res if not r.get("ok")]
    print(f"checked {len(res)} cells; mismatches: {len(bad)}")
    for r in bad:
        print(r)
    json.dump({"checked": len(res), "mismatches": bad}, open(RESULTS / "doc_number_check.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
