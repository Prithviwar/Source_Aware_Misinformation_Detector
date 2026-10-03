"""Step 6b: apparent duplication/derivation heuristics around PRIMARY sources.

For every claim with a reachable pilot-annotated primary gold document P:
  * find knowledge-store documents D (other registered domains) that reproduce
    P's content: containment of P's word 5-gram shingles in D >= THRESH
    ("apparent copies"; a heuristic, NOT verified provenance)
  * compare ranks: do the apparent copies outrank P under bm25 / dense?
  * does D name P's publisher (domain label or Wikidata label of a claim entity
    whose official domain is P's)? -> "apparent attribution"
Also a threshold-sensitivity table for the copy-group analysis of top-K lists
(how many retrieved docs would be double-counted by naive majority voting).

Writes results/provenance_primary_copies.csv and results/provenance_summary.json.
"""
import csv
import json
import re
import sys
from collections import Counter

from baseline_retrieval import claim_docs, load_rankings
from common import RESULTS, load_sample, registered_domain
from evaluate_retrieval import claim_context, load_roles
from provenance_audit import components, shingles

THRESH = (0.3, 0.5, 0.7)


def containment(a: set, b: set) -> float:
    """share of a's shingles present in b"""
    return len(a & b) / len(a) if a else 0.0


def copy_groups(top: list[dict], sh: list[set], t: float) -> list[set]:
    edges = []
    for i in range(len(top)):
        for j in range(i + 1, len(top)):
            if sh[i] and sh[j]:
                inter = len(sh[i] & sh[j])
                if inter / min(len(sh[i]), len(sh[j])) >= t:
                    edges.append((i, j))
    return components(len(top), edges)


def main():
    methods = sys.argv[1:] or ["bm25", "dense"]
    sample, roles = load_sample(), load_roles()
    ctx, _ = claim_context(sample, roles)
    ranks = {m: load_rankings(m) for m in methods}
    rows, sens = [], {m: {t: Counter() for t in THRESH} for m in methods}
    for r in sample:
        cid, c = r["claim_id"], ctx[r["claim_id"]]
        docs = {d["url_norm"]: d for d in claim_docs(cid) if d["text"].strip()}
        sh_cache: dict[str, set] = {}
        sh = lambda u: sh_cache.setdefault(u, shingles(docs[u]["text"]))
        # (a) top-K copy groups: naive majority voting would count len(top) sources
        for m in methods:
            for k in (10, 20):
                top = [u for u, _ in ranks[m][cid][:k]]
                for t in THRESH:
                    g = copy_groups(top, [sh(u) for u in top], t)
                    s = sens[m][t]
                    s[f"docs@{k}"] += len(top)
                    s[f"groups@{k}"] += len(g)
                    s[f"claims_with_dup@{k}"] += len(g) < len(top)
                    s[f"claims_largest_group>=3@{k}"] += max(len(x) for x in g) >= 3
        # (b) apparent copies of each reachable primary document
        for p in sorted(c["primary_reach"]):
            sp = sh(p)
            if len(sp) < 20:  # too short to say anything about copying
                continue
            pdom = registered_domain(p)
            label = pdom.split(".")[0]
            order = {m: {u: i for i, (u, _) in enumerate(ranks[m][cid], 1)} for m in methods}
            for u, d in docs.items():
                if u == p or registered_domain(u) == pdom:
                    continue
                cont = containment(sp, sh(u))
                if cont < min(THRESH):
                    continue
                txt = d["text"][:20_000]
                rows.append({
                    "claim_id": cid, "claim": r["claim"][:160], "gold_label": r["gold_label"],
                    "primary_url": p, "copy_url": u, "copy_is_gold": u in c["gold"],
                    "copy_gold_role": c["role_of"].get(u, ""),
                    "containment_of_primary_in_copy": round(cont, 3),
                    "copy_names_primary_publisher": bool(re.search(rf"\b{re.escape(label)}\b", txt, re.I)) if len(label) >= 3 else "",
                    **{f"rank_primary_{m}": order[m].get(p) for m in methods},
                    **{f"rank_copy_{m}": order[m].get(u) for m in methods},
                })
    with open(RESULTS / "provenance_primary_copies.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    summary = {"topk_copy_groups": {m: {str(t): dict(v) for t, v in s.items()} for m, s in sens.items()}}
    prim_claims = {(x["claim_id"], x["primary_url"]) for x in rows}
    n_primary = sum(len(ctx[c]["primary_reach"]) for c in ctx)
    summary["primary_docs_reachable"] = n_primary
    for t in THRESH:
        sel = [x for x in rows if x["containment_of_primary_in_copy"] >= t]
        pr = {(x["claim_id"], x["primary_url"]) for x in sel}
        out = {"primary_docs_with_>=1_apparent_copy": len(pr), "apparent_copies": len(sel),
               "copies_naming_primary_publisher": sum(x["copy_names_primary_publisher"] is True for x in sel)}
        for m in methods:
            out[f"copies_outranking_primary_{m}"] = sum(
                (x[f"rank_copy_{m}"] or 10**9) < (x[f"rank_primary_{m}"] or 10**9) for x in sel)
            out[f"primaries_outranked_by_a_copy_{m}"] = len({(x["claim_id"], x["primary_url"]) for x in sel
                                                             if (x[f"rank_copy_{m}"] or 10**9) < (x[f"rank_primary_{m}"] or 10**9)})
        summary[f"containment>={t}"] = out
    json.dump(summary, open(RESULTS / "provenance_summary.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps(summary, indent=1))
    print(f"{len(prim_claims)} primary docs have candidate copies at >= {min(THRESH)}")


if __name__ == "__main__":
    main()
