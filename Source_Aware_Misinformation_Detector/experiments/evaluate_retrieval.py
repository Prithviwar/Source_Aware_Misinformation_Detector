"""Step 6: evaluate every saved ranking (results/rankings_*.jsonl.gz).

Metrics per claim (K = 5, 10, 20):
  hit@K          >=1 gold evidence document in the top K  ("Recall@K" in the report)
  frac_recall@K  share of the claim's gold URLs in the top K
  primary_hit@K  >=1 gold document annotated A_primary (PILOT one-annotator
                 annotation, data/annotations/source_roles.csv) in the top K
  primary_domain_hit@K  softer: >=1 page from the domain of an annotated primary gold source
  mrr / primary_mrr     reciprocal rank of the first gold / primary gold doc (0 if not in top 100)
  role counts           role of each top-K doc: annotated gold role, or a role propagated
                        from an annotated gold doc of the SAME claim with the same
                        registered domain ("same-publisher"), or unannotated

Two denominators:
  all        claims with >=1 web gold URL (resp. >=1 primary); gold that is missing
             from the knowledge store or has empty text counts as a miss
  reachable  claims with >=1 gold (resp. primary) doc present in the KS with non-empty
             text -- the only claims on which any retriever can succeed (headline)

Paired statistics for pre-specified comparisons: exact McNemar test on per-claim
hits and a paired bootstrap (10,000 resamples) 95% CI of the difference.
"""
import csv
import glob
import json
import re
from collections import Counter
from math import comb

import numpy as np

from baseline_retrieval import claim_docs, load_rankings
from common import ANNOTATIONS, RESULTS, load_ks, load_sample, normalize_url, registered_domain

KS = (5, 10, 20)
ROLE = {"A_primary": "primary", "B_secondary": "secondary", "C_derived": "derived", "D_unclear": "unclear"}
HEADLINE_LAMBDA = "0.25"
BOOT = 10_000


def load_roles() -> dict[tuple[int, str], str]:
    with open(ANNOTATIONS / "source_roles.csv", encoding="utf-8") as fh:
        return {(int(r["claim_id"]), normalize_url(r["evidence_url"])): ROLE[r["source_role"]] for r in csv.DictReader(fh)}


def claim_context(sample, roles) -> tuple[dict, dict]:
    ctx, stats = {}, Counter()
    for r in sample:
        cid = r["claim_id"]
        docs = claim_docs(cid)
        raw = load_ks(cid)
        in_ks = {d["url_norm"] for d in docs}
        nonempty = {d["url_norm"] for d in docs if d["text"].strip()}
        gold = {g["source_url_norm"] for g in r["gold_evidence"] if g["is_web_source"]}
        role_of = {u: roles.get((cid, u), "unannotated") for u in gold}
        primary = {u for u, x in role_of.items() if x == "primary"}
        dom_role: dict[str, set] = {}
        for u, x in role_of.items():
            dom_role.setdefault(registered_domain(u), set()).add(x)
        ctx[cid] = {"gold": gold, "gold_reach": gold & nonempty, "primary": primary,
                    "primary_reach": primary & nonempty, "role_of": role_of, "dom_role": dom_role,
                    "primary_domains": {registered_domain(u) for u in primary}}
        stats["ks_docs_raw"] += len(raw)
        stats["ks_docs_raw_empty_text"] += sum(not d["text"].strip() for d in raw)
        stats["ks_docs_dedup"] += len(docs)
        stats["ks_docs_dedup_empty_text"] += len(docs) - len(nonempty)
        stats["retrieval_candidates"] += len(nonempty)
        stats["gold_answers"] += len(r["gold_evidence"])
        stats["gold_answers_no_web_source(Metadata/empty)"] += sum(not g["is_web_source"] for g in r["gold_evidence"])
        stats["gold_unique_web_urls"] += len(gold)
        stats["gold_urls_in_ks"] += len(gold & in_ks)
        stats["gold_urls_in_ks_empty_text"] += len((gold & in_ks) - nonempty)
        stats["gold_urls_missing_from_ks"] += len(gold - in_ks)
        stats["gold_urls_reachable"] += len(gold & nonempty)
        for x in ("primary", "secondary", "derived", "unclear", "unannotated"):
            stats[f"gold_role_{x}"] += sum(v == x for v in role_of.values())
            stats[f"gold_role_{x}_reachable"] += sum(v == x for u, v in role_of.items() if u in nonempty)
        stats["claims_with_web_gold"] += bool(gold)
        stats["claims_with_reachable_gold"] += bool(gold & nonempty)
        stats["claims_with_primary"] += bool(primary)
        stats["claims_with_reachable_primary"] += bool(primary & nonempty)
        stats["claims_no_reachable_gold"] += not (gold & nonempty)
    return ctx, dict(stats)


def doc_role(u: str, c: dict) -> str:
    if u in c["role_of"]:
        return c["role_of"][u]
    rs = c["dom_role"].get(registered_domain(u))
    if rs:
        return "same-publisher-as-" + ("primary" if "primary" in rs else sorted(rs)[0])
    return "unannotated"


def score(ranked: list[str], c: dict) -> dict:
    m = {}
    for k in KS:
        top = ranked[:k]
        m[f"hit@{k}"] = float(bool(c["gold"] & set(top)))
        m[f"frac_recall@{k}"] = len(c["gold"] & set(top)) / len(c["gold"]) if c["gold"] else None
        m[f"primary_hit@{k}"] = float(bool(c["primary"] & set(top)))
        m[f"primary_domain_hit@{k}"] = float(any(registered_domain(u) in c["primary_domains"] for u in top))
        m[f"roles@{k}"] = Counter(doc_role(u, c) for u in top)
    m["mrr"] = next((1 / i for i, u in enumerate(ranked, 1) if u in c["gold"]), 0.0)
    m["primary_mrr"] = next((1 / i for i, u in enumerate(ranked, 1) if u in c["primary"]), 0.0)
    return m


def subsets(ctx) -> dict[str, list[int]]:
    return {
        "gold_all": [c for c, x in ctx.items() if x["gold"]],
        "gold_reachable": [c for c, x in ctx.items() if x["gold_reach"]],
        "primary_all": [c for c, x in ctx.items() if x["primary"]],
        "primary_reachable": [c for c, x in ctx.items() if x["primary_reach"]],
    }


def aggregate(per: dict[int, dict], subs) -> dict:
    out = {}
    avg = lambda key, ids: round(sum(per[c][key] for c in ids) / len(ids), 4) if ids else None
    for scope in ("all", "reachable"):
        g, p = subs[f"gold_{scope}"], subs[f"primary_{scope}"]
        for k in KS:
            out[f"R@{k}[{scope}]"] = avg(f"hit@{k}", g)
            out[f"fracR@{k}[{scope}]"] = avg(f"frac_recall@{k}", g)
            out[f"PrimR@{k}[{scope}]"] = avg(f"primary_hit@{k}", p)
            out[f"PrimDomR@{k}[{scope}]"] = avg(f"primary_domain_hit@{k}", p)
        out[f"MRR[{scope}]"] = avg("mrr", g)
        out[f"PrimMRR[{scope}]"] = avg("primary_mrr", p)
    for k in KS:
        tot = Counter()
        for c in subs["gold_all"]:
            tot.update(per[c][f"roles@{k}"])
        n = sum(tot.values())
        for role in ("primary", "secondary", "derived", "unclear", "unannotated"):
            out[f"share_gold_{role}@{k}"] = round(tot[role] / n, 4)
        for role in ("primary", "secondary", "derived", "unclear"):
            out[f"share_samepub_{role}@{k}"] = round(tot[f"same-publisher-as-{role}"] / n, 4)
        out[f"share_unannotated_docs@{k}"] = round(tot["unannotated"] / n, 4)
    return out


def mcnemar_exact(a: list[float], b: list[float]) -> tuple[int, int, float]:
    """b better (n01), a better (n10), two-sided exact binomial p on discordant pairs."""
    n01 = sum(1 for x, y in zip(a, b) if x == 0 and y == 1)
    n10 = sum(1 for x, y in zip(a, b) if x == 1 and y == 0)
    n = n01 + n10
    if n == 0:
        return n01, n10, 1.0
    tail = sum(comb(n, i) for i in range(0, min(n01, n10) + 1)) / 2 ** n
    return n01, n10, min(1.0, 2 * tail)


def bootstrap_ci(a: list[float], b: list[float], seed: int = 0) -> tuple[float, float, float]:
    d = np.array(b, dtype=float) - np.array(a, dtype=float)
    idx = np.random.default_rng(seed).integers(0, len(d), size=(BOOT, len(d)))
    lo, hi = np.percentile(d[idx].mean(axis=1), [2.5, 97.5])
    return round(float(d.mean()), 4), round(float(lo), 4), round(float(hi), 4)


def holm(pvals: list[float]) -> list[float]:
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj, running = [0.0] * len(pvals), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvals) - rank) * pvals[i]))
        adj[i] = running
    return adj


def comparisons(methods: list[str]) -> list[tuple[str, str, str]]:
    """(family, baseline, treatment). Headline family: priors at lambda=0.25 vs their own base."""
    out = [("relevance", "bm25", "dense"), ("relevance", "bm25", "hybrid")]
    for base in ("bm25", "dense", "hybrid"):
        for v in ("generic", "entity", "claim", "full"):
            t = f"{base}+{v}_l{HEADLINE_LAMBDA}"
            if base in methods and t in methods:
                out.append(("authority@0.25", base, t))
                out.append(("authority@0.25,poolall", base, t + "_poolall"))
        if f"{base}+claim_l{HEADLINE_LAMBDA}" in methods and f"{base}+generic_l{HEADLINE_LAMBDA}" in methods:
            out.append(("claim-vs-generic", f"{base}+generic_l{HEADLINE_LAMBDA}", f"{base}+full_l{HEADLINE_LAMBDA}"))
            out.append(("claim-vs-generic", f"{base}+generic_l{HEADLINE_LAMBDA}", f"{base}+entity_l{HEADLINE_LAMBDA}"))
    extra = [m for m in methods if m.startswith("bm25+wikidata")]
    for m in extra:
        out.append(("post-hoc", "bm25", m))
    return [x for x in out if x[1] in methods and x[2] in methods]


def main():
    sample, roles = load_sample(), load_roles()
    ctx, corpus_stats = claim_context(sample, roles)
    subs = subsets(ctx)
    methods = sorted(re.sub(r"^.*rankings_(.*)\.jsonl\.gz$", r"\1", p.replace("\\", "/"))
                     for p in glob.glob(str(RESULTS / "rankings_*.jsonl.gz")))
    per_method, table = {}, []
    for m in methods:
        rk = load_rankings(m)
        per = {cid: score([u for u, _ in rk[cid]], ctx[cid]) for cid in ctx}
        per_method[m] = per
        table.append({"method": m, **aggregate(per, subs)})

    with open(RESULTS / "retrieval_results.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    with open(RESULTS / "retrieval_per_claim.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        keys = [k for k in next(iter(next(iter(per_method.values())).values())) if not k.startswith("roles")]
        w.writerow(["method", "claim_id", "has_reachable_gold", "has_reachable_primary", *keys])
        for m, per in per_method.items():
            for cid, x in per.items():
                w.writerow([m, cid, int(bool(ctx[cid]["gold_reach"])), int(bool(ctx[cid]["primary_reach"])),
                            *[x[k] for k in keys]])

    sig = []
    for fam, a, b in comparisons(methods):
        for metric, sub in [("hit@5", "gold_reachable"), ("hit@10", "gold_reachable"), ("hit@20", "gold_reachable"),
                            ("primary_hit@5", "primary_reachable"), ("primary_hit@10", "primary_reachable"),
                            ("primary_hit@20", "primary_reachable"), ("mrr", "gold_reachable"),
                            ("primary_mrr", "primary_reachable")]:
            ids = subs[sub]
            xa, xb = [per_method[a][c][metric] for c in ids], [per_method[b][c][metric] for c in ids]
            diff, lo, hi = bootstrap_ci(xa, xb)
            n01, n10, p = mcnemar_exact(xa, xb) if "mrr" not in metric else (None, None, None)
            sig.append({"family": fam, "baseline": a, "treatment": b, "metric": metric, "n_claims": len(ids),
                        "baseline_mean": round(sum(xa) / len(ids), 4), "treatment_mean": round(sum(xb) / len(ids), 4),
                        "diff": diff, "ci95_lo": lo, "ci95_hi": hi, "treatment_wins": n01, "baseline_wins": n10,
                        "mcnemar_p": None if p is None else round(p, 4)})
    fam_rows = [s for s in sig if s["family"] == "authority@0.25" and s["mcnemar_p"] is not None]
    for s, adj in zip(fam_rows, holm([s["mcnemar_p"] for s in fam_rows])):
        s["holm_p_within_family"] = round(adj, 4)
    with open(RESULTS / "significance.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for s in sig for k in s)))
        w.writeheader()
        w.writerows(sig)

    summary = {"corpus": corpus_stats, "subset_sizes": {k: len(v) for k, v in subs.items()},
               "n_sample_claims": len(sample), "methods": {r["method"]: r for r in table}}
    json.dump(summary, open(RESULTS / "retrieval_summary.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps(corpus_stats, indent=1))
    print({k: len(v) for k, v in subs.items()})
    cols = ["R@5[reachable]", "R@10[reachable]", "R@20[reachable]", "PrimR@5[reachable]", "PrimR@10[reachable]",
            "PrimR@20[reachable]", "MRR[reachable]", "PrimMRR[reachable]"]
    print("method".ljust(30), *[c.replace("[reachable]", "").rjust(8) for c in cols])
    for r in table:
        if r["method"] in ("bm25", "dense", "hybrid") or r["method"].endswith(f"_l{HEADLINE_LAMBDA}") or "wikidata" in r["method"]:
            print(r["method"].ljust(30), *[f"{r[c]:8.3f}" for c in cols])


if __name__ == "__main__":
    main()
